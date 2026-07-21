"""
DDPG（Deep Deterministic Policy Gradient）深度强化学习离线训练脚本
================================================================

文件作用：
    FORGE-HV 项目的 DDPG 离线训练脚本，使用深度确定性策略梯度算法优化
    高温合金成分配方，目标是最大化预测硬度（Vickers Hardness, HV）。

核心功能：
    - 构建 Actor-Critic 神经网络架构对成分-硬度映射进行建模
    - Actor 输出动作（成分调整/硬度预测），Critic 评估动作价值
    - 通过经验回放、目标网络软更新、高斯噪声探索等机制稳定训练
    - 在验证集上以 R² 为指标保存最佳模型并支持早停

算法原理：
    DDPG 是一种面向连续动作空间的 Actor-Critic 深度强化学习算法：
    - Actor 网络 μ(s|θ^μ)：确定性策略，输入状态 s，输出连续动作 a
    - Critic 网络 Q(s,a|θ^Q)：动作价值函数，评估状态-动作对的回报
    - 目标网络软更新：θ_target ← τ·θ + (1-τ)·θ_target，提升训练稳定性
    - 优先经验回放（PER）：按 TD 误差大小采样，提升样本利用效率
    - 探索策略：在 Actor 输出上叠加高斯噪声实现探索-利用平衡

运行方式：
    python DDPG.py

输入输出：
    - 输入：Excel 数据文件（由 config.DATA_FILE_MIC 指定，含微观结构 + 成分 + 硬度）
    - 输出：最佳模型保存至 model/ddpg_best_model.pth
    - 输出：训练曲线与散点图保存至 Image/ddpg_results/
    - 输出：评估指标与预测结果保存至 results/ddpg_results/
"""

import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

import config
from plot_utils import plot_ddph_scatter, plot_loss_curves

# 设置随机种子确保可重复性（同时固定 torch 与 numpy 两条随机源）
torch.manual_seed(config.RANDOM_STATE)
np.random.seed(config.RANDOM_STATE)


class Actor(nn.Module):
    """
    Actor 策略网络（确定性策略）

    作用：输入状态（成分+微观特征），输出一个连续动作（硬度预测值）。
    网络结构：4 层全连接，使用 BatchNorm 加速收敛、LeakyReLU 缓解神经元死亡、
    Dropout 抑制过拟合，最后用 Tanh 将动作限制在 [-1, 1]（后续再缩放到真实硬度范围）。
    增强网络容量（hidden_dim=1024）以提升对复杂成分-硬度映射的表达能力。
    """

    def __init__(self, state_dim, action_dim, hidden_dim=1024):
        super(Actor, self).__init__()
        self.model = nn.Sequential(
            # 第1层：状态输入 → 1024 维，BatchNorm + LeakyReLU + Dropout
            nn.Linear(state_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.1),  # 降低dropout防止欠拟合

            # 第2层：1024 → 1024，保持大容量
            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.1),

            # 第3层：1024 → 512，逐步压缩特征
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.LeakyReLU(0.1),

            # 第4层：512 → 256，进一步压缩
            nn.Linear(hidden_dim // 2, hidden_dim // 4),
            nn.BatchNorm1d(hidden_dim // 4),
            nn.LeakyReLU(0.1),

            # 输出层：256 → action_dim，Tanh 将输出约束到 [-1,1] 便于动作缩放
            nn.Linear(hidden_dim // 4, action_dim),
            nn.Tanh()
        )

    def forward(self, x):
        return self.model(x)


class Critic(nn.Module):
    """
    Critic 价值网络（Q 函数）

    作用：评估"在状态 s 下采取动作 a"的价值 Q(s,a)。
    采用双路结构：状态网络与动作网络分别提取特征后拼接，再经合并网络输出标量 Q 值。
    这种结构使 Critic 能更好地学习状态-动作之间的交互关系。
    """

    def __init__(self, state_dim, action_dim, hidden_dim=512):
        super(Critic, self).__init__()
        # 状态网络：单独提取状态特征，输出 hidden_dim 维
        self.state_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),  # 降低dropout
        )
        # 动作网络：单独提取动作特征，输出 hidden_dim//2 维
        self.action_net = nn.Sequential(
            nn.Linear(action_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.ReLU()
        )
        # 合并网络：拼接状态与动作特征（hidden_dim + hidden_dim//2），输出 Q 值
        self.combined_net = nn.Sequential(
            nn.Linear(hidden_dim + hidden_dim // 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )

    def forward(self, state, action):
        state_features = self.state_net(state)
        action_features = self.action_net(action)
        # 沿特征维拼接两路特征，送入合并网络输出 Q 值
        combined = torch.cat([state_features, action_features], dim=1)
        return self.combined_net(combined)


class ReplayBuffer:
    """
    优先经验回放缓冲区（Prioritized Experience Replay, PER）

    作用：存储 (s, a, r, s', done) 转移样本，并按 TD 误差优先级采样。
    - alpha：优先级强度系数（0=均匀采样，1=完全按优先级），这里取 0.7 偏向优先级
    - beta：重要性采样权重修正系数，用于补偿优先采样带来的分布偏差
    - eps：避免优先级为 0 导致采样概率为 0 的小常数
    相比均匀采样，PER 让高 TD 误差（信息量大）的样本被更频繁地学习，加速收敛。
    """

    def __init__(self, capacity, alpha=0.7):  # 提高alpha增强优先级影响
        self.capacity = capacity
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)  # 存储每个样本的优先级
        self.position = 0  # 环形缓冲区的写入指针
        self.alpha = alpha
        self.eps = 1e-6

    def push(self, state, action, reward, next_state, done):
        """存入一条转移样本，新样本赋予当前最大优先级以保证至少被采样一次"""
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        max_prio = self.priorities.max() if self.buffer else 1.0
        self.priorities[self.position] = max_prio + self.eps
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = (self.position + 1) % self.capacity  # 环形覆盖旧样本

    def sample(self, batch_size, beta=0.5):
        """按优先级概率采样一个 batch，并返回重要性采样权重 weights 以修正偏差"""
        if len(self.buffer) < batch_size:
            return None

        prios = self.priorities[:len(self.buffer)]
        # 优先级概率：p_i = priority_i^alpha，再做归一化
        probs = prios ** self.alpha + self.eps
        probs_sum = probs.sum()
        if probs_sum == 0:
            probs = np.ones_like(probs) / len(probs)
        else:
            probs /= probs_sum

        # 按概率无放回采样；概率退化时回退到均匀采样
        try:
            indices = np.random.choice(len(self.buffer), batch_size, p=probs, replace=False)
        except ValueError:
            indices = np.random.choice(len(self.buffer), batch_size, replace=False)

        batch = [self.buffer[i] for i in indices]
        states, actions, rewards, next_states, dones = zip(*batch)

        # 重要性采样权重：w_i = (N·p_i)^(-beta)，并归一化到 [0,1]
        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights /= weights.max()

        return (
            np.stack(states),
            np.array(actions).reshape(-1, 1),
            np.array(rewards).reshape(-1, 1),
            np.stack(next_states),
            np.array(dones).reshape(-1, 1),
            indices,
            weights
        )

    def update_priorities(self, indices, priorities):
        """根据 TD 误差更新对应样本的优先级（误差越大优先级越高）"""
        priorities = np.clip(priorities, self.eps, None)
        for idx, prio in zip(indices, priorities):
            self.priorities[idx] = float(prio.item() if hasattr(prio, 'item') else prio) + self.eps

    def __len__(self):
        return len(self.buffer)


class DDPGRegressor:
    """
    DDPG 强化学习回归器

    封装完整的 DDPG 算法流程：动作选择（含噪声探索）、经验回放、Critic/Actor 更新、
    目标网络软更新等。在本项目中动作维度为 1（输出标准化后的硬度预测值）。
    """

    def __init__(self, state_dim, action_dim, device='cpu'):
        """初始化 Actor/Critic 主网络与目标网络、优化器、超参数"""
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device

        # 初始化网络：主网络 + 目标网络（DDPG 用目标网络稳定 Q 学习）
        self.actor = Actor(state_dim, action_dim).to(device)
        self.actor_target = Actor(state_dim, action_dim).to(device)
        self.critic = Critic(state_dim, action_dim).to(device)
        self.critic_target = Critic(state_dim, action_dim).to(device)

        # 复制权重到目标网络（初始时目标网络 = 主网络）
        self.actor_target.load_state_dict(self.actor.state_dict())
        self.critic_target.load_state_dict(self.critic.state_dict())

        # 优化器：AdamW + 较强权重衰减，抑制过拟合
        # Actor 学习率（1e-4）小于 Critic（5e-4），保证 Critic 先收敛以提供稳定的梯度方向
        # 在DDPG初始化中增加更强的权重衰减
        self.actor_optimizer = optim.AdamW(self.actor.parameters(), lr=1e-4, weight_decay=1e-3)
        self.critic_optimizer = optim.AdamW(self.critic.parameters(), lr=5e-4, weight_decay=1e-3)

        # 经验回放缓冲区（容量来自 config）
        self.replay_buffer = ReplayBuffer(capacity=config.REPLAY_BUFFER_CAPACITY)

        # 学习率调度器：StepLR 每 3000 步衰减为 0.97 倍，平缓衰减避免过早停滞
        self.actor_scheduler = optim.lr_scheduler.StepLR(self.actor_optimizer, step_size=3000, gamma=0.97)
        self.critic_scheduler = optim.lr_scheduler.StepLR(self.critic_optimizer, step_size=3000, gamma=0.97)

        # DDPG 核心超参数
        self.gamma = 0.995  # 折扣因子：取较大值以增强长期奖励影响
        self.tau = 0.001  # 目标网络软更新系数：取较小值减慢更新，提升稳定性
        self.batch_size = config.BATCH_SIZE
        # 高斯噪声探索参数（替代标准 DDPG 中的 OU 噪声）
        self.noise_std = 0.2
        self.noise_decay = 0.995  # 噪声标准差每步衰减为 0.995 倍
        self.min_noise_std = 0.05  # 噪声下限，避免后期完全失去探索能力
        self.exploration_steps = 5000  # 前5000步保持最大噪声

        # 动作缩放参数（用于将 [-1,1] 映射到真实硬度范围）
        self.action_min = None
        self.action_max = None

    def set_action_scaling(self, min_val, max_val):
        """设置动作缩放范围（真实硬度区间的最小/最大值）"""
        self.action_min = min_val
        self.action_max = max_val

    def scale_action(self, action):
        """将网络输出 [-1,1] 缩放到真实硬度区间 [min, max]"""
        return action * (self.action_max - self.action_min) / 2 + (self.action_max + self.action_min) / 2

    def unscale_action(self, action):
        """将真实硬度值反向缩放回 [-1,1]，用于存入经验回放缓冲区"""
        return 2 * (action - self.action_min) / (self.action_max - self.action_min) - 1

    def select_action(self, state, add_noise=True, epoch=0):
        """
        根据当前状态选择动作

        - 推理时关闭噪声；训练时叠加衰减的高斯噪声进行探索
        - 噪声标准差按 noise_decay 衰减，但不低于 min_noise_std
        - 输出动作经过 scale_action 映射到真实硬度区间
        """
        state = torch.FloatTensor(state).to(self.device).unsqueeze(0)

        # 推理阶段切换到 eval 模式（关闭 Dropout/BatchNorm 更新）
        self.actor.eval()
        with torch.no_grad():
            action = self.actor(state)
        self.actor.train()

        action = action.cpu().numpy().flatten()

        if add_noise:
            # 高斯噪声探索：噪声随训练逐步衰减，保留最低探索水平
            current_noise = max(self.noise_std, self.min_noise_std)
            noise = np.random.normal(0, current_noise, size=action.shape)
            action = np.clip(action + noise, -1, 1)
            self.noise_std *= self.noise_decay  # 衰减噪声标准差

        return self.scale_action(action)

    def update(self, beta=0.5):
        """
        DDPG 核心更新步骤

        流程：
        1) 从经验回放按优先级采样一批 (s, a, r, s', done)
        2) 用目标网络计算目标 Q 值：y = r + γ·Q'(s', μ'(s'))
        3) 更新 Critic：最小化 Huber 损失（带重要性采样权重）
        4) 更新 Actor：最大化 Critic 给出的 Q 值（即最小化 -Q(s, μ(s))）
        5) 软更新目标网络参数
        6) 更新学习率调度器
        """
        if len(self.replay_buffer) < self.batch_size:
            return 0, 0

        sample_data = self.replay_buffer.sample(self.batch_size, beta)
        if sample_data is None:
            return 0, 0

        states, actions, rewards, next_states, dones, indices, weights = sample_data

        # 转换为张量并送至设备
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        weights = torch.FloatTensor(weights).to(self.device)

        # === 第一步：更新 Critic ===
        with torch.no_grad():
            # 用目标 Actor 计算下一状态的动作
            next_actions = self.actor_target(next_states)
            # 增加动作噪声正则化（类似 TD3 的目标策略平滑），防止 Critic 对动作过拟合
            next_actions = next_actions + torch.clamp(torch.randn_like(next_actions) * 0.01, -0.02, 0.02)
            # 目标 Q 值：y = r + (1-done)·γ·Q'(s', a')
            target_q = rewards + (1 - dones) * self.gamma * self.critic_target(next_states, next_actions)

        current_q = self.critic(states, actions)
        td_errors = current_q - target_q  # TD 误差，用于更新优先级
        # 使用 Huber 损失（平滑 L1）减轻异常值对 Critic 的影响
        huber_loss = torch.where(td_errors.abs() < 1, 0.5 * td_errors ** 2, td_errors.abs() - 0.5)
        # 加入重要性采样权重，补偿 PER 的采样偏差
        critic_loss = (weights * huber_loss).mean()

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic.parameters(), 0.5)  # 梯度裁剪防止爆炸
        self.critic_optimizer.step()

        # 根据当前 TD 误差回写优先级（误差越大优先级越高）
        self.replay_buffer.update_priorities(indices, np.abs(td_errors.cpu().detach().numpy()) + 1e-6)

        # === 第二步：更新 Actor ===
        # Actor 目标：最大化 Critic 的 Q 值 → 最小化 -Q(s, μ(s))
        actor_loss = -self.critic(states, self.actor(states)).mean()
        # 加入 L2 正则化项，限制 Actor 权重规模，提升泛化能力
        l2_reg = torch.tensor(0., device=self.device)
        for param in self.actor.parameters():
            l2_reg += torch.norm(param)
        actor_loss += 1e-5 * l2_reg

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 0.5)
        self.actor_optimizer.step()

        # === 第三步：软更新目标网络 ===
        # θ_target ← τ·θ + (1-τ)·θ_target，τ 较小使目标网络缓慢跟随主网络
        for target_param, param in zip(self.actor_target.parameters(), self.actor.parameters()):
            target_param.data.copy_(target_param.data * (1.0 - self.tau) + param.data * self.tau)

        for target_param, param in zip(self.critic_target.parameters(), self.critic.parameters()):
            target_param.data.copy_(target_param.data * (1.0 - self.tau) + param.data * self.tau)

        # 推进学习率调度器
        self.actor_scheduler.step()
        self.critic_scheduler.step()

        return critic_loss.item(), actor_loss.item()


def load_data():
    """从 Excel 文件加载原始数据（微观结构 + 成分 + 硬度）"""
    gan_df = pd.read_excel(config.DATA_FILE_MIC)
    print(f"加载的数据量: {len(gan_df)}")
    return gan_df


def prepare_features(df):
    """
    准备特征矩阵 X 和目标变量 y

    特征构成：70 维微观结构特征（Micro_1..Micro_70）+ 成分列（来自 config.composition_columns）
    目标变量：Vickers Hardness (HV) 维氏硬度
    对 y 做分位数截断（1%~99%）以抑制极端异常值对训练的干扰。
    """
    micro_cols = [f"Micro_{i + 1}" for i in range(70)]
    feature_cols = micro_cols + config.composition_columns
    target_col = "Vickers Hardness (HV)"

    X = df[feature_cols].values
    y = df[target_col].values

    # 处理可能的异常值：用 1%~99% 分位数截断极端值
    y = np.clip(y, np.percentile(y, 1), np.percentile(y, 99))  # 截断极端值
    return X, y, feature_cols, target_col


def calculate_metrics(y_true, y_pred, dataset_name="数据集"):
    """
    计算回归评估指标

    返回 RMSE、MAE、R²、MAPE 四项指标。同时保留原始数值（*_value）与四舍五入版本，
    前者用于程序内部比较（如早停判断），后者用于展示与导出。
    MAPE 计算时过滤 y_true=0 的样本以避免除零。
    """
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)

    # 过滤 y_true=0 的样本以避免 MAPE 除零
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


def train_ddpg_regressor():
    """
    DDPG 回归器主训练流程

    步骤：
    1) 加载数据并准备特征/目标
    2) 三划分（训练/验证/测试）并做标准化
    3) 定义基于误差的奖励函数
    4) 初始化 DDPG 模型并设置动作缩放
    5) 训练循环：采样动作 → 计算奖励 → 写入经验回放 → 更新网络
    6) 每 10 轮在验证集上评估，保存最佳模型并支持早停
    7) 训练结束后加载最佳模型做最终评估与可视化
    """
    # 1. 加载数据
    gan_df = load_data()

    # 2. 准备特征和目标变量
    X, y, feature_cols, target_col = prepare_features(gan_df)

    # 3. 划分训练集和测试集，增加验证集（用于早停判断与模型选择）
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.15, random_state=config.RANDOM_STATE
    )

    # 4. 特征和目标变量标准化（训练集 fit，验证/测试集 transform 防止数据泄露）
    X_scaler = StandardScaler()
    y_scaler = StandardScaler()

    X_train_scaled = X_scaler.fit_transform(X_train)
    X_val_scaled = X_scaler.transform(X_val)
    X_test_scaled = X_scaler.transform(X_test)
    y_train_scaled = y_scaler.fit_transform(y_train.reshape(-1, 1)).flatten()
    y_val_scaled = y_scaler.transform(y_val.reshape(-1, 1)).flatten()
    y_test_scaled = y_scaler.transform(y_test.reshape(-1, 1)).flatten()

    # === 奖励函数设计 ===
    # 调整后的奖励函数：降低低误差样本的奖励权重
    # 思路：误差越小奖励越高；分段线性，避免过度拟合训练样本
    def calculate_reward(predicted, target):
        error = abs(predicted - target)

        # 绝对误差分段奖励：误差越小奖励权重越高（避免高奖励导致过拟合）
        if error < 0.05:
            reward = 5.0 * (1 - error / 0.05)  # 误差极小，奖励最高
        elif error < 0.1:
            reward = 3.0 * (1 - error / 0.1)
        elif error < 0.2:
            reward = 2.0 * (1 - error / 0.2)
        elif error < 0.5:
            reward = 1.0 * (1 - error / 0.5)
        else:
            reward = -1.0 * error  # 误差过大给负奖励（惩罚减轻以避免梯度爆炸）

        # 相对误差奖励：低相对误差额外加分，鼓励在硬度量级上接近真值
        if target != 0:
            relative_error = error / abs(target)
            if relative_error < 0.1:
                reward += 1.0 * (1 - relative_error / 0.1)

        return np.clip(reward, -5.0, 10.0)  # 限制奖励范围，稳定 Q 值估计

    # 初始化DDPG模型
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    state_dim = X_train_scaled.shape[1]  # 状态维度 = 微观特征数 + 成分数
    action_dim = 1  # 动作维度 = 1（输出标准化后的硬度预测值）

    ddpg = DDPGRegressor(state_dim, action_dim, device)

    # 设置动作缩放范围：以训练集标准化后的 y 区间为动作范围
    y_min = y_train_scaled.min()
    y_max = y_train_scaled.max()
    ddpg.set_action_scaling(y_min, y_max)

    # 训练模型 - 增加训练轮次和改进策略
    epochs = 2000  # 训练轮次（配合早停可提前结束）
    critic_losses = []
    actor_losses = []
    best_r2 = -np.inf  # 跟踪最佳R²（比 RMSE 更适合回归质量评估）
    early_stop_counter = 0
    early_stop_patience = 100  # 早停耐心：连续 100 次评估未提升则停止

    print(f"开始训练DDPG回归模型（设备：{device}）...")

    for epoch in range(epochs):
        total_critic_loss = 0
        total_actor_loss = 0
        batch_count = 0

        # 动态调整 beta 参数：PER 重要性采样权重从 0.4 线性增长到 1.0
        # 训练后期完全修正采样偏差，保证收敛到无偏估计
        beta = min(1.0, 0.4 + epoch * (1.0 - 0.4) / (epochs * 1.5))

        # 为每个训练样本生成经验（离线强化学习：将监督样本转为转移对）
        for i in range(len(X_train_scaled)):
            state = X_train_scaled[i]
            target = y_train_scaled[i]

            # 选择动作（含高斯噪声探索）
            action = ddpg.select_action(state, add_noise=True, epoch=epoch)
            # 基于预测值与真值的误差计算奖励
            reward = calculate_reward(action, target)

            # 状态转移设计：随机选择下一个状态增加经验多样性（避免时序耦合）
            next_idx = np.random.randint(len(X_train_scaled))
            next_state = X_train_scaled[next_idx]
            done = 1.0 if (i + 1) % 100 == 0 else 0.0  # 每100步标记一次 episode 结束

            # 存入经验回放缓冲区（动作需先反归一化到 [-1,1]）
            ddpg.replay_buffer.push(
                state,
                ddpg.unscale_action(action),
                reward,
                next_state,
                done
            )

        # 动态调整更新次数：随训练进展从 4 次线性增加到 32 次（提升样本利用率）
        update_iterations = min(32, 4 + epoch // 30)
        for _ in range(update_iterations):
            critic_loss, actor_loss = ddpg.update(beta=beta)
            if critic_loss > 0:
                total_critic_loss += critic_loss
                total_actor_loss += actor_loss
                batch_count += 1

        # 计算平均损失
        avg_critic_loss = total_critic_loss / batch_count if batch_count > 0 else 0
        avg_actor_loss = total_actor_loss / batch_count if batch_count > 0 else 0

        critic_losses.append(avg_critic_loss)
        actor_losses.append(avg_actor_loss)

        # 每10轮评估一次（关闭噪声，得到确定性预测）
        if (epoch + 1) % 10 == 0:
            # 在验证集上评估
            y_pred_val = np.array([ddpg.select_action(x, add_noise=False) for x in X_val_scaled])
            y_pred_val_original = y_scaler.inverse_transform(y_pred_val.reshape(-1, 1)).flatten()
            y_val_original = y_scaler.inverse_transform(y_val_scaled.reshape(-1, 1)).flatten()
            val_metrics = calculate_metrics(y_val_original, y_pred_val_original, "验证集")

            # 测试集评估
            y_pred_test = np.array([ddpg.select_action(x, add_noise=False) for x in X_test_scaled])
            y_pred_test_original = y_scaler.inverse_transform(y_pred_test.reshape(-1, 1)).flatten()
            y_test_original = y_scaler.inverse_transform(y_test_scaled.reshape(-1, 1)).flatten()
            test_metrics = calculate_metrics(y_test_original, y_pred_test_original, "测试集")

            print(f"Epoch [{epoch + 1}/{epochs}] | "
                  f"Critic Loss: {avg_critic_loss:.4f} | "
                  f"Actor Loss: {avg_actor_loss:.4f} | "
                  f"Val R²: {val_metrics['R²']} | "
                  f"Test R²: {test_metrics['R²']} | "
                  f"Noise STD: {ddpg.noise_std:.4f}")

            # 基于验证集 R² 保存最佳模型（同时保存 scalers 以便部署时反标准化）
            if val_metrics['R2_value'] > best_r2:
                best_r2 = val_metrics['R2_value']
                early_stop_counter = 0
                os.makedirs(os.path.join(config.BASE_DIR, "model"), exist_ok=True)
                torch.save({
                    'actor_state_dict': ddpg.actor.state_dict(),
                    'critic_state_dict': ddpg.critic.state_dict(),
                    'X_scaler': X_scaler,
                    'y_scaler': y_scaler
                }, os.path.join(config.BASE_DIR, "model", "ddpg_best_model.pth"))
            else:
                early_stop_counter += 1
                if early_stop_counter >= early_stop_patience:
                    print(f"早停机制触发！在第{epoch + 1}轮停止训练")
                    break

    # 最终评估：加载验证集上表现最好的 checkpoint
    print("\n最终模型评估:")
    checkpoint = torch.load(os.path.join(config.BASE_DIR, "model", "ddpg_best_model.pth"), weights_only=False)
    ddpg.actor.load_state_dict(checkpoint['actor_state_dict'])
    ddpg.critic.load_state_dict(checkpoint['critic_state_dict'])

    # 在三个子集上生成预测（关闭噪声）
    y_pred_train = np.array([ddpg.select_action(x, add_noise=False) for x in X_train_scaled])
    y_pred_val = np.array([ddpg.select_action(x, add_noise=False) for x in X_val_scaled])
    y_pred_test = np.array([ddpg.select_action(x, add_noise=False) for x in X_test_scaled])

    # 反标准化到原始硬度量纲
    y_pred_train_original = y_scaler.inverse_transform(y_pred_train.reshape(-1, 1)).flatten()
    y_pred_val_original = y_scaler.inverse_transform(y_pred_val.reshape(-1, 1)).flatten()
    y_pred_test_original = y_scaler.inverse_transform(y_pred_test.reshape(-1, 1)).flatten()
    y_train_original = y_scaler.inverse_transform(y_train_scaled.reshape(-1, 1)).flatten()
    y_val_original = y_scaler.inverse_transform(y_val_scaled.reshape(-1, 1)).flatten()
    y_test_original = y_scaler.inverse_transform(y_test_scaled.reshape(-1, 1)).flatten()

    metrics = {
        "train": calculate_metrics(y_train_original, y_pred_train_original, "训练集"),
        "val": calculate_metrics(y_val_original, y_pred_val_original, "验证集"),
        "test": calculate_metrics(y_test_original, y_pred_test_original, "测试集")
    }

    print(f"训练集 - R²: {metrics['train']['R²']}")
    print(f"验证集 - R²: {metrics['val']['R²']}")
    print(f"测试集 - R²: {metrics['test']['R²']}")

    # 绘制结果：损失曲线 + 真实/预测散点图
    plot_loss_curves(critic_losses, actor_losses)
    plot_ddph_scatter(y_train_original, y_pred_train_original,
                      y_test_original, y_pred_test_original, "DDPG",
                      metrics['train']['MAPE_value'], metrics['test']['MAPE_value'])

    # 保存评估指标与预测结果到 Excel
    save_results(metrics, y_test_original, y_pred_test_original)

    return ddpg, metrics, y_scaler


def save_results(metrics, y_test, y_pred_test):
    """
    保存评估结果到 Excel

    输出两个文件：
    - ddpg_model_metrics.xlsx：训练/验证/测试三集的 RMSE/MAE/R²/MAPE 指标
    - DDPG_预测结果.xlsx：测试集真实值、预测值与误差
    """
    results_dir = os.path.join(config.BASE_DIR, "results", "ddpg_results")
    os.makedirs(results_dir, exist_ok=True)

    # 汇总三集指标，附加模型名与数据集类型列
    results_df = pd.DataFrame([
        {**metrics['train'], '模型': 'DDPG', '数据集类型': '训练集'},
        {**metrics['val'], '模型': 'DDPG', '数据集类型': '验证集'},
        {**metrics['test'], '模型': 'DDPG', '数据集类型': '测试集'}
    ])

    # 按指定列顺序导出
    results_df = results_df[['模型', '数据集类型', 'RMSE (HV)', 'MAE (HV)', 'R²', 'MAPE (%)']]
    results_df.to_excel(os.path.join(results_dir, "ddpg_model_metrics.xlsx"), index=False)
    print(f"模型评估指标已保存至 {os.path.join(results_dir, 'ddpg_model_metrics.xlsx')}")

    # 保存测试集预测值与误差，便于后续分析
    pred_df = pd.DataFrame({
        '真实值': y_test,
        '预测值': y_pred_test,
        '误差': y_test - y_pred_test
    })
    pred_df.to_excel(os.path.join(results_dir, "DDPG_预测结果.xlsx"), index=False)
    print(f"DDPG模型预测结果已保存至 {os.path.join(results_dir, 'DDPG_预测结果.xlsx')}")


if __name__ == "__main__":
    # 脚本入口：执行训练并返回模型、指标与 y 标准化器
    model, metrics, y_scaler = train_ddpg_regressor()
    print("\nDDPG强化学习回归模型训练完成！")