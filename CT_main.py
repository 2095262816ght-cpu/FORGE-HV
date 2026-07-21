"""
CT_main.py —— FORGE-HV 项目离线训练脚本

作用说明
--------
本脚本是独立运行的离线训练入口，不依赖 Flask，可在命令行直接执行。
核心流程：读取实测数据 → 特征工程（微观结构 + 成分） → 训练多个回归模型 →
         评估模型性能 → 保存模型评估结果与预测结果。

运行方式
--------
    python CT_main.py

输出说明
--------
- 评估指标与预测结果保存至 results/yuan_results/ 目录
- 模型散点图与综合指标对比图由 plot_utils 模块生成
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
from plot_utils import plot_model_scatter, plot_combined_metrics

# --------------------------
# 1. GAN数据处理函数
# --------------------------
def load_and_filter_gan_data():
    """加载实测数据并按成分总和筛选有效样本"""
    # 加载实测数据（含微观结构特征）
    gan_df = pd.read_excel(config.DATA_FILE_MIC)  # 从配置文件指定路径读取 Excel
    print(f"原始数据量: {len(gan_df)}")

    # 筛选成分总和在 85~115 的样本（允许实验误差）
    composition_sum = gan_df[config.composition_columns].sum(axis=1)  # 按行求成分总和
    valid_mask = (composition_sum >= 85) & (composition_sum <= 115)  # 构造有效样本布尔掩码
    filtered_df = gan_df[valid_mask].copy()  # 保留通过筛选的样本

    print(f"筛选后的数据量: {len(filtered_df)}")
    print(f"成分总和范围: [{filtered_df[config.composition_columns].sum(axis=1).min():.4f}, "
          f"{filtered_df[config.composition_columns].sum(axis=1).max():.4f}]")

    return filtered_df


def prepare_gan_features(gan_df):
    """准备GAN数据的特征和目标变量"""
    # 提取特征列：70维微观结构 + 22维成分
    micro_cols = [f"Micro_{i + 1}" for i in range(70)]  # 生成 Micro_1 ~ Micro_70 列名
    feature_cols = micro_cols + config.composition_columns  # 合并微观结构与成分特征列

    # 目标变量：硬度
    target_col = "Vickers Hardness (HV)"  # 维氏硬度（回归目标）

    X = gan_df[feature_cols].values  # 特征矩阵 X：(n_samples, 92)
    y = gan_df[target_col].values  # 标签向量 y：(n_samples,)

    return X, y, feature_cols, target_col


# --------------------------
# 2. 模型评估函数
# --------------------------
def calculate_metrics(y_true, y_pred, dataset_name="数据集"):
    """计算回归模型评估指标：RMSE、MAE、R²、MAPE"""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))  # 均方根误差
    mae = mean_absolute_error(y_true, y_pred)  # 平均绝对误差
    r2 = r2_score(y_true, y_pred)  # 决定系数

    # 处理MAPE避免除零错误
    non_zero_mask = y_true != 0  # 排除真实值为 0 的样本
    y_true_filtered = y_true[non_zero_mask]
    y_pred_filtered = y_pred[non_zero_mask]

    mape = np.mean(np.abs((y_true_filtered - y_pred_filtered) / y_true_filtered)) * 100 if len(
        y_true_filtered) > 0 else 0.0  # 平均绝对百分比误差

    return {
        "数据集": dataset_name,
        "RMSE (HV)": round(rmse, 2),  # 用于展示的四舍五入值
        "RMSE_value": rmse,  # 原始数值，用于排序比较
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
    """主流程：加载数据 → 准备特征 → 训练评估模型 → 保存结果"""
    # 1. 加载并筛选GAN数据
    gan_df = load_and_filter_gan_data()  # 获取成分总和合法的样本

    # 2. 准备特征和目标变量
    X, y, feature_cols, target_col = prepare_gan_features(gan_df)  # 构造 X、y

    # 3. 划分训练集和测试集（与model_comparison.py保持一致的划分比例）
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE  # 固定随机种子保证可复现
    )

    # 4. 定义模型（使用model_comparison.py中的三个传统模型）
    models = {
        # 线性回归
        "LR": Pipeline([  # 流水线：先标准化再拟合回归
            ('scaler', StandardScaler()),
            ('regressor', LinearRegression())
        ]),
        # 多项式回归
        "PR": Pipeline([
            ('scaler', StandardScaler()),
            ('poly', PolynomialFeatures(degree=1)),  # degree=1 退化为线性特征
            ('regressor', Ridge(alpha=1.0))  # 加入L2正则化
        ]),
        # 支持向量回归
        "SVR": Pipeline([
            ('scaler', StandardScaler()),
            ('regressor', SVR(kernel='linear'))  # 线性核 SVR
        ])
    }

    # 5. 训练模型并评估
    metrics = {}
    predictions = {}  # 存储预测结果

    for model_name, model in models.items():
        print(f"\n训练{model_name}模型...")

        # 训练模型
        model.fit(X_train, y_train)

        # 预测
        y_train_pred = model.predict(X_train)  # 训练集预测
        y_test_pred = model.predict(X_test)  # 测试集预测

        # 保存预测结果
        predictions[model_name] = {
            "train_true": y_train,
            "train_pred": y_train_pred,
            "test_true": y_test,
            "test_pred": y_test_pred
        }

        # 评估
        metrics[model_name] = {
            "train": calculate_metrics(y_train, y_train_pred, "训练集"),  # 训练集指标
            "test": calculate_metrics(y_test, y_test_pred, "测试集")  # 测试集指标
        }

        # 可视化
        plot_model_scatter(
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
    best_r2_model = ""
    best_rmse_model = ""
    best_r2 = -float('inf')  # R² 初始值设为负无穷
    best_rmse = float('inf')  # RMSE 初始值设为正无穷

    for model_name in metrics:
        if metrics[model_name]['test']['R2_value'] > best_r2:  # 比较测试集 R²
            best_r2 = metrics[model_name]['test']['R2_value']
            best_r2_model = model_name
        if metrics[model_name]['test']['RMSE_value'] < best_rmse:  # 比较测试集 RMSE
            best_rmse = metrics[model_name]['test']['RMSE_value']
            best_rmse_model = model_name

    print(f"\n测试集上R²最高的模型: {best_r2_model} (R² = {best_r2:.4f})")
    print(f"测试集上RMSE最低的模型: {best_rmse_model} (RMSE = {best_rmse:.2f} HV)")

    # 8. 保存预测结果到表格
    results_dir = os.path.join(config.BASE_DIR, "results", "yuan_results")  # 输出目录
    os.makedirs(results_dir, exist_ok=True)  # 目录不存在则创建

    # 保存指标结果
    results_df = pd.DataFrame()
    for model_name in metrics:
        train_metrics = metrics[model_name]['train'].copy()  # 训练集指标副本
        train_metrics['模型'] = model_name
        train_metrics['数据集类型'] = '训练集'

        test_metrics = metrics[model_name]['test'].copy()  # 测试集指标副本
        test_metrics['模型'] = model_name
        test_metrics['数据集类型'] = '测试集'

        results_df = pd.concat([results_df, pd.DataFrame([train_metrics, test_metrics])], ignore_index=True)  # 追加到结果表

    results_df = results_df[['模型', '数据集类型', 'RMSE (HV)', 'MAE (HV)', 'R²', 'MAPE (%)']]  # 选取展示列
    results_df.to_excel(os.path.join(results_dir, "yuan_model_metrics.xlsx"), index=False)  # 写入 Excel
    print(f"\n模型评估指标已保存至 {os.path.join(results_dir, 'yuan_model_metrics.xlsx')}")

    # 保存详细预测结果
    for model_name in predictions:
        pred_df = pd.DataFrame({
            '真实值': predictions[model_name]['test_true'],
            '预测值': predictions[model_name]['test_pred'],
            '误差': predictions[model_name]['test_true'] - predictions[model_name]['test_pred']  # 真实 - 预测
        })
        pred_df.to_excel(os.path.join(results_dir, f"{model_name}_预测结果.xlsx"), index=False)  # 每个模型单独一份
        print(f"{model_name}模型预测结果已保存至 {os.path.join(results_dir, f'{model_name}_预测结果.xlsx')}")

    # 9. 绘制综合指标对比图
    plot_combined_metrics(metrics)  # 多模型指标对比图


if __name__ == "__main__":
    main()  # 脚本入口：直接运行时执行主流程