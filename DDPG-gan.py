"""
DDPG + GAN 联合训练脚本
=======================

文件作用:
    本脚本是 FORGE-HV 项目中基于 DDPG(深度确定性策略梯度)强化学习算法,
    并结合 GAN(生成对抗网络)生成数据进行联合训练的回归模型脚本。
    用于高熵合金维氏硬度(HV)的成分配方优化与预测。

核心功能:
    1. 使用 GAN 生成的扩充数据作为训练样本,缓解原始数据量不足的问题
    2. 使用 DDPG 强化学习算法优化合金成分配方(状态=微观结构+成分,动作=硬度预测)
    3. 采用优先经验回放(PER)、目标网络软更新、Huber损失等机制提升训练稳定性
    4. 训练过程中动态调整探索噪声、学习率与beta参数

与 DDPG.py 的区别:
    - DDPG.py:仅使用原始真实数据训练
    - 本脚本(DDPG-gan.py):加入 GAN 生成的合成数据作为额外训练样本,
      通过 load_gan_data() 函数读取 GAN 生成数据并进行成分总和筛选,
      从而扩充训练集规模,提升模型泛化能力

运行方式:
    python DDPG-gan.py

输出:
    - 模型权重保存至: model/ddpg_best_model.pth
    - 评估指标保存至: results/ddpg_gan_results/ddpg_model_metrics.xlsx
    - 预测结果保存至: results/ddpg_gan_results/DDPG_预测结果.xlsx
    - 训练损失曲线和散点图由 plot_utils 自动绘制
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
from plot_utils import plot_ddph_gan_scatter, plot_ganloss_curves

# 设置随机种子确保可重复性
torch.manual_seed(config.RANDOM_STATE)
np.random.seed(config.RANDOM_STATE)


# 增强的网络结构 - 增加容量和表达能力
class Actor(nn.Module):
    """DDPG的Actor(演员)网络,根据状态输出动作(预测硬度值)"""

    def __init__(self, state_dim, action_dim, hidden_dim=1024):
        """初始化Actor网络结构

        Args:
            state_dim: 状态维度(输入特征数)
            action_dim: 动作维度(输出维度,本任务为1维硬度值)
            hidden_dim: 隐藏层神经元数,默认1024
        """
        super(Actor, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.1),  # 降低dropout防止欠拟合

            nn.Linear(hidden_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.1),

            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.LeakyReLU(0.1),

            nn.Linear(hidden_dim // 2, hidden_dim // 4),
            nn.BatchNorm1d(hidden_dim // 4),
            nn.LeakyReLU(0.1),

            nn.Linear(hidden_dim // 4, action_dim),
            nn.Tanh()  # Tanh将输出限制在[-1,1]区间,便于动作缩放
        )

    def forward(self, x):
        """前向传播:输入状态x,输出动作"""
        return self.model(x)


class Critic(nn.Module):
    """DDPG的Critic(评论家)网络,评估状态-动作对的价值Q(s,a)"""

    def __init__(self, state_dim, action_dim, hidden_dim=512):
        """初始化Critic网络结构,采用双流架构分别处理状态和动作

        Args:
            state_dim: 状态维度
            action_dim: 动作维度
            hidden_dim: 隐藏层神经元数,默认512
        """
        super(Critic, self).__init__()
        # 状态网络:提取状态特征
        self.state_net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),  # 降低dropout
        )
        # 动作网络:提取动作特征
        self.action_net = nn.Sequential(
            nn.Linear(action_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.ReLU()
        )
        # 合并网络:融合状态和动作特征,输出Q值
        self.combined_net = nn.Sequential(
            nn.Linear(hidden_dim + hidden_dim // 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )

    def forward(self, state, action):
        """前向传播:输入状态和动作,输出Q值

        Args:
            state: 状态张量
            action: 动作张量

        Returns:
            Q(s,a)价值张量
        """
        state_features = self.state_net(state)
        action_features = self.action_net(action)
        combined = torch.cat([state_features, action_features], dim=1)  # 拼接状态与动作特征
        return self.combined_net(combined)


# 优先经验回放缓冲区 - 优化采样策略
class ReplayBuffer:
    """优先经验回放缓冲区(Prioritized Experience Replay, PER)

    基于TD误差为经验样本分配优先级,优先采样高优先级样本,
    同时使用重要性采样权重修正偏差,提升训练效率。
    """

    def __init__(self, capacity, alpha=0.7):  # 提高alpha增强优先级影响
        """初始化缓冲区

        Args:
            capacity: 缓冲区容量
            alpha: 优先级强度系数,0为均匀采样,1为完全优先级采样
        """
        self.capacity = capacity
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.alpha = alpha
        self.eps = 1e-6  # 防止优先级为0的小常数

    def push(self, state, action, reward, next_state, done):
        """存入一条经验,新经验默认赋予最大优先级以保证至少被采样一次"""
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        max_prio = self.priorities.max() if self.buffer else 1.0
        self.priorities[self.position] = max_prio + self.eps
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = (self.position + 1) % self.capacity  # 环形覆盖旧经验

    def sample(self, batch_size, beta=0.5):
        """按优先级采样一个batch的经验

        Args:
            batch_size: 采样批量大小
            beta: 重要性采样权重系数,用于修正优先级采样带来的偏差

        Returns:
            包含states/actions/rewards/next_states/dones/indices/weights的元组
        """
        if len(self.buffer) < batch_size:
            return None

        prios = self.priorities[:len(self.buffer)]
        probs = prios ** self.alpha + self.eps  # 计算采样概率
        probs_sum = probs.sum()
        if probs_sum == 0:
            probs = np.ones_like(probs) / len(probs)
        else:
            probs /= probs_sum

        try:
            indices = np.random.choice(len(self.buffer), batch_size, p=probs, replace=False)
        except ValueError:
            # 概率归一化异常时退化为均匀采样
            indices = np.random.choice(len(self.buffer), batch_size, replace=False)

        batch = [self.buffer[i] for i in indices]
        states, actions, rewards, next_states, dones = zip(*batch)

        # 重要性采样权重,补偿优先级采样引入的偏差
        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights /= weights.max()  # 归一化权重

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
        """根据TD误差更新对应经验的优先级"""
        priorities = np.clip(priorities, self.eps, None)
        for idx, prio in zip(indices, priorities):
            self.priorities[idx] = float(prio.item() if hasattr(prio, 'item') else prio) + self.eps

    def __len__(self):
        """返回当前缓冲区中经验条数"""
        return len(self.buffer)


class DDPGRegressor:
    """DDPG回归器:封装Actor-Critic网络、经验回放、训练更新等完整DDPG流程

    本类将DDPG强化学习算法适配为回归任务:状态=特征向量,动作=预测硬度值,
    奖励=基于预测误差的反馈信号,通过强化学习训练优化Actor网络输出准确的硬度预测。
    """

    def __init__(self, state_dim, action_dim, device='cpu'):
        """初始化DDPG回归器

        Args:
            state_dim: 状态维度(特征数)
            action_dim: 动作维度(本任务为1)
            device: 训练设备('cpu'或'cuda')
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device

        # 初始化网络:Actor和Critic各两个(主网络+目标网络)
        self.actor = Actor(state_dim, action_dim).to(device)
        self.actor_target = Actor(state_dim, action_dim).to(device)
        self.critic = Critic(state_dim, action_dim).to(device)
        self.critic_target = Critic(state_dim, action_dim).to(device)

        # 复制权重到目标网络,保证初始时刻主网络与目标网络一致
        self.actor_target.load_state_dict(self.actor.state_dict())
        self.critic_target.load_state_dict(self.critic.state_dict())

        # 优化器 - 调整学习率
        # 在DDPG初始化中增加更强的权重衰减
        self.actor_optimizer = optim.AdamW(self.actor.parameters(), lr=1e-4, weight_decay=1e-3)
        self.critic_optimizer = optim.AdamW(self.critic.parameters(), lr=5e-4, weight_decay=1e-3)

        # 经验回放缓冲区
        self.replay_buffer = ReplayBuffer(capacity=config.REPLAY_BUFFER_CAPACITY)

        # 学习率调度器 - 更平缓的衰减
        self.actor_scheduler = optim.lr_scheduler.StepLR(self.actor_optimizer, step_size=3000, gamma=0.97)
        self.critic_scheduler = optim.lr_scheduler.StepLR(self.critic_optimizer, step_size=3000, gamma=0.97)

        # 超参数调整
        self.gamma = 0.995  # 提高gamma增强长期奖励影响
        self.tau = 0.001  # 减慢目标网络更新
        self.batch_size = config.BATCH_SIZE
        self.noise_std = 0.2
        self.noise_decay = 0.995  # 减缓噪声衰减速度
        self.min_noise_std = 0.05  # 提高最小噪声水平
        self.exploration_steps = 5000  # 前5000步保持最大噪声

        # 动作缩放参数
        self.action_min = None
        self.action_max = None

    def set_action_scaling(self, min_val, max_val):
        """设置动作缩放范围,将网络输出[-1,1]映射到真实硬度值区间"""
        self.action_min = min_val
        self.action_max = max_val

    def scale_action(self, action):
        """将归一化动作[-1,1]缩放到真实硬度值区间[min,max]"""
        return action * (self.action_max - self.action_min) / 2 + (self.action_max + self.action_min) / 2

    def unscale_action(self, action):
        """将真实硬度值反缩放回[-1,1]区间,用于存入经验回放缓冲区"""
        return 2 * (action - self.action_min) / (self.action_max - self.action_min) - 1

    def select_action(self, state, add_noise=True, epoch=0):
        """根据状态选择动作(预测硬度值)

        Args:
            state: 输入状态特征
            add_noise: 是否添加探索噪声(训练时为True,评估时为False)
            epoch: 当前训练轮次(用于调整噪声强度)

        Returns:
            缩放后的真实硬度预测值
        """
        state = torch.FloatTensor(state).to(self.device).unsqueeze(0)

        self.actor.eval()
        with torch.no_grad():
            action = self.actor(state)
        self.actor.train()

        action = action.cpu().numpy().flatten()

        if add_noise:
            # 添加高斯噪声进行探索,并逐步衰减噪声强度
            current_noise = max(self.noise_std, self.min_noise_std)
            noise = np.random.normal(0, current_noise, size=action.shape)
            action = np.clip(action + noise, -1, 1)
            self.noise_std *= self.noise_decay

        return self.scale_action(action)

    def update(self, beta=0.5):
        """执行一次DDPG网络更新(优先经验回放采样+Critic更新+Actor更新+目标网络软更新)

        Args:
            beta: 重要性采样权重系数

        Returns:
            (critic_loss, actor_loss) 损失值元组,缓冲区不足时返回(0,0)
        """
        if len(self.replay_buffer) < self.batch_size:
            return 0, 0

        sample_data = self.replay_buffer.sample(self.batch_size, beta)
        if sample_data is None:
            return 0, 0

        states, actions, rewards, next_states, dones, indices, weights = sample_data

        # 转换为张量
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)
        weights = torch.FloatTensor(weights).to(self.device)

        # 更新Critic - 增加平滑项
        with torch.no_grad():
            next_actions = self.actor_target(next_states)
            # 增加动作噪声正则化,提升目标Q值的稳定性
            next_actions = next_actions + torch.clamp(torch.randn_like(next_actions) * 0.01, -0.02, 0.02)
            target_q = rewards + (1 - dones) * self.gamma * self.critic_target(next_states, next_actions)

        current_q = self.critic(states, actions)
        td_errors = current_q - target_q  # 时序差分误差
        # 增加Huber损失减轻异常值影响
        huber_loss = torch.where(td_errors.abs() < 1, 0.5 * td_errors ** 2, td_errors.abs() - 0.5)
        critic_loss = (weights * huber_loss).mean()  # 加权Huber损失

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic.parameters(), 0.5)  # 调整梯度裁剪
        self.critic_optimizer.step()

        # 更新优先级:用TD误差绝对值作为新的优先级
        self.replay_buffer.update_priorities(indices, np.abs(td_errors.cpu().detach().numpy()) + 1e-6)

        # 更新Actor:目标是最大化Critic输出的Q值
        actor_loss = -self.critic(states, self.actor(states)).mean()
        # 增加L2正则化项,防止Actor权重过大
        l2_reg = torch.tensor(0., device=self.device)
        for param in self.actor.parameters():
            l2_reg += torch.norm(param)
        actor_loss += 1e-5 * l2_reg

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 0.5)
        self.actor_optimizer.step()

        # 软更新目标网络:以tau比例融合主网络权重,保持目标网络缓慢跟踪主网络
        for target_param, param in zip(self.actor_target.parameters(), self.actor.parameters()):
            target_param.data.copy_(target_param.data * (1.0 - self.tau) + param.data * self.tau)

        for target_param, param in zip(self.critic_target.parameters(), self.critic.parameters()):
            target_param.data.copy_(target_param.data * (1.0 - self.tau) + param.data * self.tau)

        self.actor_scheduler.step()
        self.critic_scheduler.step()

        return critic_loss.item(), actor_loss.item()


def load_gan_data():
    """加载并筛选GAN生成的数据

    GAN+DDPG联合训练的关键步骤之一:从config.COMBINED_DATA_PATH读取
    GAN生成的扩充数据,并根据成分总和(应在100附近)筛选有效样本,
    剔除成分配比不合理的GAN生成数据。
    """
    # 加载GAN生成的数据
    gan_df = pd.read_excel(config.COMBINED_DATA_PATH)
    print(f"通过GAN生成的数据量: {len(gan_df)}")

    # 筛选成分总和在100左右的样本（±1误差范围）
    composition_sum = gan_df[config.composition_columns].sum(axis=1)
    valid_mask = (composition_sum >= 90) & (composition_sum <= 110)  # 容忍±10的偏差
    filtered_df = gan_df[valid_mask].copy()

    print(f"筛选后的数据量: {len(filtered_df)}")
    print(f"成分总和范围: [{filtered_df[config.composition_columns].sum(axis=1).min():.4f}, "
          f"{filtered_df[config.composition_columns].sum(axis=1).max():.4f}]")

    return filtered_df



def prepare_features(df):
    """准备数据的特征和目标变量

    Args:
        df: 输入数据DataFrame

    Returns:
        X: 特征矩阵(70维微观结构特征 + 成分特征)
        y: 目标变量(维氏硬度)
        feature_cols: 特征列名列表
        target_col: 目标列名
    """
    micro_cols = [f"Micro_{i + 1}" for i in range(70)]
    feature_cols = micro_cols + config.composition_columns  # 微观结构特征 + 成分特征
    target_col = "Vickers Hardness (HV)"

    X = df[feature_cols].values
    y = df[target_col].values

    # 处理可能的异常值
    y = np.clip(y, np.percentile(y, 1), np.percentile(y, 99))  # 截断极端值
    return X, y, feature_cols, target_col


def calculate_metrics(y_true, y_pred, dataset_name="数据集"):
    """计算回归评估指标(RMSE/MAE/R²/MAPE)

    Args:
        y_true: 真实值
        y_pred: 预测值
        dataset_name: 数据集名称(用于结果展示)

    Returns:
        包含各项指标的字典,同时保留原始值和四舍五入值
    """
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)

    # 计算MAPE时过滤零值,避免除零错误
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
    """DDPG+GAN联合训练主流程

    完整训练流程:
        1. 加载GAN生成的扩充数据
        2. 准备特征与目标变量,划分训练/验证/测试集
        3. 标准化特征与目标
        4. 定义基于预测误差的奖励函数
        5. 初始化DDPG模型并设置动作缩放
        6. 迭代训练:采样经验→更新网络→评估→保存最佳模型
        7. 最终评估并保存结果

    Returns:
        model: 训练好的DDPG模型
        metrics: 各数据集评估指标
        y_scaler: 目标变量标准化器
    """
    # 1. 加载GAN生成的数据(与DDPG.py的核心区别:使用GAN扩充数据)
    gan_df = load_gan_data()

    # 2. 准备特征和目标变量
    X, y, feature_cols, target_col = prepare_features(gan_df)

    # 3. 划分训练集和测试集，增加验证集
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.15, random_state=config.RANDOM_STATE
    )

    # 4. 特征和目标变量标准化
    X_scaler = StandardScaler()
    y_scaler = StandardScaler()

    X_train_scaled = X_scaler.fit_transform(X_train)
    X_val_scaled = X_scaler.transform(X_val)
    X_test_scaled = X_scaler.transform(X_test)
    y_train_scaled = y_scaler.fit_transform(y_train.reshape(-1, 1)).flatten()
    y_val_scaled = y_scaler.transform(y_val.reshape(-1, 1)).flatten()
    y_test_scaled = y_scaler.transform(y_test.reshape(-1, 1)).flatten()

    # 调整后的奖励函数：降低低误差样本的奖励权重
    def calculate_reward(predicted, target):
        """基于预测误差计算奖励值(分层奖励+相对误差奖励)"""
        error = abs(predicted - target)

        # 降低奖励权重，避免过度拟合
        if error < 0.05:
            reward = 5.0 * (1 - error / 0.05)  # 降低高奖励权重
        elif error < 0.1:
            reward = 3.0 * (1 - error / 0.1)
        elif error < 0.2:
            reward = 2.0 * (1 - error / 0.2)
        elif error < 0.5:
            reward = 1.0 * (1 - error / 0.5)
        else:
            reward = -1.0 * error  # 减轻惩罚

        # 相对误差奖励也降低权重
        if target != 0:
            relative_error = error / abs(target)
            if relative_error < 0.1:
                reward += 1.0 * (1 - relative_error / 0.1)

        return np.clip(reward, -5.0, 10.0)  # 缩小奖励范围

    # 初始化DDPG模型
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    state_dim = X_train_scaled.shape[1]
    action_dim = 1  # 动作维度为1(硬度预测值)

    ddpg = DDPGRegressor(state_dim, action_dim, device)

    # 设置动作缩放范围:Actor网络输出[-1,1]需映射到标准化后的硬度范围
    y_min = y_train_scaled.min()
    y_max = y_train_scaled.max()
    ddpg.set_action_scaling(y_min, y_max)

    # 训练模型 - 增加训练轮次和改进策略
    epochs = 2000  # 增加训练轮次
    critic_losses = []
    actor_losses = []
    best_r2 = -np.inf  # 跟踪最佳R²而不是RMSE
    early_stop_counter = 0
    early_stop_patience = 100  # 增加早停耐心

    print(f"开始训练DDPG回归模型（设备：{device}）...")

    for epoch in range(epochs):
        total_critic_loss = 0
        total_actor_loss = 0
        batch_count = 0

        # 动态调整beta参数（更平缓的增长）
        # beta控制重要性采样权重强度,从0.4线性增长到1.0
        beta = min(1.0, 0.4 + epoch * (1.0 - 0.4) / (epochs * 1.5))

        # 为每个训练样本生成经验(将GAN扩充数据全部转化为强化学习经验)
        for i in range(len(X_train_scaled)):
            state = X_train_scaled[i]
            target = y_train_scaled[i]

            # 选择动作(带探索噪声)
            action = ddpg.select_action(state, add_noise=True, epoch=epoch)
            reward = calculate_reward(action, target)  # 计算即时奖励

            # 改进状态转移 - 随机选择下一个状态增加多样性
            next_idx = np.random.randint(len(X_train_scaled))
            next_state = X_train_scaled[next_idx]
            done = 1.0 if (i + 1) % 100 == 0 else 0.0  # 每100步标记一次结束

            # 将经验(反缩放后的动作)存入优先经验回放缓冲区
            ddpg.replay_buffer.push(
                state,
                ddpg.unscale_action(action),
                reward,
                next_state,
                done
            )

        # 动态调整更新次数 - 随训练进展增加
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

        # 每10轮评估一次
        if (epoch + 1) % 10 == 0:
            # 在验证集上评估(关闭探索噪声)
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

            # 基于验证集R²保存最佳模型(早停机制)
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

    # 最终评估:加载验证集上表现最好的模型
    print("\n最终模型评估:")
    checkpoint = torch.load(os.path.join(config.BASE_DIR, "model", "ddpg_best_model.pth"), weights_only=False)
    ddpg.actor.load_state_dict(checkpoint['actor_state_dict'])
    ddpg.critic.load_state_dict(checkpoint['critic_state_dict'])

    # 生成预测(三个数据集都进行预测,关闭探索噪声)
    y_pred_train = np.array([ddpg.select_action(x, add_noise=False) for x in X_train_scaled])
    y_pred_val = np.array([ddpg.select_action(x, add_noise=False) for x in X_val_scaled])
    y_pred_test = np.array([ddpg.select_action(x, add_noise=False) for x in X_test_scaled])

    # 反标准化:将标准化后的预测值还原为原始硬度值
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

    # 绘制结果:损失曲线和真实-预测散点图
    plot_ganloss_curves(critic_losses, actor_losses)
    plot_ddph_gan_scatter(y_train_original, y_pred_train_original,
                      y_test_original, y_pred_test_original, "DDPG",
                      metrics['train']['MAPE_value'], metrics['test']['MAPE_value'])

    # 保存结果
    save_results(metrics, y_test_original, y_pred_test_original)

    return ddpg, metrics, y_scaler


def save_results(metrics, y_test, y_pred_test):
    """保存模型评估指标和预测结果到Excel文件

    Args:
        metrics: 各数据集评估指标字典
        y_test: 测试集真实值
        y_pred_test: 测试集预测值
    """
    results_dir = os.path.join(config.BASE_DIR, "results", "ddpg_gan_results")
    os.makedirs(results_dir, exist_ok=True)

    # 汇总三个数据集的评估指标
    results_df = pd.DataFrame([
        {**metrics['train'], '模型': 'DDPG', '数据集类型': '训练集'},
        {**metrics['val'], '模型': 'DDPG', '数据集类型': '验证集'},
        {**metrics['test'], '模型': 'DDPG', '数据集类型': '测试集'}
    ])

    results_df = results_df[['模型', '数据集类型', 'RMSE (HV)', 'MAE (HV)', 'R²', 'MAPE (%)']]
    results_df.to_excel(os.path.join(results_dir, "ddpg_model_metrics.xlsx"), index=False)
    print(f"模型评估指标已保存至 {os.path.join(results_dir, 'ddpg_model_metrics.xlsx')}")

    # 保存测试集预测结果(真实值/预测值/误差)
    pred_df = pd.DataFrame({
        '真实值': y_test,
        '预测值': y_pred_test,
        '误差': y_test - y_pred_test
    })
    pred_df.to_excel(os.path.join(results_dir, "DDPG_预测结果.xlsx"), index=False)
    print(f"DDPG模型预测结果已保存至 {os.path.join(results_dir, 'DDPG_预测结果.xlsx')}")


if __name__ == "__main__":
    # 程序入口:执行DDPG+GAN联合训练
    model, metrics, y_scaler = train_ddpg_regressor()
    print("\nDDPG强化学习回归模型训练完成！")