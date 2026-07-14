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
    """加载并筛选GAN生成的数据"""
    # 加载GAN生成的数据
    gan_df = pd.read_excel(config.COMBINED_DATA_PATH)
    print(f"通过GAN生成的数据量: {len(gan_df)}")

    # 筛选成分总和在100左右的样本（±1误差范围）
    composition_sum = gan_df[config.composition_columns].sum(axis=1)
    valid_mask = (composition_sum >= 90) & (composition_sum <= 110)
    filtered_df = gan_df[valid_mask].copy()

    print(f"筛选后的数据量: {len(filtered_df)}")
    print(f"成分总和范围: [{filtered_df[config.composition_columns].sum(axis=1).min():.4f}, "
          f"{filtered_df[config.composition_columns].sum(axis=1).max():.4f}]")

    return filtered_df


def prepare_gan_features(gan_df):
    """准备GAN数据的特征和目标变量"""
    # 提取特征列：70维微观结构 + 22维成分
    micro_cols = [f"Micro_{i + 1}" for i in range(70)]
    feature_cols = micro_cols + config.composition_columns

    # 目标变量：硬度
    target_col = "Vickers Hardness (HV)"

    X = gan_df[feature_cols].values
    y = gan_df[target_col].values

    return X, y, feature_cols, target_col


# --------------------------
# 2. 模型评估函数
# --------------------------
def calculate_metrics(y_true, y_pred, dataset_name="数据集"):
    """计算评估指标"""
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)

    # 处理MAPE避免除零错误
    non_zero_mask = y_true != 0
    y_true_filtered = y_true[non_zero_mask]
    y_pred_filtered = y_pred[non_zero_mask]

    mape = np.mean(np.abs((y_true_filtered - y_pred_filtered) / y_true_filtered)) * 100 if len(
        y_true_filtered) > 0 else 0.0

    return {
        "数据集": dataset_name,
        "RMSE (HV)": round(rmse, 2),
        "RMSE_value": rmse,
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
    # 1. 加载并筛选GAN数据
    gan_df = load_and_filter_gan_data()

    # 2. 准备特征和目标变量
    X, y, feature_cols, target_col = prepare_gan_features(gan_df)

    # 3. 划分训练集和测试集（与model_comparison.py保持一致的划分比例）
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE
    )

    # 4. 定义模型（使用model_comparison.py中的三个传统模型）
    models = {
        # 线性回归
        "LR": Pipeline([
            ('scaler', StandardScaler()),
            ('regressor', LinearRegression())
        ]),
        # 多项式回归
        "PR": Pipeline([
            ('scaler', StandardScaler()),
            ('poly', PolynomialFeatures(degree=1)),
            ('regressor', Ridge(alpha=1.0))  # 加入L2正则化
        ]),
        # 支持向量回归
        "SVR": Pipeline([
            ('scaler', StandardScaler()),
            ('regressor', SVR(kernel='linear'))
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
        y_train_pred = model.predict(X_train)
        y_test_pred = model.predict(X_test)

        # 保存预测结果
        predictions[model_name] = {
            "train_true": y_train,
            "train_pred": y_train_pred,
            "test_true": y_test,
            "test_pred": y_test_pred
        }

        # 评估
        metrics[model_name] = {
            "train": calculate_metrics(y_train, y_train_pred, "训练集"),
            "test": calculate_metrics(y_test, y_test_pred, "测试集")
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
    best_r2_model = ""
    best_rmse_model = ""
    best_r2 = -float('inf')
    best_rmse = float('inf')

    for model_name in metrics:
        if metrics[model_name]['test']['R2_value'] > best_r2:
            best_r2 = metrics[model_name]['test']['R2_value']
            best_r2_model = model_name
        if metrics[model_name]['test']['RMSE_value'] < best_rmse:
            best_rmse = metrics[model_name]['test']['RMSE_value']
            best_rmse_model = model_name

    print(f"\n测试集上R²最高的模型: {best_r2_model} (R² = {best_r2:.4f})")
    print(f"测试集上RMSE最低的模型: {best_rmse_model} (RMSE = {best_rmse:.2f} HV)")

    # 8. 保存预测结果到表格
    results_dir = os.path.join(config.BASE_DIR, "results", "yuan_results")
    os.makedirs(results_dir, exist_ok=True)

    # 保存指标结果
    results_df = pd.DataFrame()
    for model_name in metrics:
        train_metrics = metrics[model_name]['train'].copy()
        train_metrics['模型'] = model_name
        train_metrics['数据集类型'] = '训练集'

        test_metrics = metrics[model_name]['test'].copy()
        test_metrics['模型'] = model_name
        test_metrics['数据集类型'] = '测试集'

        results_df = pd.concat([results_df, pd.DataFrame([train_metrics, test_metrics])], ignore_index=True)

    results_df = results_df[['模型', '数据集类型', 'RMSE (HV)', 'MAE (HV)', 'R²', 'MAPE (%)']]
    results_df.to_excel(os.path.join(results_dir, "yuan_model_metrics.xlsx"), index=False)
    print(f"\n模型评估指标已保存至 {os.path.join(results_dir, 'yuan_model_metrics.xlsx')}")

    # 保存详细预测结果
    for model_name in predictions:
        pred_df = pd.DataFrame({
            '真实值': predictions[model_name]['test_true'],
            '预测值': predictions[model_name]['test_pred'],
            '误差': predictions[model_name]['test_true'] - predictions[model_name]['test_pred']
        })
        pred_df.to_excel(os.path.join(results_dir, f"{model_name}_预测结果.xlsx"), index=False)
        print(f"{model_name}模型预测结果已保存至 {os.path.join(results_dir, f'{model_name}_预测结果.xlsx')}")

    # 9. 绘制综合指标对比图
    plot_combined_metricss(metrics)


if __name__ == "__main__":
    main()