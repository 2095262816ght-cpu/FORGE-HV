"""
plot_utils.py - FORGE-HV 项目绘图工具模块

模块作用：
    本模块封装了项目中常用的 matplotlib / seaborn 绘图函数，集中管理图表样式与
    输出路径，便于在主程序与离线脚本中统一调用，避免重复样板代码。

主要图表类型：
    - 真实值 vs 预测值散点图（叠加二维核密度估计 KDE 背景，标注 MAPE）
    - 多模型性能指标对比柱状图（RMSE / R² / MAPE 三联子图）
    - DDPG 训练过程中的 Critic / Actor 损失曲线

输出目录：
    图像统一保存至 config.BASE_DIR 下的 Image 子目录，按实验类型分文件夹存放：
      - yuan_results       原始数据训练结果
      - gan_results        GAN 增强数据训练结果
      - ddpg_results       DDPG 训练结果
      - ddpg_gan_results   DDPG + GAN 联合训练结果

调用方：
    - app.py：在线训练 / 预测流程中调用以保存结果图
    - 离线脚本：结果复盘、报告生成时调用
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import config

# 设置中文字体：依次回退尝试黑体、微软雅黑、宋体
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号 '-' 显示为方块的问题


def plot_model_scatter(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值 vs 预测值散点图（原始数据，英文标签）

    画出训练集与测试集的预测值—真实值散点，叠加二维核密度估计（KDE）展示数据
    分布稠密程度，并在图例中标注各自的 MAPE。结果保存至 Image/yuan_results 目录。

    参数:
        y_train      : 训练集真实值（1D 数组）
        y_train_pred : 训练集预测值（1D 数组）
        y_test       : 测试集真实值（1D 数组）
        y_test_pred  : 测试集预测值（1D 数组）
        model_name   : 模型名称，用于图标题与输出文件名
        train_mape   : 训练集 MAPE（%），显示在图例中
        test_mape    : 测试集 MAPE（%），显示在图例中
    """
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])  # 合并所有值用于确定坐标范围
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1  # 上下留 10% 边距，避免点贴边

    plt.figure(figsize=(10, 8))  # 创建 10x8 英寸画布
    # 训练集散点：灰色，标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'train (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集散点：粉色，标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'tset (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='ideal prediction')  # 绘制 y=x 理想预测参考线

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)  # 训练集二维 KDE 分布
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)  # 测试集二维 KDE 分布

    plt.xlabel("true Vickers hardness（HV）", fontsize=12)
    plt.ylabel("predicted Vickers hardness（HV）", fontsize=12)
    plt.title(f"{model_name}model results comparison chart", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)  # 虚线网格，半透明

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "yuan_results"), exist_ok=True)  # 确保输出目录存在
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "yuan_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')  # 300 DPI 高清输出，紧凑裁剪白边
    plt.close()


def plot_combined_metrics(metrics):
    """绘制多模型性能指标对比柱状图（原始数据）

    将 RMSE、R²、MAPE 三项指标以 1×3 子图形式并排展示，每个柱顶标注数值，
    便于横向对比不同模型的测试集表现。结果保存至 Image/yuan_results 目录。

    参数:
        metrics : dict，形如 {模型名: {'test': {'RMSE (HV)':..., 'R²':..., 'MAPE (%)':...}}}
                  外层键的顺序即图中柱子从左到右的顺序
    """
    models = list(metrics.keys())
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # 三种模型的配色（蓝/橙/绿）

    # 创建1x3子图
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('数据训练的模型性能指标对比', fontsize=16, y=1.05)  # 总标题，y=1.05 抬高避免与子图标题重叠

    # 1. 绘制RMSE子图（值越小越好）
    rmse_values = [metrics[model]['test']['RMSE (HV)'] for model in models]
    bars1 = axes[0].bar(models, rmse_values, color=colors, edgecolor='black')
    axes[0].set_title('RMSE (HV)', fontsize=14)
    axes[0].set_ylabel('RMSE值', fontsize=12)
    axes[0].tick_params(axis='x', rotation=45)  # x 轴标签旋转 45° 防止重叠
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        height = bar.get_height()
        axes[0].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}', ha='center', va='bottom', fontsize=10)  # 柱顶标注数值

    # 2. 绘制R²子图（值越接近1越好）
    r2_values = [metrics[model]['test']['R²'] for model in models]
    bars2 = axes[1].bar(models, r2_values, color=colors, edgecolor='black')
    axes[1].set_title('R²', fontsize=14)
    axes[1].set_ylabel('R²值', fontsize=12)
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.4f}', ha='center', va='bottom', fontsize=10)  # R² 保留 4 位小数

    # 3. 绘制MAPE子图（值越小越好）
    mape_values = [metrics[model]['test']['MAPE (%)'] for model in models]
    bars3 = axes[2].bar(models, mape_values, color=colors, edgecolor='black')
    axes[2].set_title('MAPE (%)', fontsize=14)
    axes[2].set_ylabel('MAPE值', fontsize=12)
    axes[2].tick_params(axis='x', rotation=45)
    axes[2].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars3:
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}%', ha='center', va='bottom', fontsize=10)  # MAPE 带 % 号

    plt.tight_layout()  # 自动调整子图间距
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "yuan_results", "combined_metrics_comparison.png"),
                dpi=300, bbox_inches='tight')  # 300 DPI 高清输出，紧凑裁剪白边
    plt.close()


def plot_model_scatters(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值 vs 预测值散点图（GAN 增强数据，中文标签）

    与 plot_model_scatter 功能一致，但用于 GAN 数据增强后的训练结果，
    标签与标题改为中文，输出目录切换至 Image/gan_results。

    参数:
        y_train      : 训练集真实值（1D 数组）
        y_train_pred : 训练集预测值（1D 数组）
        y_test       : 测试集真实值（1D 数组）
        y_test_pred  : 测试集预测值（1D 数组）
        model_name   : 模型名称，用于图标题与输出文件名
        train_mape   : 训练集 MAPE（%），显示在图例中
        test_mape    : 测试集 MAPE（%），显示在图例中
    """
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])  # 合并所有值用于确定坐标范围
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1  # 上下留 10% 边距，避免点贴边

    plt.figure(figsize=(10, 8))  # 创建 10x8 英寸画布
    # 训练集散点：灰色，标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'训练集 (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集散点：粉色，标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'测试集 (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='理想预测')  # 绘制 y=x 理想预测参考线

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)  # 训练集二维 KDE 分布
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)  # 测试集二维 KDE 分布

    plt.xlabel("真实维氏硬度（HV）", fontsize=12)
    plt.ylabel("预测维氏硬度（HV）", fontsize=12)
    plt.title(f"{model_name}模型的真实值与预测值对比 (GAN数据)", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)  # 虚线网格，半透明

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "gan_results"), exist_ok=True)  # 确保输出目录存在
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "gan_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')  # 300 DPI 高清输出，紧凑裁剪白边
    plt.close()


def plot_combined_metricss(metrics):
    """绘制多模型性能指标对比柱状图（GAN 增强数据）

    与 plot_combined_metrics 结构一致，区别在于标题与输出目录针对 GAN 数据：
    结果保存至 Image/gan_results。

    参数:
        metrics : dict，形如 {模型名: {'test': {'RMSE (HV)':..., 'R²':..., 'MAPE (%)':...}}}
                  外层键的顺序即图中柱子从左到右的顺序
    """
    models = list(metrics.keys())
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # 三种模型的配色（蓝/橙/绿）

    # 创建1x3子图
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('GAN数据训练的模型性能指标对比', fontsize=16, y=1.05)  # 总标题，y=1.05 抬高避免与子图标题重叠

    # 1. 绘制RMSE子图（值越小越好）
    rmse_values = [metrics[model]['test']['RMSE (HV)'] for model in models]
    bars1 = axes[0].bar(models, rmse_values, color=colors, edgecolor='black')
    axes[0].set_title('RMSE (HV)', fontsize=14)
    axes[0].set_ylabel('RMSE值', fontsize=12)
    axes[0].tick_params(axis='x', rotation=45)  # x 轴标签旋转 45° 防止重叠
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        height = bar.get_height()
        axes[0].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}', ha='center', va='bottom', fontsize=10)  # 柱顶标注数值

    # 2. 绘制R²子图（值越接近1越好）
    r2_values = [metrics[model]['test']['R²'] for model in models]
    bars2 = axes[1].bar(models, r2_values, color=colors, edgecolor='black')
    axes[1].set_title('R²', fontsize=14)
    axes[1].set_ylabel('R²值', fontsize=12)
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.4f}', ha='center', va='bottom', fontsize=10)  # R² 保留 4 位小数

    # 3. 绘制MAPE子图（值越小越好）
    mape_values = [metrics[model]['test']['MAPE (%)'] for model in models]
    bars3 = axes[2].bar(models, mape_values, color=colors, edgecolor='black')
    axes[2].set_title('MAPE (%)', fontsize=14)
    axes[2].set_ylabel('MAPE值', fontsize=12)
    axes[2].tick_params(axis='x', rotation=45)
    axes[2].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars3:
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}%', ha='center', va='bottom', fontsize=10)  # MAPE 带 % 号

    plt.tight_layout()  # 自动调整子图间距
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "gan_results", "combined_metrics_comparison.png"),
                dpi=300, bbox_inches='tight')  # 300 DPI 高清输出，紧凑裁剪白边
    plt.close()


def plot_ddph_scatter(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值 vs 预测值散点图（DDPG 训练结果，英文标签）

    用于 DDPG（深度确定性策略梯度）训练后回归结果的对比展示，结构同
    plot_model_scatter，输出目录切换至 Image/ddpg_results。

    参数:
        y_train      : 训练集真实值（1D 数组）
        y_train_pred : 训练集预测值（1D 数组）
        y_test       : 测试集真实值（1D 数组）
        y_test_pred  : 测试集预测值（1D 数组）
        model_name   : 模型名称，用于图标题与输出文件名
        train_mape   : 训练集 MAPE（%），显示在图例中
        test_mape    : 测试集 MAPE（%），显示在图例中
    """
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])  # 合并所有值用于确定坐标范围
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1  # 上下留 10% 边距，避免点贴边

    plt.figure(figsize=(10, 8))  # 创建 10x8 英寸画布
    # 训练集散点：灰色，标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'train (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集散点：粉色，标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'test (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='ideal prediction')  # 绘制 y=x 理想预测参考线

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)  # 训练集二维 KDE 分布
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)  # 测试集二维 KDE 分布

    plt.xlabel("true Vickers hardness（HV）", fontsize=12)
    plt.ylabel("predicted Vickers hardness（HV）", fontsize=12)
    plt.title(f"{model_name}model results comparison chart", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)  # 虚线网格，半透明

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_results"), exist_ok=True)  # 确保输出目录存在
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')  # 300 DPI 高清输出，紧凑裁剪白边
    plt.close()


def plot_loss_curves(critic_losses, actor_losses):
    """绘制 DDPG 训练损失曲线（Critic / Actor 双子图）

    用于监控 DDPG 训练过程中两个网络的损失变化趋势，便于判断是否收敛、
    是否出现发散或震荡。结果保存至 Image/ddpg_results 目录。

    参数:
        critic_losses : Critic 网络每个 epoch 的损失值列表
        actor_losses  : Actor 网络每个 epoch 的损失值列表
    """
    plt.figure(figsize=(12, 5))  # 创建 12x5 英寸画布，宽幅便于左右并排

    # 左子图：Critic 网络损失
    plt.subplot(1, 2, 1)
    plt.plot(critic_losses, label='Critic Loss')
    plt.title('Critic网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)  # 虚线网格，半透明

    # 右子图：Actor 网络损失（橙色区分）
    plt.subplot(1, 2, 2)
    plt.plot(actor_losses, label='Actor Loss', color='orange')
    plt.title('Actor网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    plt.tight_layout()  # 自动调整子图间距

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_results"), exist_ok=True)  # 确保输出目录存在
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_results", "ddpg_losses.png"), dpi=300)  # 300 DPI 高清输出
    plt.close()


def plot_ddph_gan_scatter(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值 vs 预测值散点图（DDPG + GAN 联合训练结果，中文标签）

    用于 DDPG 与 GAN 联合训练后的回归结果展示，结构与 plot_model_scatters 一致，
    输出目录切换至 Image/ddpg_gan_results。

    参数:
        y_train      : 训练集真实值（1D 数组）
        y_train_pred : 训练集预测值（1D 数组）
        y_test       : 测试集真实值（1D 数组）
        y_test_pred  : 测试集预测值（1D 数组）
        model_name   : 模型名称，用于图标题与输出文件名
        train_mape   : 训练集 MAPE（%），显示在图例中
        test_mape    : 测试集 MAPE（%），显示在图例中
    """
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])  # 合并所有值用于确定坐标范围
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1  # 上下留 10% 边距，避免点贴边

    plt.figure(figsize=(10, 8))  # 创建 10x8 英寸画布
    # 训练集散点：灰色，标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'训练集 (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集散点：粉色，标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'测试集 (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='理想预测')  # 绘制 y=x 理想预测参考线

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)  # 训练集二维 KDE 分布
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)  # 测试集二维 KDE 分布

    plt.xlabel("真实维氏硬度（HV）", fontsize=12)
    plt.ylabel("预测维氏硬度（HV）", fontsize=12)
    plt.title(f"{model_name}模型的真实值与预测值对比", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)  # 虚线网格，半透明

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results"), exist_ok=True)  # 确保输出目录存在
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')  # 300 DPI 高清输出，紧凑裁剪白边
    plt.close()


def plot_ganloss_curves(critic_losses, actor_losses):
    """绘制 DDPG + GAN 联合训练的损失曲线（Critic / Actor 双子图）

    与 plot_loss_curves 结构一致，区别仅在于输出目录切换至 Image/ddpg_gan_results，
    用于区分 DDPG + GAN 联合训练场景。

    参数:
        critic_losses : Critic 网络每个 epoch 的损失值列表
        actor_losses  : Actor 网络每个 epoch 的损失值列表
    """
    plt.figure(figsize=(12, 5))  # 创建 12x5 英寸画布，宽幅便于左右并排

    # 左子图：Critic 网络损失
    plt.subplot(1, 2, 1)
    plt.plot(critic_losses, label='Critic Loss')
    plt.title('Critic网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)  # 虚线网格，半透明

    # 右子图：Actor 网络损失（橙色区分）
    plt.subplot(1, 2, 2)
    plt.plot(actor_losses, label='Actor Loss', color='orange')
    plt.title('Actor网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    plt.tight_layout()  # 自动调整子图间距

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results"), exist_ok=True)  # 确保输出目录存在
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results", "ddpg_losses.png"), dpi=300)  # 300 DPI 高清输出
    plt.close()

