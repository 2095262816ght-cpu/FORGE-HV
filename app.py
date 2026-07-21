# -*- coding: utf-8 -*-
"""
FORGE 后端服务 —— 高温合金机器学习实验台 API
====================================================================

文件作用
--------
Flask 后端服务，为 FORGE-HV 高温合金机器学习实验台前端提供数据可视化、
特征工程、回归模型训练/预测、模型横向比较、DDPG 强化学习、主动学习优化等
REST API。

核心功能
--------
1. 数据可视化与统计：列名、预览、统计摘要、缺失值、相关性矩阵、PCA 降维
2. 异常检测：IsolationForest / IQR / Z-score 三种方法
3. 重复值检测：按成分列去重，结合 Image_Name 后缀识别独立实验
4. 特征工程：特征筛选（auto / importance）、PCA、特征重要性
5. 回归模型训练：14 种回归器（LinearRegression / Ridge / Lasso / SVR /
   RandomForest / ExtraTrees / GBDT / AdaBoost / Bagging / MLP / XGBoost /
   Stacking / GaussianProcess / KernelRidge 等），支持手动超参与 GridSearchCV
6. 模型横向比较：在统一数据划分上跑多个模型 + K 折交叉验证
7. DDPG 强化学习：基于 PyTorch 的简化 DDPG，异步训练 + 状态轮询
8. 主动学习优化：训练代理模型 → 拉丁超立方采样生成设计空间 →
   acquisition function（greedy / ei / ucb / thompson / bayes）筛选推荐样本
9. 数据库式查询：结构化查询构建器（columns / filters / order_by / aggregate）

主要路由（@app.route）
--------------------
- GET  /api/health                  健康检查
- GET  /api/data/source_stats       数据源统计（实测/GAN/混合条数）
- GET  /api/data/columns            数据列名
- GET  /api/data/preview            数据预览
- GET  /api/data/stats              统计摘要
- POST /api/train/traditional       传统回归模型训练
- POST /api/train/grid_search       网格搜索超参优化
- POST /api/train/compare           多模型横向比较
- GET  /api/train/export_csv         导出预测结果 CSV
- GET  /api/train/export_model      导出模型 pkl
- POST /api/outliers/detect         异常值检测
- GET  /api/duplicates/detect       重复值检测
- GET  /api/correlation/matrix     相关性矩阵
- GET  /api/features/pca           PCA 降维
- GET  /api/features/importance    特征重要性
- GET  /api/missing/stats          缺失值统计
- POST /api/missing/fill            缺失值填充
- POST /api/clustering/kmeans      KMeans 聚类
- POST /api/database/query         数据库式结构化查询
- GET  /api/database/schema        数据表结构
- POST /api/active/optimize        主动学习优化
- GET  /api/active/export_csv      导出推荐样本 CSV
- GET  /api/system/info            系统信息
- GET  /api/system/recommend       训练参数推荐
- POST /api/ddpg/train             启动 DDPG 异步训练
- GET  /api/ddpg/status/<task_id>  查询 DDPG 训练进度
- GET  /api/ddpg/tasks             列出全部 DDPG 任务

依赖
----
- Flask, flask-cors        : Web 框架与跨域支持
- pandas, numpy            : 数据处理
- scikit-learn (sklearn)  : 传统机器学习
- xgboost                  : 可选，XGBoost 回归
- torch (PyTorch)          : 可选，DDPG 强化学习
- scipy                    : 统计工具（zscore / norm）
- joblib                   : 模型序列化
- psutil                   : 系统状态查询

运行方式
--------
    python app.py
默认监听 127.0.0.1:5000，开发模式 debug=True
"""
import os
import sys
import time
import traceback
import threading
import uuid
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

# 确保能 import 项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from CT_main import load_and_filter_gan_data, prepare_gan_features, calculate_metrics

# 第三方机器学习库
import sklearn
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import (
    ExtraTreesRegressor, RandomForestRegressor, GradientBoostingRegressor,
    AdaBoostRegressor, BaggingRegressor, StackingRegressor, IsolationForest
)
from sklearn.linear_model import LinearRegression, Ridge, Lasso, BayesianRidge, HuberRegressor
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.neural_network import MLPRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.kernel_ridge import KernelRidge
# XGBoost 为可选依赖：未安装时回退到其他树模型
try:
    from xgboost import XGBRegressor
    _HAS_XGBOOST = True
except ImportError:
    _HAS_XGBOOST = False

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
# 格式: {"model": model, "X_test": X_test, "y_test": y_test, "y_pred": y_pred,
#        "feature_cols": [...], "model_name": "...", "timestamp": ...}
_LAST_TRAIN_CACHE = {"model": None, "timestamp": 0}


# ============================================================
# 数据源加载（支持实测 / GAN / 加权混合）
# ============================================================
def load_training_data(source: str = "real", gan_weight: float = 0.2):
    """根据数据源类型加载训练数据

    source:
        "real"   - 仅 149 条实测数据（训练+测试都从这里切分）
        "gan"    - 仅 GAN 数据（清洗后，训练+测试都从这里切分）
        "mix"    - 实测 + GAN 加权混合（训练+测试都从这里切分）
        "gan_train_real_test" - GAN 训练 + 实测测试（真实评估 GAN 价值）
        "mix_train_real_test" - 加权混合训练 + 实测测试
    gan_weight:
        GAN 样本权重（0~1），实测固定为 1.0。

    返回 (df, sample_weight) 或 (df, None)
    其中 df 包含所有数据（训练+测试），sample_weight 同理。
    调用方用 train_test_split 切分。
    """
    real_df = pd.read_excel(config.DATA_FILE_MIC)
    # 实测筛选
    s = real_df[config.composition_columns].sum(axis=1)
    real_mask = (s >= 85) & (s <= 115)
    real_valid = real_df[real_mask].copy()

    if source == "real":
        return real_valid, None

    if source == "gan":
        gan_df = pd.read_excel(config.GENERATED_DATA_PATH)
        gan_df = _clean_gan_data(gan_df)
        return gan_df, None

    if source == "mix":
        # 加权混合（训练+测试都从混合数据切分）
        gan_df = pd.read_excel(config.GENERATED_DATA_PATH)
        gan_df = _clean_gan_data(gan_df)
        real_w = np.ones(len(real_valid))
        gan_w = np.full(len(gan_df), gan_weight)
        weights = np.concatenate([real_w, gan_w])
        df = pd.concat([real_valid, gan_df], ignore_index=True)
        return df, weights

    if source in ("gan_train_real_test", "mix_train_real_test"):
        # GAN 训练（mix 时降权）+ 实测测试（真实评估 GAN 对实测的价值）
        gan_df = pd.read_excel(config.GENERATED_DATA_PATH)
        gan_df = _clean_gan_data(gan_df)
        if source == "gan_train_real_test":
            gan_w = np.ones(len(gan_df))           # GAN 权重 1.0
        else:  # mix_train_real_test
            gan_w = np.full(len(gan_df), gan_weight)  # GAN 降权
        real_w = np.full(len(real_valid), -1.0)  # -1 = 测试集标记
        weights = np.concatenate([gan_w, real_w])
        df = pd.concat([gan_df, real_valid], ignore_index=True)
        return df, weights

    return real_valid, None


def _clean_gan_data(gan_df: pd.DataFrame) -> pd.DataFrame:
    """清洗 GAN 数据：
    1. 删除 HV 缺失
    2. 删除成分总和超出 [85, 115]
    3. 删除 IsolationForest 检出的异常（cont=0.05）
    """
    df = gan_df.copy()

    # 1. HV 缺失
    df = df.dropna(subset=[TARGET_COL])

    # 2. 成分总和
    s = df[config.composition_columns].sum(axis=1)
    df = df[(s >= 85) & (s <= 115)].copy()

    # 3. IsolationForest 异常检测
    cols = config.composition_columns + [TARGET_COL]
    cols = [c for c in cols if c in df.columns]
    if len(df) > 100:
        iso = IsolationForest(contamination=0.05, random_state=config.RANDOM_STATE)
        labels = iso.fit_predict(df[cols])
        df = df[labels == 1].copy()

    return df


# ============================================================
# 特征筛选：删除无信息特征，缓解小样本过拟合
# ============================================================
def filter_features(X, feature_cols, y=None, mode="auto"):
    """根据模式筛选特征
    mode:
        "off"       - 不筛选
        "auto"      - 自动删除全 0 / 近零方差 / 非零样本<5 的特征
        "importance"- auto + 用 ExtraTrees 重要性保留 Top 30
    返回 (X_filtered, kept_cols, removed_cols)
    """
    if mode == "off":
        return X, feature_cols, []

    X = np.asarray(X, dtype=float)
    n_samples = X.shape[0]
    kept_mask = []
    removed = []

    for i, col in enumerate(feature_cols):
        col_vals = X[:, i]
        non_zero = np.sum(np.abs(col_vals) > 1e-6)
        std = col_vals.std()
        # 删除全 0 / 近零方差 / 非零样本<5
        if non_zero < 5 or std < 1e-4:
            removed.append(col)
            kept_mask.append(False)
        else:
            kept_mask.append(True)

    # importance 模式：用 ExtraTrees 选 Top 30
    if mode == "importance" and y is not None and sum(kept_mask) > 30:
        from sklearn.ensemble import ExtraTreesRegressor
        X_kept = X[:, kept_mask]
        kept_cols = [c for c, k in zip(feature_cols, kept_mask) if k]
        et = ExtraTreesRegressor(n_estimators=100, random_state=config.RANDOM_STATE)
        et.fit(X_kept, y)
        imp = et.feature_importances_
        top_n = 30
        top_idx = np.argsort(imp)[::-1][:top_n]
        new_mask = [False] * len(kept_cols)
        for i in top_idx:
            new_mask[i] = True
        new_removed = [c for c, k in zip(kept_cols, new_mask) if not k]
        removed.extend(new_removed)
        final_cols = [c for c, k in zip(kept_cols, new_mask) if k]
        final_X = X_kept[:, top_idx]
        return final_X, final_cols, removed

    kept_cols = [c for c, k in zip(feature_cols, kept_mask) if k]
    final_X = X[:, kept_mask]
    return final_X, kept_cols, removed


# ============================================================
# 模型工厂
# ============================================================
def build_model(name: str, params: dict = None):
    """根据算法名构造回归器，可接收超参数覆盖默认值

    params 支持的字段（按算法生效）：
      n_estimators   : int  - 树模型树数 (树模型)
      max_depth      : int  - 树最大深度 (树模型)
      alpha          : float- 正则强度 (Ridge/Lasso)
      C              : float- 正则强度倒数 (SVR)
      gamma          : str  - 核宽度 (SVR)
      hidden_layer_sizes : tuple - MLP 隐藏层结构
      max_iter       : int  - MLP 最大迭代
      learning_rate  : float- GBDT/AdaBoost 学习率
    """
    params = params or {}
    name = name.strip()

    def _p(key, default):
        """取参数，找不到用 default"""
        v = params.get(key, default)
        return v if v is not None else default

    if name == "LinearRegression":
        return LinearRegression()
    if name in ("Ridge", "Ridge / Lasso"):
        return Pipeline([("scaler", StandardScaler()),
                         ("model", Ridge(alpha=_p("alpha", 1.0)))])
    if name == "Lasso":
        return Pipeline([("scaler", StandardScaler()),
                         ("model", Lasso(alpha=_p("alpha", 1.0)))])
    if name == "BayesianRidge":
        return Pipeline([("scaler", StandardScaler()), ("model", BayesianRidge())])
    if name == "HuberRegressor":
        return Pipeline([("scaler", StandardScaler()), ("model", HuberRegressor())])
    if name == "PolynomialRegression":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("model", Ridge(alpha=_p("alpha", 1.0))),
        ])
    if name == "SVR (RBF)":
        return Pipeline([("scaler", StandardScaler()),
                         ("model", SVR(kernel="rbf", C=_p("C", 1.0), gamma=_p("gamma", "scale")))])
    if name == "SVR (Linear)":
        return Pipeline([("scaler", StandardScaler()),
                         ("model", SVR(kernel="linear", C=_p("C", 1.0)))])
    if name == "RandomForestRegressor":
        return RandomForestRegressor(
            n_estimators=int(_p("n_estimators", 200)),
            max_depth=_p("max_depth", None),
            random_state=config.RANDOM_STATE,
        )
    if name == "ExtraTreesRegressor":
        return ExtraTreesRegressor(
            n_estimators=int(_p("n_estimators", 200)),
            max_depth=_p("max_depth", None),
            random_state=config.RANDOM_STATE,
        )
    if name == "GradientBoostingRegressor":
        return GradientBoostingRegressor(
            n_estimators=int(_p("n_estimators", 200)),
            learning_rate=_p("learning_rate", 0.1),
            max_depth=_p("max_depth", 3),
            random_state=config.RANDOM_STATE,
        )
    if name == "AdaBoostRegressor":
        return AdaBoostRegressor(
            n_estimators=int(_p("n_estimators", 100)),
            learning_rate=_p("learning_rate", 1.0),
            random_state=config.RANDOM_STATE,
        )
    if name == "BaggingRegressor":
        return BaggingRegressor(
            n_estimators=int(_p("n_estimators", 50)),
            random_state=config.RANDOM_STATE,
        )
    if name == "MLPRegressor":
        hidden = _p("hidden_layer_sizes", (128, 64))
        if isinstance(hidden, str):
            # 前端可能传字符串 "128,64"
            try:
                hidden = tuple(int(x) for x in hidden.split(","))
            except Exception:
                hidden = (128, 64)
        return Pipeline([
            ("scaler", StandardScaler()),
            ("model", MLPRegressor(
                hidden_layer_sizes=hidden,
                max_iter=int(_p("max_iter", 500)),
                random_state=config.RANDOM_STATE,
            )),
        ])
    if name == "XGBoostRegressor":
        if not _HAS_XGBOOST:
            raise RuntimeError("XGBoost 未安装，请运行: pip install xgboost")
        return XGBRegressor(
            n_estimators=int(_p("n_estimators", 200)),
            learning_rate=_p("learning_rate", 0.1),
            max_depth=int(_p("max_depth", 6)),
            subsample=_p("subsample", 0.8),
            colsample_bytree=_p("colsample_bytree", 0.8),
            random_state=config.RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        )
    if name == "StackingRegressor":
        # Stacking 集成：ExtraTrees + GBDT + SVR → Ridge 作元学习器
        base_models = [
            ("et", ExtraTreesRegressor(
                n_estimators=int(_p("n_estimators", 200)),
                max_depth=_p("max_depth", None),
                random_state=config.RANDOM_STATE,
            )),
            ("gbdt", GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=3,
                random_state=config.RANDOM_STATE,
            )),
            ("svr", Pipeline([("scaler", StandardScaler()),
                              ("model", SVR(kernel="rbf", C=1.0))])),
        ]
        return StackingRegressor(
            estimators=base_models,
            final_estimator=Ridge(alpha=1.0),
            n_jobs=-1,
        )
    if name == "GaussianProcessRegressor":
        # 高斯过程回归 —— 小样本之王，天然带不确定性
        # 核函数：常数 × RBF + 白噪声（抗噪）
        kernel = ConstantKernel(_p("constant_value", 1.0)) * \
                 RBF(length_scale=_p("length_scale", 1.0)) + \
                 WhiteKernel(noise_level=_p("noise_level", 1.0))
        return Pipeline([
            ("scaler", StandardScaler()),
            ("model", GaussianProcessRegressor(
                kernel=kernel,
                alpha=_p("alpha", 1e-6),
                n_restarts_optimizer=_p("n_restarts", 3),
                random_state=config.RANDOM_STATE,
                normalize_y=True,
            )),
        ])
    if name == "KernelRidge":
        # 核岭回归 —— 适合非线性小样本
        gamma_val = _p("gamma", 0.001)
        if isinstance(gamma_val, str):
            try:
                gamma_val = float(gamma_val)
            except Exception:
                gamma_val = 0.001
        return Pipeline([
            ("scaler", StandardScaler()),
            ("model", KernelRidge(
                kernel=_p("kernel", "rbf"),
                alpha=_p("alpha", 1.0),
                gamma=gamma_val,
            )),
        ])
    # 默认
    return ExtraTreesRegressor(n_estimators=200, random_state=config.RANDOM_STATE)


# ============================================================
# 网格搜索参数空间（按算法返回候选超参数组合）
# ============================================================
GRID_SEARCH_SPACES = {
    "RandomForestRegressor": {
        "n_estimators": [100, 200, 400],
        "max_depth": [None, 8, 16],
    },
    "ExtraTreesRegressor": {
        "n_estimators": [100, 200, 400],
        "max_depth": [None, 8, 16],
    },
    "GradientBoostingRegressor": {
        "n_estimators": [100, 200, 400],
        "learning_rate": [0.05, 0.1, 0.2],
        "max_depth": [3, 5],
    },
    "AdaBoostRegressor": {
        "n_estimators": [50, 100, 200],
        "learning_rate": [0.5, 1.0, 2.0],
    },
    "SVR (RBF)": {
        "C": [0.5, 1.0, 5.0, 10.0],
        "gamma": ["scale", "auto"],
    },
    "Ridge": {"alpha": [0.1, 1.0, 10.0]},
    "Lasso": {"alpha": [0.01, 0.1, 1.0]},
    "MLPRegressor": {
        "hidden_layer_sizes": [(64,), (128, 64), (256, 128, 64)],
        "max_iter": [300, 500],
    },
    "XGBoostRegressor": {
        "n_estimators": [100, 200, 400],
        "learning_rate": [0.05, 0.1, 0.2],
        "max_depth": [3, 6, 9],
    },
    "StackingRegressor": {
        # Stacking 只调 ExtraTrees 的参数（基模型之一）
        "et__n_estimators": [100, 200, 400],
        "et__max_depth": [None, 8, 16],
    },
    "GaussianProcessRegressor": {
        "model__alpha": [1e-6, 1e-4, 1e-2],
        "model__n_restarts_optimizer": [0, 3],
    },
    "KernelRidge": {
        "model__alpha": [0.1, 1.0, 10.0],
        "model__kernel": ["rbf", "poly"],
        "model__gamma": [0.01, 0.1, 1.0],
    },
}


def get_grid_space(name: str):
    """根据算法名返回对应的网格搜索参数空间（自动加 model__ 前缀适配 Pipeline）"""
    name = name.strip()
    space = GRID_SEARCH_SPACES.get(name, {})
    # Pipeline 内的模型参数需要加 model__ 前缀
    needs_prefix = name in ("Ridge", "Lasso", "SVR (RBF)", "SVR (Linear)", "MLPRegressor", "PolynomialRegression")
    if needs_prefix:
        return {"model__" + k: v for k, v in space.items()}
    return space


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
# 数据源统计（让前端知道清洗后剩多少条 GAN 数据）
# ============================================================
@app.route("/api/data/source_stats")
def data_source_stats():
    """统计数据源条数：实测总数 / 实测有效 / GAN 原始 / GAN 清洗后 / 混合总数"""
    try:
        # 实测
        real_df = pd.read_excel(config.DATA_FILE_MIC)
        real_sum = real_df[config.composition_columns].sum(axis=1)
        real_valid = real_df[(real_sum >= 85) & (real_sum <= 115)]  # 成分总和在 85~115 之间为有效配方
        # GAN 原始
        gan_raw = pd.read_excel(config.GENERATED_DATA_PATH)
        # GAN 清洗后
        gan_clean = _clean_gan_data(gan_raw)

        return jsonify({
            "real_total": int(len(real_df)),
            "real_valid": int(len(real_valid)),
            "gan_total": int(len(gan_raw)),
            "gan_cleaned": int(len(gan_clean)),
            "gan_removed": int(len(gan_raw) - len(gan_clean)),
            "mix_default": int(len(real_valid) + len(gan_clean)),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 健康检查
# ============================================================
@app.route("/api/health")
def health():
    """健康检查：返回服务状态、数据文件路径与是否存在"""
    return jsonify({
        "status": "ok",
        "service": "FORGE Backend",
        "data_file": config.DATA_FILE_MIC,
        "exists": os.path.exists(config.DATA_FILE_MIC),
    })


# ============================================================
# 数据：列名
# ============================================================
@app.route("/api/data/columns")
def data_columns():
    """返回数据表的列结构：成分列、目标列、全部列名、行数"""
    try:
        df = pd.read_excel(config.DATA_FILE_MIC)
        return jsonify({
            "composition": config.composition_columns,
            "target": TARGET_COL,
            "all_columns": list(df.columns),
            "n_rows": len(df),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 数据：预览
# ============================================================
@app.route("/api/data/preview")
def data_preview():
    """数据预览：返回前 n 行（默认 10，最大 500）的 Image_Name + 成分 + 目标"""
    try:
        n = int(request.args.get("n", 10))
        n = max(1, min(n, 500))  # 限制 1~500 防止前端传超大值
        df = pd.read_excel(config.DATA_FILE_MIC)

        # 优先返回：序号 + 成分 + 目标（前端表格展示用）
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
# 数据：统计摘要（指标卡用）
# ============================================================
@app.route("/api/data/stats")
def data_stats():
    """统计摘要：返回样本数、元素数、HV 的 min/max/mean/std/median（指标卡用）"""
    try:
        df = pd.read_excel(config.DATA_FILE_MIC)
        y = df[TARGET_COL].dropna()
        return jsonify({
            "n_samples": int(len(df)),
            "n_elements": len(config.composition_columns),
            "hv_min": safe_float(y.min()),
            "hv_max": safe_float(y.max()),
            "hv_mean": safe_float(y.mean()),
            "hv_std": safe_float(y.std()),
            "hv_median": safe_float(y.median()),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 训练：传统回归模型（支持手动超参数 + 数据源选择）
# ============================================================
@app.route("/api/train/traditional", methods=["POST"])
def train_traditional():
    """传统回归模型训练入口

    请求体 JSON 字段：
      model           : str  算法名（如 ExtraTreesRegressor）
      test_size       : float 测试集比例，默认 config.TEST_SIZE，限制 0.05~0.5
      params          : dict  手动超参数，会覆盖默认值
      data_source     : str  数据源 real/gan/mix/gan_train_real_test/mix_train_real_test
      gan_weight      : float GAN 样本权重 0~1
      feature_filter  : str  特征筛选模式 off/auto/importance
      target_transform: str  目标变换 off/log

    返回：训练/测试指标、散点图数据、特征筛选结果、缓存训练结果以供导出
    """
    try:
        req = request.get_json() or {}
        model_name = req.get("model", "ExtraTreesRegressor")
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))  # 限制测试集比例范围
        params = req.get("params", {}) or {}
        data_source = req.get("data_source", "real")  # real / gan / mix
        gan_weight = float(req.get("gan_weight", 0.2))
        gan_weight = max(0.0, min(gan_weight, 1.0))  # GAN 权重范围 0~1

        # 清理 None 值
        params = {k: v for k, v in params.items() if v is not None and v != ""}

        # 增强选项：特征筛选 + 目标变换
        feature_filter = req.get("feature_filter", "off")  # off / auto / importance
        target_transform = req.get("target_transform", "off")  # off / log

        # 加载数据（支持多种数据源）
        df, sample_weight = load_training_data(data_source, gan_weight)
        X, y, feature_cols, target_col = prepare_gan_features(df)

        # 特征筛选
        removed_cols = []
        if feature_filter != "off":
            X, feature_cols, removed_cols = filter_features(X, feature_cols, y, feature_filter)

        # gan_train_real_test 模式：GAN 训练 + 实测测试（样本 weight=-1 标记实测）
        if data_source == "gan_train_real_test" and sample_weight is not None:
            train_mask = sample_weight > 0
            test_mask = sample_weight < 0
            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[test_mask], y[test_mask]
            sw_train = None  # 全是 GAN，无需加权
        elif data_source == "mix_train_real_test" and sample_weight is not None:
            # mix 训练（实测+GAN 加权）+ 实测测试
            # 实测样本 weight = -1（标记测试集），GAN 样本 weight = gan_weight
            train_mask = sample_weight > 0
            test_mask = sample_weight < 0
            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[test_mask], y[test_mask]
            sw_train = sample_weight[train_mask]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=config.RANDOM_STATE
            )
            if sample_weight is not None:
                sw_train, _ = train_test_split(
                    sample_weight, test_size=test_size, random_state=config.RANDOM_STATE
                )
            else:
                sw_train = None

        model = build_model(model_name, params)

        # 目标变换：log 变换让右偏分布更对称
        if target_transform == "log":
            y_train_orig = y_train
            y_test_orig = y_test
            y_train = np.log(np.maximum(y_train, 1))
            y_test = np.log(np.maximum(y_test, 1))
        else:
            y_train_orig = None
            y_test_orig = None

        if sw_train is not None and model_name in (
            "RandomForestRegressor", "ExtraTreesRegressor", "GradientBoostingRegressor",
            "AdaBoostRegressor", "BaggingRegressor", "Ridge", "Lasso",
            "Ridge / Lasso", "BayesianRidge", "HuberRegressor"
        ):
            # 仅对支持 sample_weight 的算法传入样本权重（混合数据源时 GAN 降权）
            try:
                if isinstance(model, Pipeline):
                    model.fit(X_train, y_train, model__sample_weight=sw_train)
                else:
                    model.fit(X_train, y_train, sample_weight=sw_train)
            except Exception:
                model.fit(X_train, y_train)
        else:
            model.fit(X_train, y_train)

        y_train_pred = model.predict(X_train)
        y_test_pred = model.predict(X_test)

        # 如果做了 log 变换，预测时还原
        if target_transform == "log":
            y_train = y_train_orig
            y_test = y_test_orig
            y_train_pred = np.exp(y_train_pred)
            y_test_pred = np.exp(y_test_pred)

        train_metrics = calculate_metrics(y_train, y_train_pred, "训练集")
        test_metrics = calculate_metrics(y_test, y_test_pred, "测试集")

        # 缓存训练结果，供导出端点使用
        import time as _time
        _LAST_TRAIN_CACHE.update({
            "model": model,
            "model_name": model_name,
            "X_test": X_test,
            "y_test": y_test,
            "y_test_pred": y_test_pred,
            "X_train": X_train,
            "y_train": y_train,
            "y_train_pred": y_train_pred,
            "feature_cols": feature_cols,
            "target_col": target_col,
            "params": params,
            "data_source": data_source,
            "test_size": test_size,
            "feature_filter": feature_filter,
            "target_transform": target_transform,
            "timestamp": _time.time(),
        })

        scatter = [
            {"x": safe_float(y_test[i]), "y": safe_float(y_test_pred[i])}
            for i in range(len(y_test))
        ]

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
            "feature_filter": feature_filter,
            "removed_features": removed_cols,
            "n_features_used": len(feature_cols),
            "target_transform": target_transform,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 训练结果导出：CSV（预测值 vs 实测值）
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
        # 拼接训练集 + 测试集的预测结果
        y_train = cache["y_train"]
        y_train_pred = cache["y_train_pred"]
        y_test = cache["y_test"]
        y_test_pred = cache["y_test_pred"]

        df_out = pd.DataFrame({
            "split": ["train"] * len(y_train) + ["test"] * len(y_test),
            "y_actual": list(y_train) + list(y_test),
            "y_pred": list(y_train_pred) + list(y_test_pred),
            "residual": list(np.array(y_train) - np.array(y_train_pred))
                       + list(np.array(y_test) - np.array(y_test_pred)),
        })

        # 加上特征列（如果 X_test 有列名）
        try:
            X_train_df = pd.DataFrame(cache["X_train"], columns=cache["feature_cols"])
            X_test_df = pd.DataFrame(cache["X_test"], columns=cache["feature_cols"])
            X_all = pd.concat([X_train_df, X_test_df], ignore_index=True)
            df_out = pd.concat([df_out, X_all], axis=1)
        except Exception:
            pass

        # 元信息
        df_out.attrs["model"] = cache["model_name"]
        df_out.attrs["params"] = cache.get("params", {})
        df_out.attrs["data_source"] = cache.get("data_source", "real")
        df_out.attrs["test_size"] = cache.get("test_size", 0.2)

        buf = io.BytesIO()
        buf.write(f"# model={cache['model_name']}, source={cache.get('data_source','real')}, "
                  f"test_size={cache.get('test_size',0.2)}\n".encode("utf-8"))
        df_out.to_csv(buf, index=False, encoding="utf-8-sig")
        buf.seek(0)

        return send_file(
            buf,
            as_attachment=True,
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
    import joblib
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
            "test_size": cache.get("test_size", 0.2),
            "timestamp": cache["timestamp"],
            "sklearn_version": sklearn.__version__,
        }

        buf = io.BytesIO()
        joblib.dump(bundle, buf)
        buf.seek(0)

        return send_file(
            buf,
            as_attachment=True,
            download_name=f"model_{cache['model_name']}_{int(cache['timestamp'])}.pkl",
            mimetype="application/octet-stream"
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 训练：自动超参数搜索（GridSearchCV + 数据源选择）
# ============================================================
@app.route("/api/train/grid_search", methods=["POST"])
def train_grid_search():
    """网格搜索超参优化（GridSearchCV + 数据源选择）

    请求体 JSON 字段：
      model       : str  算法名
      test_size   : float 测试集比例
      cv_folds    : int  交叉验证折数（2~10）
      data_source : str  数据源
      gan_weight  : float GAN 权重

    返回：最优参数、CV R²、训练/测试指标、Top 20 候选组合
    """
    try:
        from sklearn.model_selection import GridSearchCV
        req = request.get_json() or {}
        model_name = req.get("model", "ExtraTreesRegressor")
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))
        cv_folds = int(req.get("cv_folds", 5))
        cv_folds = max(2, min(cv_folds, 10))
        data_source = req.get("data_source", "real")
        gan_weight = float(req.get("gan_weight", 0.2))
        gan_weight = max(0.0, min(gan_weight, 1.0))

        df, sample_weight = load_training_data(data_source, gan_weight)
        X, y, feature_cols, target_col = prepare_gan_features(df)

        # gan_train_real_test / mix_train_real_test 模式：特殊切分（与 train_traditional 一致）
        if data_source == "gan_train_real_test" and sample_weight is not None:
            train_mask = sample_weight > 0
            test_mask = sample_weight < 0
            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[test_mask], y[test_mask]
            sw_train = None  # 全是 GAN，无需加权
        elif data_source == "mix_train_real_test" and sample_weight is not None:
            train_mask = sample_weight > 0
            test_mask = sample_weight < 0
            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[test_mask], y[test_mask]
            sw_train = sample_weight[train_mask]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=config.RANDOM_STATE
            )
            if sample_weight is not None:
                sw_train, _ = train_test_split(
                    sample_weight, test_size=test_size, random_state=config.RANDOM_STATE
                )
            else:
                sw_train = None

        base_model = build_model(model_name)
        param_grid = get_grid_space(model_name)

        if not param_grid:
            return jsonify({"error": f"算法 {model_name} 暂未配置网格搜索参数空间，请手动调参"}), 400

        gs = GridSearchCV(
            base_model, param_grid, cv=cv_folds,
            scoring="r2", n_jobs=-1, refit=True,
        )
        # GridSearchCV 的 fit 支持 sample_weight（通过 fit_params）
        if sw_train is not None and model_name in (
            "RandomForestRegressor", "ExtraTreesRegressor", "GradientBoostingRegressor",
            "AdaBoostRegressor", "BaggingRegressor", "Ridge", "Lasso",
            "Ridge / Lasso", "BayesianRidge", "HuberRegressor"
        ):
            try:
                if isinstance(base_model, Pipeline):
                    gs.fit(X_train, y_train, model__sample_weight=sw_train)
                else:
                    gs.fit(X_train, y_train, sample_weight=sw_train)
            except Exception:
                gs.fit(X_train, y_train)
        else:
            gs.fit(X_train, y_train)

        best_model = gs.best_estimator_
        y_train_pred = best_model.predict(X_train)
        y_test_pred = best_model.predict(X_test)

        train_metrics = calculate_metrics(y_train, y_train_pred, "训练集")
        test_metrics = calculate_metrics(y_test, y_test_pred, "测试集")

        # 缓存训练结果，供导出端点使用
        import time as _time
        _LAST_TRAIN_CACHE.update({
            "model": best_model,
            "model_name": model_name,
            "X_test": X_test,
            "y_test": y_test,
            "y_test_pred": y_test_pred,
            "X_train": X_train,
            "y_train": y_train,
            "y_train_pred": y_train_pred,
            "feature_cols": feature_cols,
            "target_col": target_col,
            "params": dict(gs.best_params_),
            "data_source": data_source,
            "test_size": test_size,
            "timestamp": _time.time(),
        })

        scatter = [
            {"x": safe_float(y_test[i]), "y": safe_float(y_test_pred[i])}
            for i in range(len(y_test))
        ]

        cv_results = gs.cv_results_
        candidates = []
        for i in range(len(cv_results["mean_test_score"])):
            params_i = cv_results["params"][i]
            clean_params = {k.replace("model__", ""): v for k, v in params_i.items()}
            candidates.append({
                "params": clean_params,
                "mean_r2": safe_float(cv_results["mean_test_score"][i]),
                "std_r2": safe_float(cv_results["std_test_score"][i]),
                "mean_fit_time": safe_float(cv_results["mean_fit_time"][i]),
            })
        candidates.sort(key=lambda x: x["mean_r2"], reverse=True)

        best_params_clean = {k.replace("model__", ""): v for k, v in gs.best_params_.items()}

        return jsonify({
            "model": model_name,
            "best_params": best_params_clean,
            "best_cv_r2": safe_float(gs.best_score_),
            "cv_folds": cv_folds,
            "data_source": data_source,
            "n_candidates": len(candidates),
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "test_size": test_size,
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "scatter": scatter,
            "candidates": candidates[:20],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 训练：多模型横向比较
# ============================================================
@app.route("/api/train/compare", methods=["POST"])
def train_compare():
    """多模型横向比较：在统一数据划分上跑多个模型 + K 折交叉验证

    请求体 JSON 字段：
      models           : list[str] 待比较的算法名列表
      test_size        : float 测试集比例
      cv_folds         : int   交叉验证折数
      feature_filter   : str   特征筛选模式
      target_transform : str   目标变换

    返回：每个模型的 R²/RMSE/MAE/MAPE、CV 均值/方差、训练耗时，并标注最优模型
    """
    try:
        from sklearn.model_selection import cross_val_score
        req = request.get_json() or {}
        models = req.get("models", [
            "ExtraTreesRegressor", "RandomForestRegressor",
            "GradientBoostingRegressor", "LinearRegression", "SVR (RBF)"
        ])
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))
        cv_folds = int(req.get("cv_folds", 5))
        cv_folds = max(2, min(cv_folds, 10))

        # 增强选项
        feature_filter = req.get("feature_filter", "off")
        target_transform = req.get("target_transform", "off")

        df = load_and_filter_gan_data()
        X, y, feature_cols, target_col = prepare_gan_features(df)

        # 特征筛选
        removed_cols = []
        if feature_filter != "off":
            X, feature_cols, removed_cols = filter_features(X, feature_cols, y, feature_filter)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=config.RANDOM_STATE
        )

        results = []
        import time
        for name in models:
            t0 = time.time()
            try:
                m = build_model(name)
                # 1) 测试集评估（默认参数训练一次）
                # 目标变换：log 在训练空间做，预测后 exp 还原，再用原始 y 算指标
                if target_transform == "log":
                    y_train_t = np.log(np.maximum(y_train, 1))
                else:
                    y_train_t = y_train
                m.fit(X_train, y_train_t)
                y_pred = m.predict(X_test)
                if target_transform == "log":
                    y_pred = np.exp(y_pred)
                mt = calculate_metrics(y_test, y_pred, "测试集")
                # 2) K 折交叉验证（在训练集上做，返回 K 个 R²；CV 用原始 y，不做 log 变换）
                cv_scores = cross_val_score(
                    build_model(name), X_train, y_train,
                    cv=cv_folds, scoring="r2", n_jobs=-1,
                )
                cv_r2_mean = float(np.mean(cv_scores))
                cv_r2_std = float(np.std(cv_scores))
                results.append({
                    "model": name,
                    "r2": safe_float(mt["R2_value"]),
                    "rmse": safe_float(mt["RMSE_value"]),
                    "mae": safe_float(mt["MAE_value"]),
                    "mape": safe_float(mt["MAPE_value"]),
                    "cv_r2_mean": cv_r2_mean,
                    "cv_r2_std": cv_r2_std,
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

        # 找最优（按测试集 R²）
        valid = [r for r in results if r["r2"] is not None]
        best = max(valid, key=lambda r: r["r2"])["model"] if valid else None

        return jsonify({
            "models": results,
            "best": best,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
            "cv_folds": cv_folds,
            "feature_filter": feature_filter,
            "removed_features": removed_cols,
            "n_features_used": len(feature_cols),
            "target_transform": target_transform,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 异常值检测
# ============================================================
@app.route("/api/outliers/detect", methods=["POST"])
def outliers_detect():
    """异常值检测：支持 isolation_forest / iqr / zscore 三种方法

    请求体 JSON 字段：
      method       : str  检测方法（isolation_forest / iqr / zscore）
      contamination: float 异常比例（仅 isolation_forest 用，默认 0.05）

    返回：异常值索引、各列取值、Top 50 异常样本
    """
    try:
        from sklearn.ensemble import IsolationForest
        req = request.get_json() or {}
        method = req.get("method", "isolation_forest")
        contamination = float(req.get("contamination", 0.05))

        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = config.composition_columns + [TARGET_COL]
        cols = [c for c in cols if c in df.columns]
        data = df[cols].dropna()

        if method == "isolation_forest":
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
            return jsonify({"error": "未知方法"}), 400

        outlier_idx = np.where(is_outlier)[0].tolist()
        samples = []
        for i in outlier_idx:
            row = data.iloc[i]
            samples.append({
                "index": int(data.index[i]),
                "values": {c: safe_float(row[c]) for c in cols},
            })

        return jsonify({
            "method": method,
            "total": len(data),
            "n_outliers": len(outlier_idx),
            "outliers": samples[:50],
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 重复值检测
# ============================================================
@app.route("/api/duplicates/detect")
def duplicates_detect():
    """重复值检测：按成分列去重，结合 Image_Name 后缀识别独立实验

    返回：成分重复的样本、独立实验组数（同成分但 Image_Name 不同）、真重复组数
    （Image_Name 也相同，需处理）
    """
    try:
        import re
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = [c for c in config.composition_columns if c in df.columns]
        dups = df.duplicated(subset=cols, keep=False)

        # 解析 Image_Name 后缀含义：
        # - 纯数字（-12, -600, -1000）= 测试温度
        # - cast/age/solution/anneal = 热处理工艺
        # - air-cooling/furnace-cooling/oil-quenching = 冷却方式
        # 只要有不同后缀，就认为是独立实验，不是重复
        def parse_suffix(name):
            if not isinstance(name, str): return None
            m = re.search(r'-(\w+(?:-\w+)?)$', name)
            return m.group(1) if m else None

        df['_suffix'] = df['Image_Name'].apply(parse_suffix) if 'Image_Name' in df.columns else None

        dup_df = df[dups][["Image_Name"] + cols + [TARGET_COL]] if "Image_Name" in df.columns else df[dups][cols + [TARGET_COL]]

        # 分析重复组：只要 Image_Name 不同 = 独立实验（温度/热处理/冷却方式）
        # 仅当 Image_Name 完全相同才算是真重复
        dup_groups = df[dups].groupby(cols, dropna=False)
        variant_groups = 0    # 独立实验组数（不同后缀）
        real_dup_groups = 0   # 真重复组数（Image_Name 完全相同）
        real_dup_count = 0    # 真重复样本数
        for _, grp in dup_groups:
            names = grp['Image_Name'].dropna().unique() if 'Image_Name' in grp.columns else []
            if len(names) > 1:
                # 同成分但 Image_Name 不同 = 独立实验
                variant_groups += 1
            else:
                # Image_Name 也相同 = 真重复（需处理）
                real_dup_groups += 1
                real_dup_count += len(grp)

        return jsonify({
            "total": len(df),
            "n_duplicates": int(dups.sum()),
            "n_unique_compositions": int(df[~dups].shape[0] + df[dups].groupby(cols, dropna=False).ngroups),
            "columns": list(dup_df.columns),
            "rows": dup_df.head(50).values.tolist(),
            "temp_exp_groups": variant_groups,   # 兼容前端字段名，含义为"独立实验组"
            "real_dup_groups": real_dup_groups,
            "real_dup_count": real_dup_count,
            "has_temp_info": bool(df['_suffix'].notna().any()),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 特征相关性
# ============================================================
@app.route("/api/correlation/matrix")
def correlation_matrix():
    """返回成分列的相关性矩阵（pearson / spearman / kendall），并标注高相关列对"""
    try:
        method = request.args.get("method", "pearson")
        df = pd.read_excel(config.DATA_FILE_MIC)
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
    """从相关性矩阵中筛选 |r| >= threshold 的高相关列对，按相关性强度排序"""
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = float(corr.iloc[i, j])
            if abs(r) >= threshold:
                pairs.append({"a": cols[i], "b": cols[j], "r": round(r, 3)})
    return sorted(pairs, key=lambda x: abs(x["r"]), reverse=True)


# ============================================================
# 特征筛选与降维 (PCA)
# ============================================================
@app.route("/api/features/pca")
def features_pca():
    """PCA 主成分分析：标准化后做 PCA，返回各主成分方差解释比例与 Top 3 载荷元素"""
    try:
        n_components = int(request.args.get("n", 10))
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = [c for c in config.composition_columns if c in df.columns]
        cols_arr = np.array(cols)
        X = df[cols].dropna().values
        # 标准化：消除元素量级差异（Ni 50% vs S 0.0001%）
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        pca = PCA(n_components=min(n_components, len(cols)))
        pca.fit(X_scaled)
        return jsonify({
            "n_components": pca.n_components_,
            "explained_variance": pca.explained_variance_ratio_.tolist(),
            "cumulative": np.cumsum(pca.explained_variance_ratio_).tolist(),
            "components": [cols_arr[np.argsort(-np.abs(c))[:3]].tolist() for c in pca.components_],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 特征重要性
# ============================================================
@app.route("/api/features/importance")
def features_importance():
    """特征重要性：用 ExtraTrees 拟合成分→HV，返回各特征重要性排序与 Top 5"""
    try:
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = [c for c in config.composition_columns if c in df.columns]
        X = df[cols].dropna().values
        y = df.loc[df[cols].dropna().index, TARGET_COL].values
        model = ExtraTreesRegressor(n_estimators=200, random_state=config.RANDOM_STATE)
        model.fit(X, y)
        imp = model.feature_importances_
        order = np.argsort(-imp)
        return jsonify({
            "features": [cols[i] for i in order],
            "importances": [safe_float(imp[i]) for i in order],
            "top5": [cols[i] for i in order[:5]],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 缺失值统计
# ============================================================
@app.route("/api/missing/stats")
def missing_stats():
    """缺失值统计：返回每列缺失数、缺失率（默认只返回有缺失或目标列）"""
    try:
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = ["Image_Name"] + config.composition_columns + [TARGET_COL]
        cols = [c for c in cols if c in df.columns]
        sub = df[cols]
        missing = sub.isnull().sum()
        result = []
        for c in cols:
            n_miss = int(missing[c])
            if n_miss > 0 or c == TARGET_COL:
                result.append({
                    "column": c,
                    "missing": n_miss,
                    "total": len(df),
                    "ratio": round(n_miss / len(df) * 100, 1),
                })
        return jsonify({
            "total_rows": len(df),
            "total_missing": int(sub.isnull().sum().sum()),
            "columns": result,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/missing/fill", methods=["POST"])
def missing_fill():
    """缺失值填充：支持 median / mean / knn / drop 四种策略

    返回：填充前后的缺失数、剩余行数
    """
    try:
        req = request.get_json() or {}
        strategy = req.get("strategy", "median")
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = [c for c in config.composition_columns if c in df.columns]
        before = int(df[cols + [TARGET_COL]].isnull().sum().sum())
        if strategy == "median":
            df[cols + [TARGET_COL]] = df[cols + [TARGET_COL]].fillna(df[cols + [TARGET_COL]].median())
        elif strategy == "mean":
            df[cols + [TARGET_COL]] = df[cols + [TARGET_COL]].fillna(df[cols + [TARGET_COL]].mean())
        elif strategy == "knn":
            from sklearn.impute import KNNImputer
            imp = KNNImputer(n_neighbors=5)
            df[cols + [TARGET_COL]] = imp.fit_transform(df[cols + [TARGET_COL]])
        elif strategy == "drop":
            df = df.dropna(subset=cols + [TARGET_COL])
        after = int(df[cols + [TARGET_COL]].isnull().sum().sum())
        return jsonify({
            "strategy": strategy,
            "before": before,
            "after": after,
            "rows_remaining": len(df),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 聚类分析
# ============================================================
@app.route("/api/clustering/kmeans", methods=["POST"])
def clustering_kmeans():
    """KMeans 聚类：对成分数据聚类后用 PCA 降到 2 维返回散点

    请求体 JSON 字段：
      n_clusters : int  簇数（默认 4）
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        req = request.get_json() or {}
        n_clusters = int(req.get("n_clusters", 4))
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = [c for c in config.composition_columns if c in df.columns]
        X = df[cols].dropna().values
        km = KMeans(n_clusters=n_clusters, random_state=config.RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X)
        pca = PCA(n_components=2)
        proj = pca.fit_transform(X)
        return jsonify({
            "n_clusters": n_clusters,
            "labels": labels.tolist(),
            "pca_x": proj[:, 0].tolist(),
            "pca_y": proj[:, 1].tolist(),
            "hv": df.loc[df[cols].dropna().index, TARGET_COL].round(1).tolist(),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 数据库查询（模拟）
# ============================================================
@app.route("/api/database/query", methods=["POST"])
def database_query():
    """可视化查询构建器后端
    接收结构化参数（不再让前端写 SQL 字符串）：
      columns   : list[str]  查询列，空表示全部
      filters   : list[{col, op, val}]  筛选条件（AND 连接）
                    op: > < >= <= = != between contains
      order_by  : {col, desc:bool}  排序
      limit     : int  返回行数上限（默认 100，最大 1000）
      aggregate : {func, col, group_by}  聚合查询
                    func: count avg min max sum
    """
    try:
        req = request.get_json() or {}
        df = pd.read_excel(config.DATA_FILE_MIC)

        # ---------- 聚合模式 ----------
        agg = req.get("aggregate")
        if agg and agg.get("func"):
            func_map = {"count": "count", "avg": "mean", "min": "min",
                        "max": "max", "sum": "sum"}
            func = func_map.get(agg["func"].lower(), agg["func"].lower())
            group_by = agg.get("group_by") or []
            col = agg.get("col")
            # 分组聚合
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
                # 全表聚合（单行结果）
                if func == "count":
                    val = int(len(df))
                    res = pd.DataFrame({"count": [val]})
                else:
                    if not col or col not in df.columns:
                        return jsonify({"error": f"聚合列 {col} 不存在"}), 400
                    val = float(df[col].agg(func))
                    res = pd.DataFrame({f"{func}_{col}": [val]})
            res = res.head(int(req.get("limit", 100)))
            return jsonify({
                "columns": list(res.columns),
                "rows": res.values.tolist(),
                "n": int(len(res)),
            })

        # ---------- 普通查询 ----------
        # 筛选
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
        # 排序
        ob = req.get("order_by")
        if ob and ob.get("col") and ob["col"] in df.columns:
            df = df.sort_values(ob["col"], ascending=not ob.get("desc", False))
        # 选列
        cols = req.get("columns") or []
        cols = [c for c in cols if c in df.columns]
        if cols:
            df = df[cols]
        # limit
        n = int(req.get("limit", 100))
        n = max(1, min(n, 1000))
        df = df.head(n)
        return jsonify({
            "columns": list(df.columns),
            "rows": df.values.tolist(),
            "n": int(len(df)),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/database/schema")
def database_schema():
    """返回数据表的列结构，供前端构建器渲染下拉选项"""
    try:
        df = pd.read_excel(config.DATA_FILE_MIC)
        cols = []
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                kind = "number"
            else:
                kind = "text"
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
# 主动学习 / 单目标优化
# ============================================================
# 缓存最后一次推荐结果，供导出使用
_LAST_ACTIVE_CACHE = {"recommendations": None, "timestamp": 0}


@app.route("/api/active/optimize", methods=["POST"])
def active_optimize():
    """主动学习：训练代理模型 → 生成设计空间 → acquisition 筛选推荐样本
    请求参数：
      model_name    : str  代理模型（默认 ExtraTreesRegressor）
      n_candidates  : int  设计空间大小（默认 5000，最大 20000）
      n_recommend   : int  推荐数量（默认 8）
      strategy      : str  采样策略 greedy/ei/ucb/thompson/bayes
      explore_ratio : float 探索/利用平衡（0~1，默认 0.5）
      cv_folds      : int  交叉验证折数（默认 5）
    """
    try:
        from sklearn.model_selection import cross_val_score
        req = request.get_json() or {}
        model_name = req.get("model_name", "ExtraTreesRegressor")
        n_candidates = int(req.get("n_candidates", 5000))
        n_candidates = max(100, min(n_candidates, 20000))
        n_recommend = int(req.get("n_recommend", 8))
        n_recommend = max(1, min(n_recommend, 50))
        strategy = req.get("strategy", "ei")
        explore_ratio = float(req.get("explore_ratio", 0.5))
        explore_ratio = max(0.0, min(explore_ratio, 1.0))
        cv_folds = int(req.get("cv_folds", 5))
        cv_folds = max(2, min(cv_folds, 10))

        # 1. 加载实测数据
        df = load_and_filter_gan_data()
        X, y, feature_cols, target_col = prepare_gan_features(df)

        # 2. 训练代理模型
        model = build_model(model_name)
        model.fit(X, y)

        # 2b. 交叉验证评估代理模型
        cv_scores = cross_val_score(
            build_model(model_name), X, y,
            cv=cv_folds, scoring="r2", n_jobs=-1,
        )
        cv_r2_mean = float(np.mean(cv_scores))
        cv_r2_std = float(np.std(cv_scores))

        # 3. 生成虚拟设计空间（仅对成分列 LHS 采样，Micro 列用实测均值填充）
        rng = np.random.RandomState(config.RANDOM_STATE)
        micro_cols = [f"Micro_{i + 1}" for i in range(70)]
        comp_indices = [i for i, c in enumerate(feature_cols) if c not in micro_cols]
        micro_indices = [i for i, c in enumerate(feature_cols) if c in micro_cols]
        n_comp = len(comp_indices)
        # 成分范围：实测 min/max，留 5% 余地
        X_comp = X[:, comp_indices]
        mins = X_comp.min(axis=0).astype(float)
        maxs = X_comp.max(axis=0).astype(float)
        span = maxs - mins
        mins = np.maximum(mins - span * 0.05, 0)
        maxs = maxs + span * 0.05
        # 拉丁超立方采样
        lhs = rng.uniform(size=(n_candidates, n_comp))
        for j in range(n_comp):
            order = rng.permutation(n_candidates)
            lhs[:, j] = (lhs[:, j] + order) / n_candidates
        comp_candidates = lhs * (maxs - mins) + mins
        # 归一化：让每个候选配方的成分总和接近 100%（按实测平均总和缩放）
        real_sums = X_comp.sum(axis=1)
        target_sum = float(np.median(real_sums))  # 用中位数作为目标总和
        comp_sums = comp_candidates.sum(axis=1, keepdims=True)
        comp_sums = np.maximum(comp_sums, 1e-9)
        comp_candidates = comp_candidates * (target_sum / comp_sums)
        # 拼接：Micro 列用实测均值填充
        candidates = np.zeros((n_candidates, len(feature_cols)))
        candidates[:, comp_indices] = comp_candidates
        if micro_indices:
            micro_mean = X[:, micro_indices].mean(axis=0)
            candidates[:, micro_indices] = micro_mean

        # 4. 代理模型预测设计空间
        preds = model.predict(candidates)
        # 不确定性：用 ExtraTrees/RF 的树间标准差
        uncertainties = np.zeros(n_candidates)
        if hasattr(model, "estimators_") and hasattr(model, "n_estimators"):
            # 树模型：每棵树单独预测，算标准差
            tree_preds = np.array([t.predict(candidates) for t in model.estimators_])
            uncertainties = tree_preds.std(axis=0)
        else:
            # 非树模型：用预测值距离均值的程度近似
            mean_pred = preds.mean()
            uncertainties = np.abs(preds - mean_pred)

        # 5. Acquisition Function 打分
        y_best = float(np.max(y))  # 已测数据中最高 HV
        sigma = uncertainties + 1e-9  # 防 0
        if strategy == "greedy":
            scores = preds
        elif strategy == "ucb":
            kappa = 2.0 * (0.3 + explore_ratio)  # κ 越大越爱探索
            scores = preds + kappa * sigma
        elif strategy == "thompson":
            scores = preds + rng.normal(0, 1, n_candidates) * sigma
        elif strategy == "bayes":
            # 综合 EI + UCB
            ei = _expected_improvement(preds, sigma, y_best)
            ucb = preds + 2.0 * (0.3 + explore_ratio) * sigma
            # 归一化后加权
            ei_n = (ei - ei.min()) / (ei.max() - ei.min() + 1e-9)
            ucb_n = (ucb - ucb.min()) / (ucb.max() - ucb.min() + 1e-9)
            scores = (1 - explore_ratio) * ei_n + explore_ratio * ucb_n
        else:  # ei（默认）
            scores = _expected_improvement(preds, sigma, y_best)

        # 6. 选 top N
        top_idx = np.argsort(scores)[::-1][:n_recommend]
        recommendations = []
        for rank, idx in enumerate(top_idx, 1):
            comp = {}
            for j, col in enumerate(feature_cols):
                comp[col] = round(float(candidates[idx, j]), 4)
            recommendations.append({
                "rank": rank,
                "predicted_hv": round(float(preds[idx]), 2),
                "uncertainty": round(float(uncertainties[idx]), 2),
                "score": round(float(scores[idx]), 4),
                "composition": comp,
            })

        # 7. 缓存结果（供导出用）
        import time as _time
        _LAST_ACTIVE_CACHE.update({
            "recommendations": recommendations,
            "model_name": model_name,
            "strategy": strategy,
            "feature_cols": feature_cols,
            "timestamp": _time.time(),
        })

        return jsonify({
            "recommendations": recommendations,
            "meta": {
                "model_name": model_name,
                "strategy": strategy,
                "n_candidates": n_candidates,
                "n_recommend": n_recommend,
                "cv_r2_mean": cv_r2_mean,
                "cv_r2_std": cv_r2_std,
                "y_best": y_best,
                "n_train": int(len(y)),
                "feature_cols": feature_cols,
            },
            # 散点图数据（预测 HV vs 不确定性 σ），采样 500 点避免前端卡顿
            "scatter": _sample_scatter(preds, uncertainties, scores, top_idx, 500),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _expected_improvement(preds, sigma, y_best, xi=0.01):
    """EI 期望改进"""
    from scipy.stats import norm
    if sigma.max() == 0:
        return np.zeros_like(preds)
    with np.errstate(divide="ignore"):
        Z = (preds - y_best - xi) / sigma
        ei = (preds - y_best - xi) * norm.cdf(Z) + sigma * norm.pdf(Z)
        ei[sigma == 0] = 0
    # 负值置 0
    ei = np.maximum(ei, 0)
    return ei


def _sample_scatter(preds, uncertainties, scores, top_idx, n=500):
    """从设计空间均匀采样 n 个点用于前端散点图，确保推荐点包含在内"""
    total = len(preds)
    if total <= n:
        idx = np.arange(total)
    else:
        # 分层采样：先包含推荐点，剩余随机
        top_set = set(top_idx.tolist())
        remain = [i for i in range(total) if i not in top_set]
        rng = np.random.RandomState(42)
        sample_idx = rng.choice(remain, size=n - len(top_set), replace=False)
        idx = np.concatenate([list(top_set), sample_idx])
    pts = []
    for i in idx:
        pts.append({
            "pred": round(float(preds[i]), 2),
            "sigma": round(float(uncertainties[i]), 2),
            "score": round(float(scores[i]), 4),
            "recommended": int(i) in set(top_idx.tolist()),
        })
    return pts


@app.route("/api/active/export_csv")
def active_export_csv():
    """导出最后一次推荐的样本为 CSV"""
    try:
        import io
        from flask import send_file
        recs = _LAST_ACTIVE_CACHE.get("recommendations")
        if not recs:
            return jsonify({"error": "没有可导出的推荐结果，请先运行优化"}), 400
        feature_cols = _LAST_ACTIVE_CACHE.get("feature_cols", [])
        # 构造 DataFrame
        rows = []
        for r in recs:
            row = {
                "rank": r["rank"],
                "predicted_HV": r["predicted_hv"],
                "uncertainty_sigma": r["uncertainty"],
                "acquisition_score": r["score"],
            }
            for col in feature_cols:
                row[col] = r["composition"].get(col, 0)
            rows.append(row)
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        buf.seek(0)
        return send_file(
            buf,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"recommended_samples_{int(_LAST_ACTIVE_CACHE.get('timestamp', 0))}.csv",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 系统状态（代码优化页用）
# ============================================================
@app.route("/api/system/info")
def system_info():
    """系统状态：CPU/内存使用率、Python 版本、torch/CUDA 信息"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        # torch 为可选依赖，未安装时 torch_info 返回 available=False
        try:
            import torch
            torch_info = {
                "available": True,
                "torch_version": torch.__version__,
                "cuda_available": bool(torch.cuda.is_available()),
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "gpu_memory_total": safe_float(torch.cuda.get_device_properties(0).total_memory / 1024**3) if torch.cuda.is_available() else None,
            }
        except ImportError:
            torch_info = {"available": False}
        info = {
            "cpu_percent": safe_float(psutil.cpu_percent(interval=None)),
            "cpu_count": psutil.cpu_count(),
            "mem_total": safe_float(mem.total / 1024**3),
            "mem_used": safe_float(mem.used / 1024**3),
            "mem_percent": safe_float(mem.percent),
            "python_version": sys.version.split()[0],
            "torch": torch_info,
        }
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/system/recommend")
def system_recommend():
    """根据系统硬件 + 数据集规模，推荐当前项目的训练参数"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_count = psutil.cpu_count()
        mem_total_gb = mem.total / 1024**3
        mem_avail_gb = mem.available / 1024**3

        # 数据集规模
        df = pd.read_excel(config.DATA_FILE_MIC)
        n_samples = len(df)
        n_features = len(config.composition_columns) + 70  # 22 成分 + 70 微结构

        recs = []

        # 1. 单一模型树数
        if n_samples < 200:
            recs.append({"p": "ExtraTrees n_estimators", "v": 200,
                         "why": f"样本 {n_samples} 条偏少，200 棵树足够，过多过拟合"})
        else:
            recs.append({"p": "ExtraTrees n_estimators", "v": 400,
                         "why": f"样本 {n_samples} 条，可上调至 400 提升稳定性"})

        # 2. 网格搜索
        recs.append({"p": "GridSearchCV cv", "v": 5,
                     "why": f"{n_samples} 样本 · 5 折每折 {n_samples//5} 条，平衡稳定性与速度"})

        # 3. 测试集比例
        recs.append({"p": "test_size", "v": 0.2,
                     "why": f"测试集 {int(n_samples*0.2)} 条 · 训练集 {int(n_samples*0.8)} 条"})

        # 4. 主动学习设计空间
        if mem_avail_gb > 8:
            recs.append({"p": "设计空间大小", "v": "10000~20000",
                         "why": f"可用内存 {mem_avail_gb:.1f} GB 充足，可生成大设计空间"})
        elif mem_avail_gb > 4:
            recs.append({"p": "设计空间大小", "v": "5000~10000",
                         "why": f"可用内存 {mem_avail_gb:.1f} GB 适中"})
        else:
            recs.append({"p": "设计空间大小", "v": "2000~5000",
                         "why": f"可用内存 {mem_avail_gb:.1f} GB 偏低，减小设计空间"})

        # 5. 主动学习推荐数量
        recs.append({"p": "主动学习推荐数", "v": 8,
                     "why": "单轮 8 个配方 · 实验成本与模型提升的平衡点"})

        # 6. 主动学习策略
        recs.append({"p": "采样策略", "v": "EI（期望改进）",
                     "why": "小样本场景下 EI 最稳定 · 自动平衡探索/利用"})

        # 7. n_jobs
        recs.append({"p": "n_jobs", "v": -1,
                     "why": f"使用全部 {cpu_count} 核并行加速训练"})

        # 8. 是否启用 GAN
        try:
            import torch
            if torch.cuda.is_available():
                gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
                recs.append({"p": "GAN 训练", "v": "可启用",
                             "why": f"GPU {gpu_mem:.1f} GB 显存 · 可跑 GAN+DDPG 完整流程"})
            else:
                recs.append({"p": "GAN 训练", "v": "跳过（CPU 模式）",
                             "why": "无 CUDA · 默认跳过 GAN/DDPG，仅传统 ML"})
        except ImportError:
            recs.append({"p": "GAN 训练", "v": "跳过（未装 PyTorch）",
                         "why": "pip install torch 启用 GAN"})

        tips = []
        if mem.percent > 80:
            tips.append(f"⚠ 内存使用率 {mem.percent:.0f}% 偏高：建议关闭其他程序再训练")
        else:
            tips.append(f"✓ 内存使用率 {mem.percent:.0f}% 正常")
        if n_samples < 200:
            tips.append(f"⚠ 样本量 {n_samples} 偏少：R² 可能偏低，建议用主动学习扩充数据")
        tips.append(f"→ 特征维度 {n_features}（22 成分 + 70 微结构）· 样本/特征比 {n_samples/n_features:.1f}")

        return jsonify({"recs": recs, "tips": tips,
                        "n_samples": n_samples, "n_features": n_features})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# DDPG 深度强化学习 —— 异步训练接口
# ============================================================
import threading
import uuid

# 全局训练任务缓存：{task_id: {status, progress, epoch, total_epochs, losses, metrics, scatter, error, ...}}
_DDPG_TASKS = {}


def _run_ddpg_async(task_id, data_source, epochs, batch_size, lr_actor, lr_critic, test_size):
    """在后台线程中执行 DDPG 训练，实时更新 _DDPG_TASKS[task_id]"""
    task = _DDPG_TASKS[task_id]
    try:
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

        # ---------- 数据加载 ----------
        if data_source == "gan":
            # 前端"GAN 混合数据"选项：读取实测+GAN 合并的混合数据（COMBINED_DATA_PATH）
            df = pd.read_excel(config.COMBINED_DATA_PATH)
            s = df[config.composition_columns].sum(axis=1)
            df = df[(s >= 85) & (s <= 115)].copy()
        else:
            df = pd.read_excel(config.DATA_FILE_MIC)

        micro_cols = [f"Micro_{i+1}" for i in range(70)]
        feature_cols = micro_cols + config.composition_columns
        target_col = TARGET_COL

        # dropna 防止缺失值导致训练报错
        df = df.dropna(subset=feature_cols + [target_col])
        X = df[feature_cols].values
        y = df[target_col].values
        y = np.clip(y, np.percentile(y, 1), np.percentile(y, 99))  # 截断 1%/99% 分位外的极端值，抗噪

        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, random_state=config.RANDOM_STATE
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=0.15, random_state=config.RANDOM_STATE
        )

        # 标准化：X 与 y 都做 z-score，便于神经网络训练；scaler 用训练集拟合后变换 val/test
        X_scaler = StandardScaler(); X_train_s = X_scaler.fit_transform(X_train)
        X_val_s = X_scaler.transform(X_val); X_test_s = X_scaler.transform(X_test)
        y_scaler = StandardScaler()
        y_train_s = y_scaler.fit_transform(y_train.reshape(-1,1)).flatten()
        y_val_s = y_scaler.transform(y_val.reshape(-1,1)).flatten()
        y_test_s = y_scaler.transform(y_test.reshape(-1,1)).flatten()

        # ---------- 模型定义（简化版 DDPG，适配小样本）----------
        class Actor(nn.Module):
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
        gamma = 0.995; tau = 0.001  # gamma: 折扣因子；tau: 目标网络软更新系数
        y_min = y_train_s.min(); y_max = y_train_s.max()

        # 简单经验回放
        buf = []; cap = 10000
        def push(e):
            if len(buf) < cap: buf.append(e)
            else: buf[np.random.randint(len(buf))] = e  # 缓冲区满后随机覆盖

        task.update({"status":"running", "device": str(device), "n_train": len(y_train),
                     "n_val": len(y_val), "n_test": len(y_test), "n_features": s_dim})

        critic_losses = []; actor_losses = []
        best_r2 = -np.inf; patience = 100; no_improve = 0  # early stopping: 连续 100 轮无提升则停止

        for epoch in range(epochs):
            # 收集经验（eval 模式避免 BatchNorm 单样本报错）
            actor.eval()
            with torch.no_grad():
                all_acts = actor(torch.FloatTensor(X_train_s).to(device)).cpu().numpy().flatten()
            actor.train()
            for i in range(len(X_train_s)):
                st = X_train_s[i]; tgt = y_train_s[i]
                act = all_acts[i]
                noise = np.random.normal(0, 0.2, act.shape)  # OU-like 高斯噪声，鼓励探索
                act = np.clip(act + noise, -1, 1)  # Actor 输出 tanh 限制在 [-1,1]
                act_scaled = act * (y_max - y_min)/2 + (y_max + y_min)/2  # 反归一化到 y 真实尺度
                err = abs(act_scaled - tgt)
                # 奖励：误差越小奖励越高，分段线性递减；误差过大给负奖励
                if err < 0.05: r = 5.0*(1-err/0.05)
                elif err < 0.1: r = 3.0*(1-err/0.1)
                elif err < 0.2: r = 2.0*(1-err/0.2)
                elif err < 0.5: r = 1.0*(1-err/0.5)
                else: r = -1.0*err
                r = float(np.clip(r, -5, 10))
                ni = np.random.randint(len(X_train_s))
                # 经验元组：(s, a, r, s', done)；每 100 步标记一次 done
                push((st, float(act), r, X_train_s[ni], 1.0 if (i+1)%100==0 else 0.0))

            # 更新
            if len(buf) >= batch_size:
                idx = np.random.choice(len(buf), batch_size, replace=False)
                batch = [buf[i] for i in idx]
                sts = torch.FloatTensor(np.stack([b[0] for b in batch])).to(device)
                acts = torch.FloatTensor(np.array([b[1] for b in batch]).reshape(-1,1)).to(device)
                rs = torch.FloatTensor(np.array([b[2] for b in batch]).reshape(-1,1)).to(device)
                nss = torch.FloatTensor(np.stack([b[3] for b in batch])).to(device)
                ds = torch.FloatTensor(np.array([b[4] for b in batch]).reshape(-1,1)).to(device)

                # Critic 更新：TD 目标 = r + (1-done) * γ * Q'(s', a')
                with torch.no_grad():
                    na = actor_target(nss)
                    tq = rs + (1-ds)*gamma*critic_target(nss, na)
                cq = critic(sts, acts)
                td = cq - tq
                # Huber loss：小误差用 MSE，大误差用 MAE，抗异常值
                cl = torch.where(td.abs()<1, 0.5*td**2, td.abs()-0.5).mean()
                opt_c.zero_grad(); cl.backward()
                torch.nn.utils.clip_grad_norm_(critic.parameters(), 0.5); opt_c.step()  # 梯度裁剪防爆炸

                # Actor 更新：最大化 Q(s, a)，等价于最小化 -Q(s, μ(s))
                al = -critic(sts, actor(sts)).mean()
                opt_a.zero_grad(); al.backward()
                torch.nn.utils.clip_grad_norm_(actor.parameters(), 0.5); opt_a.step()

                # 目标网络软更新：θ' ← (1-τ)·θ' + τ·θ，平滑追踪主网络
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

        # 最终评估
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
            return {
                "r2": float(r2_score(yt, yp)),
                "rmse": float(np.sqrt(mean_squared_error(yt, yp))),
                "mae": float(mean_absolute_error(yt, yp)),
            }

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
        import time as _time
        req = request.get_json() or {}
        data_source = req.get("data_source", "real")  # real / gan
        epochs = max(1, int(req.get("epochs", 2000)))
        batch_size = max(2, int(req.get("batch_size", 32)))
        lr_actor = float(req.get("lr_actor", 1e-4))
        lr_critic = float(req.get("lr_critic", 5e-4))
        test_size = float(req.get("test_size", config.TEST_SIZE))
        test_size = max(0.05, min(test_size, 0.5))

        # 清理超过 1 小时的旧任务，避免 _DDPG_TASKS 无限增长
        now = _time.time()
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
            "created_at": _time.time(),
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
    """列出所有 DDPG 训练任务（最近的在前）"""
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
# 入口
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("FORGE 后端服务启动中...")
    print(f"数据文件: {config.DATA_FILE_MIC}")
    print(f"文件存在: {os.path.exists(config.DATA_FILE_MIC)}")
    print(f"PyTorch: {'可用' if _HAS_TORCH else '未安装'}")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=True)
