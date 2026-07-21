"""
GAN-main.py —— GAN（Generative Adversarial Network）生成对抗网络离线训练脚本

文件作用：
    本脚本为 FORGE-HV 项目的 GAN 数据下游训练评估入口。它加载已通过 GAN
    生成对抗网络合成的高温合金成分数据，并将其与原始训练集合并、扩充，
    随后用传统机器学习模型对扩充后的数据进行训练与评估。

核心功能：
    1. 加载 GAN 生成的高温合金成分数据（含 70 维微观结构 + 22 维成分 + 硬度）
    2. 按成分总和约束（90~110）筛选有效样本，过滤异常合成数据
    3. 使用 LR（线性回归）、PR（多项式回归 + Ridge）、SVR（支持向量回归）
       三个基线模型对扩充后的数据进行训练
    4. 在训练集 / 测试集上评估 RMSE、MAE、R²、MAPE 等指标
    5. 输出散点拟合图与综合指标对比图，并将结果保存为 Excel

算法原理简述：
    GAN 由 Generator（生成器）和 Discriminator（判别器）组成。生成器负责
    从随机噪声中生成逼真的高温合金成分样本，判别器负责区分真实样本与生成
    样本；两者通过对抗博弈交替训练，最终生成器能够产出逼近真实分布的合成
    数据。本脚本不直接训练 GAN，而是消费 GAN 已生成的数据用于下游回归任务。

运行方式：
    python GAN-main.py

输出：
    - 生成数据相关结果：保存到 results/yuan_results/ 目录
      （含 yuan_model_metrics.xlsx 模型指标汇总、{模型}_预测结果.xlsx 预测明细）
    - 训练损失 / 拟合散点图与综合指标对比图：由 plot_utils 输出到 output/ 目录
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.linear_model import Ridge
import config

# 导入绘图模块
from plot_utils import plot_model_scatters, plot_combined_metricss

# --------------------------
# 1. GAN数据处理函数
# --------------------------
def load_and_filter_gan_data():
    """
    加载并筛选 GAN 生成的数据。

    从 config.COMBINED_DATA_PATH 读取 GAN 合成的数据，按成分总和约束
    （90~110，允许 ±10 的容差以兼容生成数据的浮动）过滤掉异常样本，
    保证用于下游训练的合成样本在物理上合理。
    """
    # 加载GAN生成的数据
    gan_df = pd.read_excel(config.COMBINED_DATA_PATH)
    print(f"通过GAN生成的数据量: {len(gan_df)}")

    # 筛选成分总和在100左右的样本（±1误差范围）
    composition_sum = gan_df[config.composition_columns].sum(axis=1)  # 按行求 22 维成分总和
    valid_mask = (composition_sum >= 90) & (composition_sum <= 110)   # 合法合金成分总和区间
    filtered_df = gan_df[valid_mask].copy()                          # 保留通过筛选的样本

    print(f"筛选后的数据量: {len(filtered_df)}")
    print(f"成分总和范围: [{filtered_df[config.composition_columns].sum(axis=1).min():.4f}, "
          f"{filtered_df[config.composition_columns].sum(axis=1).max():.4f}]")

    return filtered_df


def prepare_gan_features(gan_df):
    """
    准备 GAN 数据的特征矩阵和目标变量。

    特征由 70 维微观结构（Micro_1 ~ Micro_70）与 22 维成分拼接而成，
    目标变量为 Vickers 硬度（HV）。
    """
    # 提取特征列：70维微观结构 + 22维成分
    micro_cols = [f"Micro_{i + 1}" for i in range(70)]               # 70 维微观结构列名
    feature_cols = micro_cols + config.composition_columns           # 拼接成完整特征列（共 92 维）

    # 目标变量：硬度
    target_col = "Vickers Hardness (HV)"                             # 维氏硬度回归目标

    X = gan_df[feature_cols].values                                  # 特征矩阵 X: (n_samples, 92)
    y = gan_df[target_col].values                                    # 目标向量 y: (n_samples,)

    return X, y, feature_cols, target_col


# --------------------------
# 2. 模型评估函数
# --------------------------
def calculate_metrics(y_true, y_pred, dataset_name="数据集"):
    """
    计算回归评估指标。

    返回 RMSE、MAE、R²、MAPE 四项核心指标。其中展示用字段保留 2~4 位小数，
    带下划线后缀的字段（如 RMSE_value）保留原始浮点值，便于后续比较与筛选最佳模型。
    MAPE 计算时会过滤真实值为 0 的样本，避免除零错误。
    """
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))   # 均方根误差
    mae = mean_absolute_error(y_true, y_pred)            # 平均绝对误差
    r2 = r2_score(y_true, y_pred)                        # 决定系数

    # 处理MAPE避免除零错误
    non_zero_mask = y_true != 0                          # 排除真实值为 0 的样本
    y_true_filtered = y_true[non_zero_mask]
    y_pred_filtered = y_pred[non_zero_mask]

    # MAPE：平均绝对百分比误差，单位 %
    mape = np.mean(np.abs((y_true_filtered - y_pred_filtered) / y_true_filtered)) * 100 if len(
        y_true_filtered) > 0 else 0.0

    return {
        "数据集": dataset_name,
        "RMSE (HV)": round(rmse, 2),                     # 展示用（保留 2 位小数）
        "RMSE_value": rmse,                              # 原始值，用于模型比较
        "MAE (HV)": round(mae, 2),
        "MAE_value": mae,
        "R²": round(r2, 4),
        "R2_value": r2,
        "MAPE (%)": round(mape, 2),
        "MAPE_value": mape
    }


# --------------------------
# 3. 主函数
# --------------------------
def main():
    """
    主流程：加载 GAN 数据 -> 准备特征 -> 划分数据集 -> 训练三个基线模型
    -> 评估并可视化 -> 选出最佳模型 -> 保存结果。
    """
    # 1. 加载并筛选GAN数据
    gan_df = load_and_filter_gan_data()

    # 2. 准备特征和目标变量
    X, y, feature_cols, target_col = prepare_gan_features(gan_df)

    # 3. 划分训练集和测试集（与model_comparison.py保持一致的划分比例）
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE   # 复用全局随机种子保证可复现
    )

    # 4. 定义模型（使用model_comparison.py中的三个传统模型）
    models = {
        # 线性回归
        "LR": Pipeline([
            ('scaler', StandardScaler()),                                     # 标准化：去均值、除标准差
            ('regressor', LinearRegression())                                 # 普通最小二乘线性回归
        ]),
        # 多项式回归
        "PR": Pipeline([
            ('scaler', StandardScaler()),
            ('poly', PolynomialFeatures(degree=1)),                           # degree=1 退化为线性特征
            ('regressor', Ridge(alpha=1.0))  # 加入L2正则化                   # alpha=1.0 控制 L2 惩罚强度
        ]),
        # 支持向量回归
        "SVR": Pipeline([
            ('scaler', StandardScaler()),
            ('regressor', SVR(kernel='linear'))                               # 线性核 SVR
        ])
    }

    # 5. 训练模型并评估
    metrics = {}                                                                      # 各模型评估指标字典
    predictions = {}  # 存储预测结果                                                  # 各模型预测明细字典

    for model_name, model in models.items():
        print(f"\n训练{model_name}模型...")

        # 训练模型
        model.fit(X_train, y_train)                                                   # 在训练集上拟合模型

        # 预测
        y_train_pred = model.predict(X_train)                                         # 训练集预测值
        y_test_pred = model.predict(X_test)                                           # 测试集预测值

        # 保存预测结果
        predictions[model_name] = {
            "train_true": y_train,
            "train_pred": y_train_pred,
            "test_true": y_test,
            "test_pred": y_test_pred
        }

        # 评估
        metrics[model_name] = {
            "train": calculate_metrics(y_train, y_train_pred, "训练集"),               # 训练集指标
            "test": calculate_metrics(y_test, y_test_pred, "测试集")                  # 测试集指标
        }

        # 可视化
        plot_model_scatters(
            y_train, y_train_pred,
            y_test, y_test_pred,
            model_name,
            train_mape=metrics[model_name]['train']['MAPE (%)'],  # 传入训练集MAPE
            test_mape=metrics[model_name]['test']['MAPE (%)']  # 传入测试集MAPE
        )

    # 6. 打印性能指标
    print("\n" + "=" * 50)
    print("训练的模型性能对比")
    print("=" * 50)
    for model_name in metrics:
        print(f"\n{model_name}:")
        print(f"训练集 - RMSE: {metrics[model_name]['train']['RMSE (HV)']} HV, "
              f"R²: {metrics[model_name]['train']['R²']}, "
              f"MAPE: {metrics[model_name]['train']['MAPE (%)']}%")
        print(f"测试集 - RMSE: {metrics[model_name]['test']['RMSE (HV)']} HV, "
              f"R²: {metrics[model_name]['test']['R²']}, "
              f"MAPE: {metrics[model_name]['test']['MAPE (%)']}%")

    # 7. 确定最佳模型
    best_r2_model = ""                                                                # R² 最高的模型名
    best_rmse_model = ""                                                              # RMSE 最低的模型名
    best_r2 = -float('inf')                                                           # R² 初始值取负无穷
    best_rmse = float('inf')                                                          # RMSE 初始值取正无穷

    for model_name in metrics:
        if metrics[model_name]['test']['R2_value'] > best_r2:                        # 更新最佳 R²
            best_r2 = metrics[model_name]['test']['R2_value']
            best_r2_model = model_name
        if metrics[model_name]['test']['RMSE_value'] < best_rmse:                    # 更新最佳 RMSE
            best_rmse = metrics[model_name]['test']['RMSE_value']
            best_rmse_model = model_name

    print(f"\n测试集上R²最高的模型: {best_r2_model} (R² = {best_r2:.4f})")
    print(f"测试集上RMSE最低的模型: {best_rmse_model} (RMSE = {best_rmse:.2f} HV)")

    # 8. 保存预测结果到表格
    results_dir = os.path.join(config.BASE_DIR, "results", "yuan_results")            # 结果输出目录
    os.makedirs(results_dir, exist_ok=True)                                           # 目录不存在则创建

    # 保存指标结果
    results_df = pd.DataFrame()
    for model_name in metrics:
        train_metrics = metrics[model_name]['train'].copy()                           # 复制训练集指标
        train_metrics['模型'] = model_name
        train_metrics['数据集类型'] = '训练集'

        test_metrics = metrics[model_name]['test'].copy()                             # 复制测试集指标
        test_metrics['模型'] = model_name
        test_metrics['数据集类型'] = '测试集'

        results_df = pd.concat([results_df, pd.DataFrame([train_metrics, test_metrics])], ignore_index=True)

    results_df = results_df[['模型', '数据集类型', 'RMSE (HV)', 'MAE (HV)', 'R²', 'MAPE (%)']]   # 整理列顺序
    results_df.to_excel(os.path.join(results_dir, "yuan_model_metrics.xlsx"), index=False)       # 写入 Excel
    print(f"\n模型评估指标已保存至 {os.path.join(results_dir, 'yuan_model_metrics.xlsx')}")

    # 保存详细预测结果
    for model_name in predictions:
        pred_df = pd.DataFrame({
            '真实值': predictions[model_name]['test_true'],
            '预测值': predictions[model_name]['test_pred'],
            '误差': predictions[model_name]['test_true'] - predictions[model_name]['test_pred']    # 真实值 - 预测值
        })
        pred_df.to_excel(os.path.join(results_dir, f"{model_name}_预测结果.xlsx"), index=False)
        print(f"{model_name}模型预测结果已保存至 {os.path.join(results_dir, f'{model_name}_预测结果.xlsx')}")

    # 9. 绘制综合指标对比图
    plot_combined_metricss(metrics)                                                   # 多模型指标横向对比


if __name__ == "__main__":
    main()