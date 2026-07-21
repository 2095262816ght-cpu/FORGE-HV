# -*- coding: utf-8 -*-
"""
FORGE 后端服务 —— 高温合金机器学习实验台 API（精简版）
====================================================================

文件作用
--------
Flask 后端服务，为 FORGE-HV 前端提供与论文对应的 REST API。
本版本严格对照论文《基于深度确定性策略梯度的合金维氏硬度预测算法》裁剪，
只保留论文中涉及的功能与算法。

核心功能（严格对齐论文章节）
--------
1. 数据准备与预处理（第 2 章）
   - 数据导入（支持 Excel / CSV 上传）
   - 数据预览、统计摘要、数据源条数统计
   - 异常值检测（分位数截断 / IsolationForest / IQR / Z-score）
   - 元素相关性矩阵（pearson / spearman / kendall）
2. DDPG 模型训练（第 3-4 章）
   - Actor-Critic 网络、优先经验回放、分段奖励
3. 5.3 / 5.4 对比实验（第 5.3 / 5.4 节）
   - 4 种算法横向对比：LinearRegression / PolynomialRegression / SVR / DDPG
   - 4 种评估指标：RMSE / MAE / R² / MAPE
   - 两种数据源：原始 149 条 / GAN 扩充数据
4. 数据库管理（保留）：结构化查询构建器

主要路由（@app.route）
--------------------
- GET  /api/health                  健康检查
- GET  /api/data/source_stats       数据源统计
- GET  /api/data/columns            数据列名
- GET  /api/data/preview            数据预览
- GET  /api/data/stats              统计摘要
- POST /api/data/upload             数据导入（Excel/CSV）
- POST /api/train/traditional       传统回归模型训练（LR/PR/SVR）
- POST /api/train/compare           多模型横向对比（5.3 / 5.4 用）
- GET  /api/train/export_csv        导出预测结果 CSV
- GET  /api/train/export_model      导出模型 pkl
- POST /api/outliers/detect         异常值检测
- GET  /api/correlation/matrix      元素相关性矩阵
- POST /api/database/query          数据库式结构化查询
- GET  /api/database/schema         数据表结构
- POST /api/ddpg/train             启动 DDPG 异步训练
- GET  /api/ddpg/status/<task_id>  查询 DDPG 训练进度
- GET  /api/ddpg/tasks             列出全部 DDPG 任务

依赖
----
- Flask, flask-cors        : Web 框架与跨域支持
- pandas, numpy            : 数据处理
- scikit-learn (sklearn)  : 传统机器学习
- torch (PyTorch)          : 可选，DDPG 强化学习
- scipy, joblib            : 统计工具与模型序列化

运行方式
--------
    python app.py
默认监听 127.0.0.1:5000，开发模式 debug=True
"""
import os
import sys
import time
import json
import sqlite3
import hashlib
import secrets
import traceback
import threading
import uuid
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, g
from flask_cors import CORS

# 确保能 import 项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from CT_main import load_and_filter_gan_data, prepare_gan_features, calculate_metrics

# 可选依赖：JWT 鉴权
try:
    import jwt
    _HAS_JWT = True
except ImportError:
    _HAS_JWT = False
    print("[warn] PyJWT 未安装，用户登录功能将不可用。pip install PyJWT")

# 第三方机器学习库（只保留论文涉及的算法依赖）
import sklearn
import joblib
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# DDPG (PyTorch) —— 可选依赖，仅在 /api/ddpg/* 路由用到
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

app = Flask(__name__)
CORS(app)  # 允许前端跨域访问

# 目标变量列名：维氏硬度 HV
TARGET_COL = "Vickers Hardness (HV)"

# 训练结果缓存（最后一次训练的模型和预测数据，用于导出）
_LAST_TRAIN_CACHE = {
    "model": None, "model_name": None, "X_test": None, "y_test": None,
    "y_test_pred": None, "X_train": None, "y_train": None, "y_train_pred": None,
    "feature_cols": [], "target_col": TARGET_COL, "params": {},
    "data_source": "real", "test_size": config.TEST_SIZE, "timestamp": 0,
}

# 用户上传的数据文件路径（若上传过则覆盖默认数据文件）
_UPLOADED_DATA_PATH = {"path": None}


def _current_data_path():
    """返回当前使用的数据文件路径：若用户上传过数据则用上传的，否则用默认"""
    if _UPLOADED_DATA_PATH["path"] and os.path.exists(_UPLOADED_DATA_PATH["path"]):
        return _UPLOADED_DATA_PATH["path"]
    return config.DATA_FILE_MIC


# ============================================================
# 数据加载工具
# ============================================================
def load_training_data(source: str = "real", gan_weight: float = 0.2):
    """加载数据用于训练
    source 取值：
      real              ：实测 149 条数据
      gan               ：GAN 生成 + 实测合并数据（论文 5.4 节用）
      gan_train_real_test：GAN 训练 + 实测测试
    """
    path = _current_data_path()
    if source == "gan":
        # 优先使用合并后的 GAN 数据
        if os.path.exists(config.COMBINED_DATA_PATH):
            df = pd.read_excel(config.COMBINED_DATA_PATH)
        else:
            df = load_and_filter_gan_data()
        return df, None
    if source == "gan_train_real_test" and os.path.exists(config.COMBINED_DATA_PATH):
        # 实测样本 weight=-1（测试集），GAN 样本 weight=0.2（训练集降权）
        df = pd.read_excel(config.COMBINED_DATA_PATH)
        s = df[config.composition_columns].sum(axis=1)
        df = df[(s >= 85) & (s <= 115)].copy()
        # 标记样本权重：来源列若存在则按来源区分
        if "Source" in df.columns:
            sw = df["Source"].apply(lambda x: -1.0 if x == "real" else gan_weight).values
        else:
            # 无 Source 列时退化为统一权重
            sw = np.full(len(df), gan_weight)
        return df, sw
    # 默认：实测数据
    df = pd.read_excel(path)
    return df, None


def filter_features(X, feature_cols, y=None, mode="auto"):
    """特征筛选（保留接口以兼容现有调用，论文不强调此步）"""
    return X, feature_cols, []


# ============================================================
# 回归模型构造（只保留论文 5.1 节的 3 种传统算法）
# ============================================================
def build_model(name: str, params: dict = None):
    """根据算法名构造回归器
    论文 5.1 节对比算法：LinearRegression / PolynomialRegression / SVR
    """
    params = params or {}
    name = name.strip()

    def _p(key, default):
        v = params.get(key, default)
        return v if v is not None else default

    # 1. 线性回归（Linear Regression, LR）
    if name == "LinearRegression":
        return LinearRegression()

    # 2. 多项式回归（Polynomial Regression, PR）—— 二次多项式 + Ridge 防过拟合
    if name == "PolynomialRegression":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=int(_p("degree", 2)), include_bias=False)),
            ("model", Ridge(alpha=_p("alpha", 1.0))),
        ])

    # 3. 支持向量回归（SVR）—— 默认 RBF 核
    if name == "SVR":
        return Pipeline([("scaler", StandardScaler()),
                         ("model", SVR(kernel=_p("kernel", "rbf"),
                                       C=_p("C", 1.0), gamma=_p("gamma", "scale")))])

    # 默认退化为线性回归，保证不会因算法名错误而崩
    return LinearRegression()


def safe_float(x):
    """numpy 类型转 Python 原生 float，便于 JSON 序列化"""
    try:
        if isinstance(x, (np.floating, np.integer, np.bool_)):
            return float(x)
        if isinstance(x, np.ndarray):
            return x.tolist()
    except Exception:
        pass
    return x


# ============================================================
# 数据源统计
# ============================================================
@app.route("/api/data/source_stats")
def data_source_stats():
    """统计数据源条数：实测 / GAN / 混合"""
    try:
        real_df = pd.read_excel(_current_data_path())
        real_sum = real_df[config.composition_columns].sum(axis=1)
        real_valid = real_df[(real_sum >= 85) & (real_sum <= 115)]
        gan_total = 0
        gan_cleaned = 0
        if os.path.exists(config.GENERATED_DATA_PATH):
            gan_raw = pd.read_excel(config.GENERATED_DATA_PATH)
            gan_total = len(gan_raw)
            s = gan_raw[config.composition_columns].sum(axis=1)
            gan_cleaned = int(((s >= 85) & (s <= 115)).sum())
        return jsonify({
            "real_total": int(len(real_df)),
            "real_valid": int(len(real_valid)),
            "gan_total": int(gan_total),
            "gan_cleaned": int(gan_cleaned),
            "mix_default": int(len(real_valid) + gan_cleaned),
            "using_uploaded": _UPLOADED_DATA_PATH["path"] is not None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 健康检查
# ============================================================
@app.route("/api/health")
def health():
    """健康检查"""
    path = _current_data_path()
    return jsonify({
        "status": "ok",
        "service": "FORGE Backend",
        "data_file": path,
        "exists": os.path.exists(path),
        "using_uploaded": _UPLOADED_DATA_PATH["path"] is not None,
    })


# ============================================================
# 数据列名
# ============================================================
@app.route("/api/data/columns")
def data_columns():
    """返回数据表的列结构"""
    try:
        df = pd.read_excel(_current_data_path())
        return jsonify({
            "composition": config.composition_columns,
            "target": TARGET_COL,
            "all_columns": list(df.columns),
            "n_rows": len(df),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 数据预览
# ============================================================
@app.route("/api/data/preview")
def data_preview():
    """数据预览：返回前 n 行（默认 10，最大 500）"""
    try:
        n = int(request.args.get("n", 10))
        n = max(1, min(n, 500))
        df = pd.read_excel(_current_data_path())
        want_cols = ["Image_Name"] + config.composition_columns + [TARGET_COL]
        cols = [c for c in want_cols if c in df.columns]
        sub = df[cols].head(n)
        return jsonify({
            "columns": cols,
            "rows": sub.values.tolist(),
            "total": len(df),
            "n": n,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 数据统计摘要
# ============================================================
@app.route("/api/data/stats")
def data_stats():
    """统计摘要：样本数、元素数、HV 的 min/max/mean/std/median"""
    try:
        df = pd.read_excel(_current_data_path())
        y = df[TARGET_COL].dropna()
        return jsonify({
            "n_samples": int(len(df)),
            "n_elements": len(config.composition_columns),
            "n_microstructure": 70,
            "hv_min": safe_float(y.min()),
            "hv_max": safe_float(y.max()),
            "hv_mean": safe_float(y.mean()),
            "hv_std": safe_float(y.std()),
            "hv_median": safe_float(y.median()),
            "using_uploaded": _UPLOADED_DATA_PATH["path"] is not None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 数据导入（Excel / CSV）—— 对应论文 2 章数据来源说明
# ============================================================
@app.route("/api/data/upload", methods=["POST"])
def data_upload():
    """数据导入：接收前端上传的 Excel(.xlsx/.xls) 或 CSV 文件
    存到项目 generated_data/uploaded_data.<ext>，并切换后端数据源到该文件
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "未收到文件（字段名应为 file）"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "文件名为空"}), 400

        # 按扩展名决定保存格式
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".xlsx", ".xls", ".csv"):
            return jsonify({"error": "仅支持 .xlsx / .xls / .csv 格式"}), 400

        os.makedirs(os.path.join(config.BASE_DIR, "generated_data"), exist_ok=True)
        save_path = os.path.join(config.BASE_DIR, "generated_data", f"uploaded_data{ext}")
        f.save(save_path)

        # 校验文件可读 + 包含必要列
        try:
            if ext == ".csv":
                df = pd.read_csv(save_path)
            else:
                df = pd.read_excel(save_path)
        except Exception as e:
            os.remove(save_path)
            return jsonify({"error": f"文件解析失败：{e}"}), 400

        # 检查目标列是否存在
        if TARGET_COL not in df.columns:
            # 尝试模糊匹配
            target_candidates = [c for c in df.columns if "hardness" in c.lower() or "hv" in c.lower()]
            if not target_candidates:
                os.remove(save_path)
                return jsonify({
                    "error": f"文件缺少目标列 '{TARGET_COL}'（或含 hardness/HV 的列）"
                }), 400

        # 切换数据源
        _UPLOADED_DATA_PATH["path"] = save_path
        return jsonify({
            "status": "ok",
            "filename": f.filename,
            "saved_path": save_path,
            "n_rows": int(len(df)),
            "n_cols": int(len(df.columns)),
            "columns": list(df.columns)[:30],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/reset", methods=["POST"])
def data_reset():
    """重置为默认数据文件（取消使用上传数据）"""
    _UPLOADED_DATA_PATH["path"] = None
    return jsonify({"status": "ok", "using_uploaded": False})


# ============================================================
# 传统回归模型训练（LR / PR / SVR）
# ============================================================
@app.route("/api/train/traditional", methods=["POST"])
def train_traditional():
    """传统回归模型训练（论文 5.1 节对比算法之一）

    请求体 JSON 字段：
      model           : str  算法名（LinearRegression / PolynomialRegression / SVR）
      test_size       : float 测试集比例
      params          : dict  手动超参数
      data_source     : str  数据源 real / gan / gan_train_real_test
      feature_filter  : str  特征筛选模式 off（论文不强调，保留接口）
      target_transform: str  目标变换 off / log
    """
    try:
        req = request.get_json() or {}
        model_name = req.get("model", "LinearRegression")
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))
        params = req.get("params", {}) or {}
        data_source = req.get("data_source", "real")
        params = {k: v for k, v in params.items() if v is not None and v != ""}

        df, sample_weight = load_training_data(data_source)
        X, y, feature_cols, target_col = prepare_gan_features(df)

        # gan_train_real_test 模式：GAN 训练 + 实测测试
        if data_source == "gan_train_real_test" and sample_weight is not None:
            train_mask = sample_weight > 0
            test_mask = sample_weight < 0
            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[test_mask], y[test_mask]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=config.RANDOM_STATE
            )

        model = build_model(model_name, params)
        model.fit(X_train, y_train)
        y_train_pred = model.predict(X_train)
        y_test_pred = model.predict(X_test)

        train_metrics = calculate_metrics(y_train, y_train_pred, "训练集")
        test_metrics = calculate_metrics(y_test, y_test_pred, "测试集")

        _LAST_TRAIN_CACHE.update({
            "model": model,
            "model_name": model_name,
            "X_test": X_test, "y_test": y_test, "y_test_pred": y_test_pred,
            "X_train": X_train, "y_train": y_train, "y_train_pred": y_train_pred,
            "feature_cols": feature_cols, "target_col": target_col,
            "params": params, "data_source": data_source,
            "test_size": test_size, "timestamp": time.time(),
        })

        scatter = [
            {"x": safe_float(y_test[i]), "y": safe_float(y_test_pred[i])}
            for i in range(len(y_test))
        ]
        # 自动写入历史预测记录
        try:
            _record_history(
                task_type="train_traditional",
                algorithm=model_name,
                data_source=data_source,
                metrics={"train": train_metrics, "test": test_metrics},
                params={"test_size": test_size, **params},
                n_samples=len(y_train) + len(y_test),
                duration_sec=0,
                status="done",
            )
        except Exception:
            pass
        return jsonify({
            "model": model_name,
            "params": params,
            "data_source": data_source,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "test_size": test_size,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "scatter": scatter,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 多模型横向对比（5.3 / 5.4 节用）
# ============================================================
@app.route("/api/train/compare", methods=["POST"])
def train_compare():
    """多模型横向对比：在统一数据划分上跑 LR / PR / SVR + K 折交叉验证

    请求体 JSON 字段：
      models    : list[str] 算法名列表（默认 ['LinearRegression','PolynomialRegression','SVR']）
      test_size : float 测试集比例
      cv_folds  : int   交叉验证折数
      data_source : str 数据源 real / gan / gan_train_real_test
    """
    try:
        req = request.get_json() or {}
        models = req.get("models", ["LinearRegression", "PolynomialRegression", "SVR"])
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))
        cv_folds = int(req.get("cv_folds", 5))
        cv_folds = max(2, min(cv_folds, 10))
        data_source = req.get("data_source", "real")

        df, sample_weight = load_training_data(data_source)
        X, y, feature_cols, target_col = prepare_gan_features(df)

        if data_source == "gan_train_real_test" and sample_weight is not None:
            train_mask = sample_weight > 0
            test_mask = sample_weight < 0
            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[test_mask], y[test_mask]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=config.RANDOM_STATE
            )

        results = []
        for name in models:
            t0 = time.time()
            try:
                m = build_model(name)
                m.fit(X_train, y_train)
                y_pred = m.predict(X_test)
                mt = calculate_metrics(y_test, y_pred, "测试集")
                # K 折交叉验证
                cv_scores = cross_val_score(
                    build_model(name), X_train, y_train,
                    cv=cv_folds, scoring="r2", n_jobs=-1,
                )
                results.append({
                    "model": name,
                    "r2": safe_float(mt["R2_value"]),
                    "rmse": safe_float(mt["RMSE_value"]),
                    "mae": safe_float(mt["MAE_value"]),
                    "mape": safe_float(mt["MAPE_value"]),
                    "cv_r2_mean": float(np.mean(cv_scores)),
                    "cv_r2_std": float(np.std(cv_scores)),
                    "cv_scores": [float(s) for s in cv_scores],
                    "time": round(time.time() - t0, 2),
                    "error": None,
                })
            except Exception as e:
                results.append({
                    "model": name, "r2": None, "rmse": None, "mae": None,
                    "mape": None, "cv_r2_mean": None, "cv_r2_std": None,
                    "cv_scores": [], "time": round(time.time() - t0, 2),
                    "error": str(e),
                })

        valid = [r for r in results if r["r2"] is not None]
        best = max(valid, key=lambda r: r["r2"])["model"] if valid else None

        return jsonify({
            "models": results,
            "best": best,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "cv_folds": cv_folds,
            "data_source": data_source,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 训练结果导出：CSV
# ============================================================
@app.route("/api/train/export_csv")
def train_export_csv():
    """导出最后一次训练的预测结果为 CSV"""
    import io
    from flask import send_file

    if _LAST_TRAIN_CACHE.get("model") is None:
        return jsonify({"error": "还没有训练记录，请先训练一次"}), 400
    try:
        cache = _LAST_TRAIN_CACHE
        y_train = cache["y_train"]; y_train_pred = cache["y_train_pred"]
        y_test = cache["y_test"]; y_test_pred = cache["y_test_pred"]

        df_out = pd.DataFrame({
            "split": ["train"] * len(y_train) + ["test"] * len(y_test),
            "y_actual": list(y_train) + list(y_test),
            "y_pred": list(y_train_pred) + list(y_test_pred),
            "residual": list(np.array(y_train) - np.array(y_train_pred))
                       + list(np.array(y_test) - np.array(y_test_pred)),
        })
        buf = io.BytesIO()
        buf.write(f"# model={cache['model_name']}, source={cache.get('data_source','real')}\n".encode("utf-8"))
        df_out.to_csv(buf, index=False, encoding="utf-8-sig")
        buf.seek(0)
        return send_file(
            buf, as_attachment=True,
            download_name=f"predictions_{cache['model_name']}_{int(cache['timestamp'])}.csv",
            mimetype="text/csv"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 训练结果导出：模型 pkl
# ============================================================
@app.route("/api/train/export_model")
def train_export_model():
    """导出最后一次训练的模型为 pkl 文件"""
    import io
    from flask import send_file

    if _LAST_TRAIN_CACHE.get("model") is None:
        return jsonify({"error": "还没有训练记录，请先训练一次"}), 400
    try:
        cache = _LAST_TRAIN_CACHE
        bundle = {
            "model": cache["model"],
            "model_name": cache["model_name"],
            "feature_cols": cache["feature_cols"],
            "target_col": cache["target_col"],
            "params": cache.get("params", {}),
            "data_source": cache.get("data_source", "real"),
            "sklearn_version": sklearn.__version__,
        }
        buf = io.BytesIO()
        joblib.dump(bundle, buf)
        buf.seek(0)
        return send_file(
            buf, as_attachment=True,
            download_name=f"model_{cache['model_name']}_{int(cache['timestamp'])}.pkl",
            mimetype="application/octet-stream"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 异常值检测（论文 2 章分位数截断 + 多方法支持）
# ============================================================
@app.route("/api/outliers/detect", methods=["POST"])
def outliers_detect():
    """异常值检测：支持 quantile_clip / isolation_forest / iqr / zscore 四种方法

    请求体 JSON 字段：
      method       : str  检测方法
      contamination: float 异常比例（仅 isolation_forest 用）
      low_pct      : float 下分位（quantile_clip 用，默认 0.01）
      high_pct     : float 上分位（quantile_clip 用，默认 0.99）
    """
    try:
        req = request.get_json() or {}
        method = req.get("method", "quantile_clip")
        contamination = float(req.get("contamination", 0.05))
        low_pct = float(req.get("low_pct", 0.01))
        high_pct = float(req.get("high_pct", 0.99))

        df = pd.read_excel(_current_data_path())
        cols = config.composition_columns + [TARGET_COL]
        cols = [c for c in cols if c in df.columns]
        data = df[cols].dropna()

        if method == "quantile_clip":
            # 论文 2 章公式 (1)(2)(3)：分位数截断
            low = data.quantile(low_pct)
            high = data.quantile(high_pct)
            clipped = data.clip(lower=low, upper=high, axis=1)
            # 被截断的样本视为异常
            is_outlier = ((data < low) | (data > high)).any(axis=1).values
        elif method == "isolation_forest":
            iso = IsolationForest(contamination=contamination, random_state=config.RANDOM_STATE)
            labels = iso.fit_predict(data)
            is_outlier = labels == -1
        elif method == "iqr":
            q1 = data.quantile(0.25); q3 = data.quantile(0.75); iqr = q3 - q1
            is_outlier = ((data < (q1 - 1.5 * iqr)) | (data > (q3 + 1.5 * iqr))).any(axis=1).values
        elif method == "zscore":
            from scipy import stats
            z = np.abs(stats.zscore(data))
            is_outlier = (z > 3).any(axis=1)
        else:
            return jsonify({"error": f"未知方法：{method}"}), 400

        outlier_idx = np.where(is_outlier)[0].tolist()
        samples = []
        for i in outlier_idx[:50]:
            row = data.iloc[i]
            samples.append({
                "index": int(data.index[i]),
                "values": {c: safe_float(row[c]) for c in cols},
            })
        return jsonify({
            "method": method,
            "total": len(data),
            "n_outliers": len(outlier_idx),
            "outliers": samples,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 元素相关性矩阵（原"特征相关性"，论文 2 章术语修正）
# ============================================================
@app.route("/api/correlation/matrix")
def correlation_matrix():
    """返回 22 种元素成分的相关性矩阵（pearson / spearman / kendall）"""
    try:
        method = request.args.get("method", "pearson")
        df = pd.read_excel(_current_data_path())
        cols = [c for c in config.composition_columns if c in df.columns]
        corr = df[cols].corr(method=method).fillna(0)
        return jsonify({
            "method": method,
            "columns": cols,
            "matrix": corr.values.tolist(),
            "high_pairs": _high_corr_pairs(corr, cols),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _high_corr_pairs(corr, cols, threshold=0.7):
    """从相关性矩阵中筛选 |r| >= threshold 的高相关列对"""
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = float(corr.iloc[i, j])
            if abs(r) >= threshold:
                pairs.append({"a": cols[i], "b": cols[j], "r": round(r, 3)})
    return sorted(pairs, key=lambda x: abs(x["r"]), reverse=True)


# ============================================================
# 数据库查询（保留页面）
# ============================================================
@app.route("/api/database/query", methods=["POST"])
def database_query():
    """可视化查询构建器后端
    接收结构化参数：
      columns   : list[str]  查询列，空表示全部
      filters   : list[{col, op, val}]  筛选条件（AND 连接）
      order_by  : {col, desc:bool}  排序
      limit     : int  返回行数上限
      aggregate : {func, col, group_by}  聚合查询
    """
    try:
        req = request.get_json() or {}
        df = pd.read_excel(_current_data_path())

        agg = req.get("aggregate")
        if agg and agg.get("func"):
            func_map = {"count": "count", "avg": "mean", "min": "min", "max": "max", "sum": "sum"}
            func = func_map.get(agg["func"].lower(), agg["func"].lower())
            group_by = agg.get("group_by") or []
            col = agg.get("col")
            if group_by:
                group_cols = [c for c in group_by if c in df.columns]
                if func == "count":
                    res = df.groupby(group_cols, dropna=False).size().reset_index(name="count")
                else:
                    if not col or col not in df.columns:
                        return jsonify({"error": f"聚合列 {col} 不存在"}), 400
                    res = df.groupby(group_cols, dropna=False)[col].agg(func).reset_index()
                    res.columns = group_cols + [f"{func}_{col}"]
            else:
                if func == "count":
                    res = pd.DataFrame({"count": [int(len(df))]})
                else:
                    if not col or col not in df.columns:
                        return jsonify({"error": f"聚合列 {col} 不存在"}), 400
                    res = pd.DataFrame({f"{func}_{col}": [float(df[col].agg(func))]})
            res = res.head(int(req.get("limit", 100)))
            return jsonify({"columns": list(res.columns), "rows": res.values.tolist(), "n": int(len(res))})

        # 普通查询：筛选
        for f in (req.get("filters") or []):
            c = f.get("col"); op = f.get("op"); v = f.get("val")
            if not c or c not in df.columns or not op:
                continue
            try:
                if op == "between":
                    parts = str(v).split(",")
                    if len(parts) == 2:
                        df = df[(df[c] >= float(parts[0])) & (df[c] <= float(parts[1]))]
                elif op == "contains":
                    df = df[df[c].astype(str).str.contains(str(v), na=False)]
                else:
                    num = float(v)
                    series = df[c]
                    if op == ">":   df = df[series > num]
                    elif op == "<": df = df[series < num]
                    elif op == ">=":df = df[series >= num]
                    elif op == "<=":df = df[series <= num]
                    elif op == "=": df = df[series == num]
                    elif op == "!=":df = df[series != num]
            except Exception:
                continue
        ob = req.get("order_by")
        if ob and ob.get("col") and ob["col"] in df.columns:
            df = df.sort_values(ob["col"], ascending=not ob.get("desc", False))
        cols = req.get("columns") or []
        cols = [c for c in cols if c in df.columns]
        if cols:
            df = df[cols]
        n = max(1, min(int(req.get("limit", 100)), 1000))
        df = df.head(n)
        return jsonify({"columns": list(df.columns), "rows": df.values.tolist(), "n": int(len(df))})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/schema")
def database_schema():
    """返回数据表的列结构"""
    try:
        df = pd.read_excel(_current_data_path())
        cols = []
        for c in df.columns:
            kind = "number" if pd.api.types.is_numeric_dtype(df[c]) else "text"
            cols.append({"name": c, "type": kind})
        return jsonify({
            "columns": cols,
            "n_rows": int(len(df)),
            "target": TARGET_COL,
            "composition": config.composition_columns,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# DDPG 深度强化学习 —— 异步训练接口（论文 3-4 章）
# ============================================================
_DDPG_TASKS = {}


def _run_ddpg_async(task_id, data_source, epochs, batch_size, lr_actor, lr_critic, test_size):
    """在后台线程中执行 DDPG 训练（论文 3-4 章算法实现）"""
    task = _DDPG_TASKS[task_id]
    try:
        # ---------- 数据加载 ----------
        if data_source == "gan":
            # 论文 5.4 节：使用 GAN 扩充后的数据
            if os.path.exists(config.COMBINED_DATA_PATH):
                df = pd.read_excel(config.COMBINED_DATA_PATH)
            else:
                df = load_and_filter_gan_data()
            s = df[config.composition_columns].sum(axis=1)
            df = df[(s >= 85) & (s <= 115)].copy()
        else:
            # 论文 5.3 节：原始 149 条数据
            df = pd.read_excel(_current_data_path())

        micro_cols = [f"Micro_{i+1}" for i in range(70)]
        feature_cols = micro_cols + config.composition_columns
        target_col = TARGET_COL

        df = df.dropna(subset=feature_cols + [target_col])
        X = df[feature_cols].values
        y = df[target_col].values
        y = np.clip(y, np.percentile(y, 1), np.percentile(y, 99))  # 论文 2 章分位数截断

        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, random_state=config.RANDOM_STATE
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=0.15, random_state=config.RANDOM_STATE
        )

        # 标准化（论文 2 章公式 4-6）
        X_scaler = StandardScaler(); X_train_s = X_scaler.fit_transform(X_train)
        X_val_s = X_scaler.transform(X_val); X_test_s = X_scaler.transform(X_test)
        y_scaler = StandardScaler()
        y_train_s = y_scaler.fit_transform(y_train.reshape(-1,1)).flatten()
        y_val_s = y_scaler.transform(y_val.reshape(-1,1)).flatten()
        y_test_s = y_scaler.transform(y_test.reshape(-1,1)).flatten()

        # ---------- 论文 3.2 节：Actor-Critic 网络定义 ----------
        class Actor(nn.Module):
            """论文 3.2 节 Actor 网络：4 个隐藏层 (1024→1024→512→256) + Tanh 输出"""
            def __init__(self, s_dim, a_dim, h=256):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Linear(s_dim, h), nn.BatchNorm1d(h), nn.LeakyReLU(0.1), nn.Dropout(0.1),
                    nn.Linear(h, h), nn.BatchNorm1d(h), nn.LeakyReLU(0.1), nn.Dropout(0.1),
                    nn.Linear(h, h//2), nn.BatchNorm1d(h//2), nn.LeakyReLU(0.1),
                    nn.Linear(h//2, a_dim), nn.Tanh()
                )
            def forward(self, x): return self.net(x)

        class Critic(nn.Module):
            """论文 3.2 节 Critic 网络：双流架构（state + action → Q 值）"""
            def __init__(self, s_dim, a_dim, h=256):
                super().__init__()
                self.s_net = nn.Sequential(nn.Linear(s_dim,h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(0.1))
                self.a_net = nn.Sequential(nn.Linear(a_dim,h//2), nn.BatchNorm1d(h//2), nn.ReLU())
                self.c_net = nn.Sequential(
                    nn.Linear(h+h//2, h), nn.ReLU(), nn.Dropout(0.1),
                    nn.Linear(h, h//2), nn.ReLU(), nn.Linear(h//2, 1)
                )
            def forward(self, s, a):
                return self.c_net(torch.cat([self.s_net(s), self.a_net(a)], dim=1))

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        s_dim = X_train_s.shape[1]
        actor = Actor(s_dim, 1).to(device)
        actor_target = Actor(s_dim, 1).to(device)
        actor_target.load_state_dict(actor.state_dict())
        critic = Critic(s_dim, 1).to(device)
        critic_target = Critic(s_dim, 1).to(device)
        critic_target.load_state_dict(critic.state_dict())

        opt_a = optim.AdamW(actor.parameters(), lr=lr_actor, weight_decay=1e-3)
        opt_c = optim.AdamW(critic.parameters(), lr=lr_critic, weight_decay=1e-3)
        gamma = 0.995; tau = 0.001  # 论文 3.1 节软更新系数 τ
        y_min = y_train_s.min(); y_max = y_train_s.max()

        # 论文 4.2 节：经验回放缓冲区
        buf = []; cap = 10000
        def push(e):
            if len(buf) < cap: buf.append(e)
            else: buf[np.random.randint(len(buf))] = e

        task.update({"status":"running", "device": str(device), "n_train": len(y_train),
                     "n_val": len(y_val), "n_test": len(y_test), "n_features": s_dim})

        critic_losses = []; actor_losses = []
        best_r2 = -np.inf; patience = 100; no_improve = 0

        for epoch in range(epochs):
            # 收集经验
            actor.eval()
            with torch.no_grad():
                all_acts = actor(torch.FloatTensor(X_train_s).to(device)).cpu().numpy().flatten()
            actor.train()
            for i in range(len(X_train_s)):
                st = X_train_s[i]; tgt = y_train_s[i]
                act = all_acts[i]
                # 论文 4.1 节：高斯噪声探索
                noise = np.random.normal(0, 0.2, act.shape)
                act = np.clip(act + noise, -1, 1)
                # 论文 3.3 节：动作缩放
                act_scaled = act * (y_max - y_min)/2 + (y_max + y_min)/2
                err = abs(act_scaled - tgt)
                # 论文 3.4 节：五段式奖励函数
                if err < 0.05: r = 5.0*(1-err/0.05)
                elif err < 0.1: r = 3.0*(1-err/0.1)
                elif err < 0.2: r = 2.0*(1-err/0.2)
                elif err < 0.5: r = 1.0*(1-err/0.5)
                else: r = -1.0*err
                r = float(np.clip(r, -5, 10))
                ni = np.random.randint(len(X_train_s))
                push((st, float(act), r, X_train_s[ni], 1.0 if (i+1)%100==0 else 0.0))

            # 更新网络
            if len(buf) >= batch_size:
                idx = np.random.choice(len(buf), batch_size, replace=False)
                batch = [buf[i] for i in idx]
                sts = torch.FloatTensor(np.stack([b[0] for b in batch])).to(device)
                acts = torch.FloatTensor(np.array([b[1] for b in batch]).reshape(-1,1)).to(device)
                rs = torch.FloatTensor(np.array([b[2] for b in batch]).reshape(-1,1)).to(device)
                nss = torch.FloatTensor(np.stack([b[3] for b in batch])).to(device)
                ds = torch.FloatTensor(np.array([b[4] for b in batch]).reshape(-1,1)).to(device)

                with torch.no_grad():
                    na = actor_target(nss)
                    tq = rs + (1-ds)*gamma*critic_target(nss, na)
                cq = critic(sts, acts)
                td = cq - tq
                cl = torch.where(td.abs()<1, 0.5*td**2, td.abs()-0.5).mean()
                opt_c.zero_grad(); cl.backward()
                torch.nn.utils.clip_grad_norm_(critic.parameters(), 0.5); opt_c.step()

                al = -critic(sts, actor(sts)).mean()
                opt_a.zero_grad(); al.backward()
                torch.nn.utils.clip_grad_norm_(actor.parameters(), 0.5); opt_a.step()

                # 论文 3.1 节：目标网络软更新 θ' ← (1-τ)·θ' + τ·θ
                for tp, p in zip(actor_target.parameters(), actor.parameters()):
                    tp.data.copy_(tp.data*(1-tau) + p.data*tau)
                for tp, p in zip(critic_target.parameters(), critic.parameters()):
                    tp.data.copy_(tp.data*(1-tau) + p.data*tau)

                critic_losses.append(float(cl.item()))
                actor_losses.append(float(al.item()))

            # 每 10 轮评估
            if (epoch+1) % 10 == 0 or epoch == epochs-1:
                actor.eval()
                with torch.no_grad():
                    p_val = actor(torch.FloatTensor(X_val_s).to(device)).cpu().numpy().flatten()
                    p_val = p_val * (y_max-y_min)/2 + (y_max+y_min)/2
                    p_val_orig = y_scaler.inverse_transform(p_val.reshape(-1,1)).flatten()
                actor.train()
                val_r2 = r2_score(y_val, p_val_orig)

                task.update({
                    "status": "running",
                    "epoch": epoch+1, "total_epochs": epochs,
                    "progress": (epoch+1)/epochs*100,
                    "critic_loss": critic_losses[-1] if critic_losses else 0,
                    "actor_loss": actor_losses[-1] if actor_losses else 0,
                    "val_r2": float(val_r2),
                    "losses": {"critic": critic_losses[-50:], "actor": actor_losses[-50:]},
                })

                if val_r2 > best_r2:
                    best_r2 = val_r2; no_improve = 0
                else:
                    no_improve += 1
                    if no_improve >= patience:
                        task["early_stopped"] = True
                        break

        # 最终评估（论文 5.2 节指标：RMSE / MAE / R² / MAPE）
        actor.eval()
        with torch.no_grad():
            def predict(Xs):
                p = actor(torch.FloatTensor(Xs).to(device)).cpu().numpy().flatten()
                p = p * (y_max-y_min)/2 + (y_max+y_min)/2
                return y_scaler.inverse_transform(p.reshape(-1,1)).flatten()
            yp_train = predict(X_train_s)
            yp_val = predict(X_val_s)
            yp_test = predict(X_test_s)

        def mtr(yt, yp):
            """论文 5.2 节四维评估指标"""
            r2 = float(r2_score(yt, yp))
            rmse = float(np.sqrt(mean_squared_error(yt, yp)))
            mae = float(mean_absolute_error(yt, yp))
            # MAPE：排除零值避免除零
            mask = np.abs(yt) > 1e-6
            mape = float(np.mean(np.abs((yt[mask] - yp[mask]) / yt[mask])) * 100) if mask.any() else 0.0
            return {"r2": r2, "rmse": rmse, "mae": mae, "mape": mape}

        task.update({
            "status": "done",
            "epoch": epoch+1, "total_epochs": epochs,
            "progress": 100.0,
            "metrics": {
                "train": mtr(y_train, yp_train),
                "val": mtr(y_val, yp_val),
                "test": mtr(y_test, yp_test),
            },
            "scatter": [
                {"x": float(y_test[i]), "y": float(yp_test[i])}
                for i in range(len(y_test))
            ],
            "best_val_r2": float(best_r2),
            "losses": {"critic": critic_losses[-200:], "actor": actor_losses[-200:]},
        })

    except Exception as e:
        traceback.print_exc()
        task.update({"status": "error", "error": str(e)})


@app.route("/api/ddpg/train", methods=["POST"])
def ddpg_train():
    """启动 DDPG 异步训练，立即返回 task_id"""
    if not _HAS_TORCH:
        return jsonify({"error": "PyTorch 未安装，无法训练 DDPG"}), 500
    try:
        req = request.get_json() or {}
        data_source = req.get("data_source", "real")  # real / gan
        epochs = max(1, int(req.get("epochs", 2000)))
        batch_size = max(2, int(req.get("batch_size", 32)))
        lr_actor = float(req.get("lr_actor", 1e-4))
        lr_critic = float(req.get("lr_critic", 5e-4))
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))

        # 清理超过 1 小时的旧任务
        now = time.time()
        expired = [tid for tid, t in _DDPG_TASKS.items()
                   if now - t.get("created_at", 0) > 3600]
        for tid in expired:
            _DDPG_TASKS.pop(tid, None)

        task_id = str(uuid.uuid4())[:12]
        _DDPG_TASKS[task_id] = {
            "status": "pending",
            "data_source": data_source,
            "epochs": epochs,
            "progress": 0,
            "created_at": time.time(),
        }
        t = threading.Thread(target=_run_ddpg_async, kwargs=dict(
            task_id=task_id, data_source=data_source, epochs=epochs,
            batch_size=batch_size, lr_actor=lr_actor, lr_critic=lr_critic, test_size=test_size,
        ), daemon=True)
        t.start()
        return jsonify({"task_id": task_id, "status": "pending"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ddpg/status/<task_id>")
def ddpg_status(task_id):
    """查询 DDPG 训练进度"""
    task = _DDPG_TASKS.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)


@app.route("/api/ddpg/tasks")
def ddpg_tasks():
    """列出所有 DDPG 训练任务"""
    tasks = []
    for tid, t in sorted(_DDPG_TASKS.items(), key=lambda x: x[1].get("created_at", 0), reverse=True):
        tasks.append({
            "task_id": tid,
            "status": t.get("status"),
            "data_source": t.get("data_source"),
            "progress": t.get("progress", 0),
            "epoch": t.get("epoch", 0),
            "total_epochs": t.get("total_epochs", 0),
            "val_r2": t.get("val_r2"),
            "created_at": t.get("created_at"),
        })
    return jsonify({"tasks": tasks})


# ============================================================
# 用户系统 + 历史记录 + 数据管理（统一扩展模块）
# ------------------------------------------------------------
# - SQLite 持久化：users / history / settings 三张表
# - JWT 鉴权：登录签发 token，受保护接口通过 @login_required 校验
# - 角色：admin（管理员）/ user（普通用户）
# - 历史：训练/预测完成自动落库，支持按时间/算法/用户筛选 + 导出
# - 数据管理：对当前数据源做行级增删改查 + 批量导入 + 导出
# ============================================================

DB_PATH = os.path.join(config.BASE_DIR, "forge.db")
JWT_SECRET = "forge-hv-secret-key-2026"  # 本地演示用，可改环境变量
JWT_EXP_HOURS = 24

_DB_LOCK = threading.Lock()


def _get_db():
    """获取 SQLite 连接（行级结果可按列名访问）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """初始化数据库表"""
    with _DB_LOCK:
        conn = _get_db()
        c = conn.cursor()
        # 用户表
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                display_name TEXT,
                email TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        # 历史预测记录表
        c.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                task_type TEXT,
                algorithm TEXT,
                data_source TEXT,
                metrics TEXT,
                params TEXT,
                n_samples INTEGER,
                duration_sec REAL,
                status TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        # 系统设置表（key-value）
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL,
                updated_by TEXT
            )
        """)
        conn.commit()

        # 首次启动自动创建默认 admin 账号
        c.execute("SELECT COUNT(*) AS n FROM users")
        if c.fetchone()["n"] == 0:
            _create_user_internal(c, "admin", "admin123", "admin", "管理员", "admin@forge.local")
            print("[init] 已创建默认管理员账号 admin / admin123")

        conn.commit()
        conn.close()


def _hash_password(password: str, salt: str = None) -> tuple:
    """密码加盐 SHA-256 哈希（本地演示级，生产建议用 bcrypt）"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return h, salt


def _create_user_internal(c, username, password, role="user", display_name=None, email=None):
    """内部工具：在已打开的 cursor 上创建用户"""
    h, salt = _hash_password(password)
    c.execute(
        "INSERT INTO users (username, password_hash, salt, role, display_name, email, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, h, salt, role, display_name, email, datetime.now().isoformat())
    )


def _generate_token(user_row) -> str:
    """签发 JWT token"""
    if not _HAS_JWT:
        return "no-jwt-" + secrets.token_hex(16)
    payload = {
        "user_id": user_row["id"],
        "username": user_row["username"],
        "role": user_row["role"],
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _parse_token() -> dict:
    """从请求头解析 token，失败返回 None"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    if not _HAS_JWT:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def login_required(admin_only: bool = False):
    """装饰器：要求登录（可选要求管理员）"""
    from functools import wraps
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            payload = _parse_token()
            if not payload:
                return jsonify({"error": "未登录或登录已过期"}), 401
            if admin_only and payload.get("role") != "admin":
                return jsonify({"error": "需要管理员权限"}), 403
            g.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ------------------------------------------------------------
# 用户认证 API
# ------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """用户登录：返回 JWT token 与用户信息"""
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    with _DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "用户名不存在"}), 404
        h, _ = _hash_password(password, row["salt"])
        if h != row["password_hash"]:
            conn.close()
            return jsonify({"error": "密码错误"}), 401
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), row["id"]))
        conn.commit()
        conn.close()

    token = _generate_token(row)
    return jsonify({
        "token": token,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "display_name": row["display_name"],
            "email": row["email"],
        }
    })


@app.route("/api/auth/me")
@login_required()
def auth_me():
    """获取当前登录用户信息"""
    return jsonify({"user": g.user})


@app.route("/api/auth/change_password", methods=["POST"])
@login_required()
def auth_change_password():
    """修改自己的密码"""
    data = request.get_json(force=True, silent=True) or {}
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")
    if not old_pwd or not new_pwd:
        return jsonify({"error": "原密码和新密码不能为空"}), 400
    if len(new_pwd) < 6:
        return jsonify({"error": "新密码至少 6 位"}), 400

    with _DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (g.user["user_id"],)).fetchone()
        h, _ = _hash_password(old_pwd, row["salt"])
        if h != row["password_hash"]:
            conn.close()
            return jsonify({"error": "原密码错误"}), 401
        new_h, new_salt = _hash_password(new_pwd)
        conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_h, new_salt, row["id"]))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# 用户管理 API（仅管理员）
# ------------------------------------------------------------
@app.route("/api/users")
@login_required(admin_only=True)
def users_list():
    """用户列表"""
    page = max(1, int(request.args.get("page", 1)))
    size = max(1, min(100, int(request.args.get("size", 20))))
    kw = request.args.get("keyword", "").strip()
    offset = (page - 1) * size
    sql = "SELECT id, username, role, display_name, email, created_at, last_login FROM users"
    args = []
    if kw:
        sql += " WHERE username LIKE ? OR display_name LIKE ? OR email LIKE ?"
        args += [f"%{kw}%", f"%{kw}%", f"%{kw}%"]
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [size, offset]
    with _DB_LOCK:
        conn = _get_db()
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
        total = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        conn.close()
    return jsonify({"items": rows, "total": total, "page": page, "size": size})


@app.route("/api/users", methods=["POST"])
@login_required(admin_only=True)
def users_create():
    """创建用户"""
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    role = (data.get("role") or "user").strip()
    display_name = (data.get("display_name") or "").strip() or None
    email = (data.get("email") or "").strip() or None
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    if role not in ("admin", "user"):
        return jsonify({"error": "role 必须是 admin 或 user"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少 6 位"}), 400
    try:
        with _DB_LOCK:
            conn = _get_db()
            c = conn.cursor()
            _create_user_internal(c, username, password, role, display_name, email)
            conn.commit()
            conn.close()
        return jsonify({"status": "ok"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "用户名已存在"}), 400


@app.route("/api/users/<int:uid>", methods=["PUT"])
@login_required(admin_only=True)
def users_update(uid):
    """修改用户（可改 role / display_name / email / 重置密码）"""
    data = request.get_json(force=True, silent=True) or {}
    with _DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "用户不存在"}), 404
        role = data.get("role") or row["role"]
        display_name = data.get("display_name", row["display_name"])
        email = data.get("email", row["email"])
        if role not in ("admin", "user"):
            conn.close()
            return jsonify({"error": "role 必须是 admin 或 user"}), 400
        conn.execute(
            "UPDATE users SET role = ?, display_name = ?, email = ? WHERE id = ?",
            (role, display_name, email, uid)
        )
        # 重置密码（可选）
        new_pwd = data.get("password")
        if new_pwd:
            if len(new_pwd) < 6:
                conn.close()
                return jsonify({"error": "密码至少 6 位"}), 400
            h, salt = _hash_password(new_pwd)
            conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (h, salt, uid))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/users/<int:uid>", methods=["DELETE"])
@login_required(admin_only=True)
def users_delete(uid):
    """删除用户（不能删除自己）"""
    if uid == g.user["user_id"]:
        return jsonify({"error": "不能删除当前登录用户"}), 400
    with _DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "用户不存在"}), 404
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# 历史预测记录 API
# ------------------------------------------------------------
def _record_history(task_type, algorithm, data_source, metrics, params, n_samples, duration_sec, status="done"):
    """记录一条历史（无登录时 user_id = NULL）"""
    payload = _parse_token()
    user_id = payload.get("user_id") if payload else None
    username = payload.get("username") if payload else None
    with _DB_LOCK:
        conn = _get_db()
        conn.execute(
            "INSERT INTO history (user_id, username, task_type, algorithm, data_source, metrics, params, "
            "n_samples, duration_sec, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, username, task_type, algorithm, data_source,
             json.dumps(metrics, ensure_ascii=False) if metrics else None,
             json.dumps(params, ensure_ascii=False) if params else None,
             n_samples, duration_sec, status, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()


@app.route("/api/history")
@login_required()
def history_list():
    """查询历史记录（支持按算法/数据源/时间筛选）"""
    page = max(1, int(request.args.get("page", 1)))
    size = max(1, min(100, int(request.args.get("size", 20))))
    offset = (page - 1) * size
    algorithm = request.args.get("algorithm", "").strip()
    data_source = request.args.get("data_source", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    sql = "SELECT * FROM history WHERE 1=1"
    args = []
    if algorithm:
        sql += " AND algorithm = ?"; args.append(algorithm)
    if data_source:
        sql += " AND data_source = ?"; args.append(data_source)
    if date_from:
        sql += " AND created_at >= ?"; args.append(date_from)
    if date_to:
        sql += " AND created_at <= ?"; args.append(date_to + " 23:59:59")
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    args += [size, offset]

    with _DB_LOCK:
        conn = _get_db()
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
        # 统计总数
        cnt_sql = "SELECT COUNT(*) AS n FROM history WHERE 1=1"
        cnt_args = []
        if algorithm: cnt_sql += " AND algorithm = ?"; cnt_args.append(algorithm)
        if data_source: cnt_sql += " AND data_source = ?"; cnt_args.append(data_source)
        if date_from: cnt_sql += " AND created_at >= ?"; cnt_args.append(date_from)
        if date_to: cnt_sql += " AND created_at <= ?"; cnt_args.append(date_to + " 23:59:59")
        total = conn.execute(cnt_sql, cnt_args).fetchone()["n"]
        conn.close()

    for r in rows:
        if r.get("metrics"):
            try: r["metrics"] = json.loads(r["metrics"])
            except Exception: pass
        if r.get("params"):
            try: r["params"] = json.loads(r["params"])
            except Exception: pass
    return jsonify({"items": rows, "total": total, "page": page, "size": size})


@app.route("/api/history/<int:hid>")
@login_required()
def history_detail(hid):
    """历史记录详情"""
    with _DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT * FROM history WHERE id = ?", (hid,)).fetchone()
        conn.close()
    if not row:
        return jsonify({"error": "记录不存在"}), 404
    r = dict(row)
    if r.get("metrics"):
        try: r["metrics"] = json.loads(r["metrics"])
        except Exception: pass
    if r.get("params"):
        try: r["params"] = json.loads(r["params"])
        except Exception: pass
    return jsonify(r)


@app.route("/api/history/export")
@login_required()
def history_export():
    """导出历史记录为 CSV"""
    with _DB_LOCK:
        conn = _get_db()
        rows = [dict(r) for r in conn.execute(
            "SELECT id, username, task_type, algorithm, data_source, metrics, params, "
            "n_samples, duration_sec, status, created_at FROM history ORDER BY id DESC"
        ).fetchall()]
        conn.close()
    import io, csv
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "用户", "任务类型", "算法", "数据源", "指标", "参数", "样本数", "耗时(s)", "状态", "时间"])
    for r in rows:
        writer.writerow([
            r["id"], r.get("username") or "", r.get("task_type") or "",
            r.get("algorithm") or "", r.get("data_source") or "",
            r.get("metrics") or "", r.get("params") or "",
            r.get("n_samples") or "", r.get("duration_sec") or "",
            r.get("status") or "", r.get("created_at") or ""
        ])
    from flask import Response
    return Response(
        "\ufeff" + buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=history.csv"}
    )


@app.route("/api/history/<int:hid>", methods=["DELETE"])
@login_required(admin_only=True)
def history_delete(hid):
    """删除历史记录（仅管理员）"""
    with _DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT * FROM history WHERE id = ?", (hid,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "记录不存在"}), 404
        conn.execute("DELETE FROM history WHERE id = ?", (hid,))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# 系统设置 API（key-value）
# ------------------------------------------------------------
_DEFAULT_SETTINGS = {
    "site_title": "FORGE 高温合金机器学习实验台",
    "default_data_source": "real",
    "allow_guest_browse": "false",
    "max_upload_size_mb": "50",
    "history_retention_days": "365",
}


@app.route("/api/settings")
def settings_get():
    """获取系统设置（公开接口，登录页要用）"""
    with _DB_LOCK:
        conn = _get_db()
        rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()}
        conn.close()
    merged = dict(_DEFAULT_SETTINGS)
    merged.update(rows)
    return jsonify({"settings": merged})


@app.route("/api/settings", methods=["PUT"])
@login_required(admin_only=True)
def settings_update():
    """更新系统设置（仅管理员）"""
    data = request.get_json(force=True, silent=True) or {}
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        return jsonify({"error": "settings 必须是对象"}), 400
    now = datetime.now().isoformat()
    user = g.user.get("username", "")
    with _DB_LOCK:
        conn = _get_db()
        for k, v in settings.items():
            conn.execute(
                "INSERT INTO settings (key, value, updated_at, updated_by) VALUES (?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (k, str(v), now, user)
            )
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# 数据管理 API（行级增删改查 + 导出）
# ------------------------------------------------------------
def _load_df_for_manage():
    """加载数据为 DataFrame，附带行号"""
    path = _current_data_path()
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    df = df.reset_index().rename(columns={"index": "_row_id"})
    return df


@app.route("/api/data/rows")
@login_required()
def data_rows():
    """数据行查询（支持分页 + 关键词搜索 + 按列排序）"""
    page = max(1, int(request.args.get("page", 1)))
    size = max(1, min(200, int(request.args.get("size", 20))))
    offset = (page - 1) * size
    keyword = request.args.get("keyword", "").strip()
    sort_col = request.args.get("sort", "").strip()
    sort_dir = request.args.get("dir", "asc").lower()
    try:
        df = _load_df_for_manage()
    except Exception as e:
        return jsonify({"error": f"加载数据失败：{e}"}), 500

    # 关键词搜索（任意列包含）
    if keyword:
        mask = pd.Series([False] * len(df))
        for col in df.columns:
            if col == "_row_id": continue
            mask = mask | df[col].astype(str).str.contains(keyword, case=False, na=False, regex=False)
        df = df[mask]

    total = len(df)
    # 排序
    if sort_col and sort_col in df.columns:
        df = df.sort_values(by=sort_col, ascending=(sort_dir != "desc"))
    df = df.iloc[offset: offset + size]

    # 转 list of dict（NaN 转 None）
    rows = df.where(pd.notnull(df), None).to_dict(orient="records")
    return jsonify({
        "items": rows,
        "total": total,
        "page": page,
        "size": size,
        "columns": list(df.columns),
    })


@app.route("/api/data/rows/<int:row_id>", methods=["PUT"])
@login_required()
def data_row_update(row_id):
    """修改一行（按 _row_id 定位）"""
    data = request.get_json(force=True, silent=True) or {}
    try:
        df = _load_df_for_manage()
        if row_id not in df["_row_id"].values:
            return jsonify({"error": "行号不存在"}), 404
        idx = df.index[df["_row_id"] == row_id][0]
        for col, val in data.items():
            if col in df.columns and col != "_row_id":
                df.at[idx, col] = val
        df = df.drop(columns=["_row_id"])
        path = _current_data_path()
        if path.lower().endswith(".csv"):
            df.to_csv(path, index=False)
        else:
            df.to_excel(path, index=False)
        return jsonify({"status": "ok"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/rows/<int:row_id>", methods=["DELETE"])
@login_required()
def data_row_delete(row_id):
    """删除一行"""
    try:
        df = _load_df_for_manage()
        if row_id not in df["_row_id"].values:
            return jsonify({"error": "行号不存在"}), 404
        idx = df.index[df["_row_id"] == row_id][0]
        df = df.drop(index=idx).drop(columns=["_row_id"])
        path = _current_data_path()
        if path.lower().endswith(".csv"):
            df.to_csv(path, index=False)
        else:
            df.to_excel(path, index=False)
        return jsonify({"status": "ok", "remaining": len(df)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/rows", methods=["POST"])
@login_required()
def data_row_create():
    """新增一行"""
    data = request.get_json(force=True, silent=True) or {}
    try:
        df = _load_df_for_manage().drop(columns=["_row_id"])
        new_row = {col: data.get(col) for col in df.columns}
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        path = _current_data_path()
        if path.lower().endswith(".csv"):
            df.to_csv(path, index=False)
        else:
            df.to_excel(path, index=False)
        return jsonify({"status": "ok", "n_rows": len(df)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/batch_import", methods=["POST"])
@login_required()
def data_batch_import():
    """批量导入：接收 Excel/CSV 文件，追加到当前数据源
    复用 /api/data/upload 的文件接收逻辑，但改为追加而非覆盖
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "未收到文件"}), 400
        f = request.files["file"]
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".xlsx", ".xls", ".csv"):
            return jsonify({"error": "仅支持 .xlsx / .xls / .csv"}), 400

        tmp_path = os.path.join(config.BASE_DIR, "generated_data", f"batch_tmp{ext}")
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        f.save(tmp_path)
        try:
            new_df = pd.read_csv(tmp_path) if ext == ".csv" else pd.read_excel(tmp_path)
        except Exception as e:
            os.remove(tmp_path)
            return jsonify({"error": f"文件解析失败：{e}"}), 400

        # 读取现有数据
        path = _current_data_path()
        old_df = pd.read_csv(path) if path.lower().endswith(".csv") else pd.read_excel(path)
        # 列对齐：只取共有列，缺失列补 NaN
        common_cols = [c for c in old_df.columns if c in new_df.columns]
        if not common_cols:
            os.remove(tmp_path)
            return jsonify({"error": "导入文件的列与现有数据完全不一致"}), 400
        appended = pd.concat([old_df, new_df[common_cols]], ignore_index=True)
        if path.lower().endswith(".csv"):
            appended.to_csv(path, index=False)
        else:
            appended.to_excel(path, index=False)
        os.remove(tmp_path)
        _record_history("batch_import", "data_import", path, None, {"filename": f.filename, "appended": len(new_df)}, len(appended), 0, "done")
        return jsonify({
            "status": "ok",
            "filename": f.filename,
            "appended_rows": int(len(new_df)),
            "total_rows": int(len(appended)),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/export")
@login_required()
def data_export():
    """导出当前数据源为 Excel/CSV"""
    fmt = request.args.get("format", "xlsx").lower()
    try:
        path = _current_data_path()
        df = pd.read_csv(path) if path.lower().endswith(".csv") else pd.read_excel(path)
        if fmt == "csv":
            import io
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            from flask import Response
            return Response(
                "\ufeff" + buf.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment;filename=data_export.csv"}
            )
        else:
            import io
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)
            from flask import send_file
            return send_file(buf, as_attachment=True, download_name="data_export.xlsx",
                             mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/analysis")
@login_required()
def data_analysis():
    """数据分析：特征统计 + 目标值分布 + 元素相关性摘要（参考论文 2 章）"""
    try:
        df = _load_df_for_manage().drop(columns=["_row_id"])
        # 数值列统计
        numeric_cols = [c for c in df.columns if df[c].dtype != object and c != "Image_Name"]
        stats = {}
        for col in numeric_cols:
            s = df[col].dropna()
            if len(s) == 0: continue
            stats[col] = {
                "count": int(len(s)),
                "min": safe_float(s.min()),
                "max": safe_float(s.max()),
                "mean": safe_float(s.mean()),
                "std": safe_float(s.std()),
                "median": safe_float(s.median()),
                "q1": safe_float(s.quantile(0.25)),
                "q3": safe_float(s.quantile(0.75)),
            }
        # 目标列分布
        target_stats = {}
        if TARGET_COL in df.columns:
            y = df[TARGET_COL].dropna()
            target_stats = {
                "count": int(len(y)),
                "min": safe_float(y.min()),
                "max": safe_float(y.max()),
                "mean": safe_float(y.mean()),
                "std": safe_float(y.std()),
                "hist_bins": [safe_float(x) for x in np.histogram(y, bins=15)[1].tolist()],
                "hist_counts": [int(x) for x in np.histogram(y, bins=15)[0].tolist()],
            }
        # 元素相关性摘要（与目标列的相关系数 Top 10）
        correlation_top = []
        if TARGET_COL in df.columns:
            elem_cols = [c for c in config.composition_columns if c in df.columns]
            if elem_cols:
                corr = df[elem_cols + [TARGET_COL]].corr()[TARGET_COL].drop(TARGET_COL).fillna(0)
                corr = corr.abs().sort_values(ascending=False).head(10)
                correlation_top = [{"element": k, "abs_corr": safe_float(v)} for k, v in corr.items()]
        return jsonify({
            "feature_stats": stats,
            "target_stats": target_stats,
            "correlation_top": correlation_top,
            "n_samples": len(df),
            "n_features": len(numeric_cols),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------
# 在训练接口里埋点：自动写历史
# ------------------------------------------------------------
_original_train_traditional = None


# ============================================================
# 入口
# ============================================================
# 初始化数据库（首次启动自动建表 + 创建默认 admin）
_init_db()

if __name__ == "__main__":
    print("=" * 50)
    print("FORGE 后端服务启动中（精简版 · 论文对齐）...")
    print(f"数据文件: {_current_data_path()}")
    print(f"文件存在: {os.path.exists(_current_data_path())}")
    print(f"PyTorch: {'可用' if _HAS_TORCH else '未安装'}")
    print(f"JWT 鉴权: {'可用' if _HAS_JWT else '未安装'}")
    print(f"数据库: {DB_PATH}")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=True)
