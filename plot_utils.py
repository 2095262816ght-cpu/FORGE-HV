import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import config

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "SimSun"]
plt.rcParams["axes.unicode_minus"] = False


def plot_model_scatter(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值vs预测值散点图（包含MAPE信息）"""
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1

    plt.figure(figsize=(10, 8))
    # 训练集标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'train (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'tset (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='ideal prediction')

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)

    plt.xlabel("true Vickers hardness（HV）", fontsize=12)
    plt.ylabel("predicted Vickers hardness（HV）", fontsize=12)
    plt.title(f"{model_name}model results comparison chart", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "yuan_results"), exist_ok=True)
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "yuan_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')
    plt.close()


def plot_combined_metrics(metrics):
    """绘制模型性能对比图"""
    models = list(metrics.keys())
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # 三种模型的配色

    # 创建1x3子图
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('数据训练的模型性能指标对比', fontsize=16, y=1.05)

    # 1. 绘制RMSE子图
    rmse_values = [metrics[model]['test']['RMSE (HV)'] for model in models]
    bars1 = axes[0].bar(models, rmse_values, color=colors, edgecolor='black')
    axes[0].set_title('RMSE (HV)', fontsize=14)
    axes[0].set_ylabel('RMSE值', fontsize=12)
    axes[0].tick_params(axis='x', rotation=45)
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        height = bar.get_height()
        axes[0].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}', ha='center', va='bottom', fontsize=10)

    # 2. 绘制R²子图
    r2_values = [metrics[model]['test']['R²'] for model in models]
    bars2 = axes[1].bar(models, r2_values, color=colors, edgecolor='black')
    axes[1].set_title('R²', fontsize=14)
    axes[1].set_ylabel('R²值', fontsize=12)
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.4f}', ha='center', va='bottom', fontsize=10)

    # 3. 绘制MAPE子图
    mape_values = [metrics[model]['test']['MAPE (%)'] for model in models]
    bars3 = axes[2].bar(models, mape_values, color=colors, edgecolor='black')
    axes[2].set_title('MAPE (%)', fontsize=14)
    axes[2].set_ylabel('MAPE值', fontsize=12)
    axes[2].tick_params(axis='x', rotation=45)
    axes[2].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars3:
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}%', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "yuan_results", "combined_metrics_comparison.png"),
                dpi=300, bbox_inches='tight')
    plt.close()


def plot_model_scatters(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值vs预测值散点图（包含MAPE信息）"""
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1

    plt.figure(figsize=(10, 8))
    # 训练集标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'训练集 (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'测试集 (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='理想预测')

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)

    plt.xlabel("真实维氏硬度（HV）", fontsize=12)
    plt.ylabel("预测维氏硬度（HV）", fontsize=12)
    plt.title(f"{model_name}模型的真实值与预测值对比 (GAN数据)", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "gan_results"), exist_ok=True)
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "gan_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')
    plt.close()


def plot_combined_metricss(metrics):
    """绘制模型性能对比图"""
    models = list(metrics.keys())
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']  # 三种模型的配色

    # 创建1x3子图
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('GAN数据训练的模型性能指标对比', fontsize=16, y=1.05)

    # 1. 绘制RMSE子图
    rmse_values = [metrics[model]['test']['RMSE (HV)'] for model in models]
    bars1 = axes[0].bar(models, rmse_values, color=colors, edgecolor='black')
    axes[0].set_title('RMSE (HV)', fontsize=14)
    axes[0].set_ylabel('RMSE值', fontsize=12)
    axes[0].tick_params(axis='x', rotation=45)
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        height = bar.get_height()
        axes[0].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}', ha='center', va='bottom', fontsize=10)

    # 2. 绘制R²子图
    r2_values = [metrics[model]['test']['R²'] for model in models]
    bars2 = axes[1].bar(models, r2_values, color=colors, edgecolor='black')
    axes[1].set_title('R²', fontsize=14)
    axes[1].set_ylabel('R²值', fontsize=12)
    axes[1].tick_params(axis='x', rotation=45)
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.4f}', ha='center', va='bottom', fontsize=10)

    # 3. 绘制MAPE子图
    mape_values = [metrics[model]['test']['MAPE (%)'] for model in models]
    bars3 = axes[2].bar(models, mape_values, color=colors, edgecolor='black')
    axes[2].set_title('MAPE (%)', fontsize=14)
    axes[2].set_ylabel('MAPE值', fontsize=12)
    axes[2].tick_params(axis='x', rotation=45)
    axes[2].grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars3:
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width() / 2., height,
                     f'{height:.2f}%', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "gan_results", "combined_metrics_comparison.png"),
                dpi=300, bbox_inches='tight')
    plt.close()


def plot_ddph_scatter(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值vs预测值散点图（包含MAPE信息）"""
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1

    plt.figure(figsize=(10, 8))
    # 训练集标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'train (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'test (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='ideal prediction')

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)

    plt.xlabel("true Vickers hardness（HV）", fontsize=12)
    plt.ylabel("predicted Vickers hardness（HV）", fontsize=12)
    plt.title(f"{model_name}model results comparison chart", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_results"), exist_ok=True)
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')
    plt.close()


def plot_loss_curves(critic_losses, actor_losses):
    """绘制训练损失曲线"""
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(critic_losses, label='Critic Loss')
    plt.title('Critic网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    plt.subplot(1, 2, 2)
    plt.plot(actor_losses, label='Actor Loss', color='orange')
    plt.title('Actor网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    plt.tight_layout()

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_results"), exist_ok=True)
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_results", "ddpg_losses.png"), dpi=300)
    plt.close()

def plot_ddph_gan_scatter(y_train, y_train_pred, y_test, y_test_pred, model_name, train_mape, test_mape):
    """绘制真实值vs预测值散点图（包含MAPE信息）"""
    all_vals = np.concatenate([y_train, y_train_pred, y_test, y_test_pred])
    min_val, max_val = all_vals.min() * 0.9, all_vals.max() * 1.1

    plt.figure(figsize=(10, 8))
    # 训练集标签添加MAPE
    plt.scatter(y_train, y_train_pred, c='gray', label=f'训练集 (MAPE: {train_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    # 测试集标签添加MAPE
    plt.scatter(y_test, y_test_pred, c='#FF69B4', label=f'测试集 (MAPE: {test_mape:.2f}%)',
                s=50, alpha=0.6, edgecolor='black')
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='理想预测')

    sns.kdeplot(x=y_train, y=y_train_pred, fill=True, cmap='Blues', alpha=0.3, levels=10)
    sns.kdeplot(x=y_test, y=y_test_pred, fill=True, cmap='Reds', alpha=0.3, levels=10)

    plt.xlabel("真实维氏硬度（HV）", fontsize=12)
    plt.ylabel("预测维氏硬度（HV）", fontsize=12)
    plt.title(f"{model_name}模型的真实值与预测值对比", fontsize=14)
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results"), exist_ok=True)
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results", f"{model_name}_对比图.png"),
                dpi=300, bbox_inches='tight')
    plt.close()


def plot_ganloss_curves(critic_losses, actor_losses):
    """绘制训练损失曲线"""
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(critic_losses, label='Critic Loss')
    plt.title('Critic网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    plt.subplot(1, 2, 2)
    plt.plot(actor_losses, label='Actor Loss', color='orange')
    plt.title('Actor网络损失')
    plt.xlabel('Epoch')
    plt.ylabel('损失值')
    plt.legend()
    plt.grid(linestyle='--', alpha=0.7)

    plt.tight_layout()

    os.makedirs(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results"), exist_ok=True)
    plt.savefig(os.path.join(config.BASE_DIR, "Image", "ddpg_gan_results", "ddpg_losses.png"), dpi=300)
    plt.close()

