"""
config.py —— FORGE-HV 项目全局配置文件

本文件作用：
    - 集中定义整个项目使用的文件路径、模型参数、训练超参数与强化学习（RL）参数
    - 通过统一配置入口，保证各模块（app.py / CT_main.py / DDPG.py / DDPG-gan.py /
      GAN-main.py / run_all.py 等）引用一致的路径与参数，便于维护与移植

包含内容：
    1. 文件路径配置：原始数据、单位转换后数据、含微结构数据、GAN 生成数据、
       合并数据、预测结果与 PCA 对比结果输出路径
    2. 成分元素列名列表（22 种元素）
    3. 模型参数：元素种类数、学习率、批次大小、PCA 目标维度
    4. 训练参数：训练轮次、验证集比例、随机种子
    5. 输出文件路径：预测结果、PCA 对比结果
    6. 强化学习（DDPG）参数：成分调整步长、回合长度、训练轮次、经验回放、
       探索率衰减、优先级经验回放参数等

使用方式：
    其他模块通过 `from config import *` 或 `import config` 引用本文件中的常量
"""

import os

# ===================== 文件路径配置 =====================
# 基于本文件所在目录构造绝对路径，保证项目可移植（不依赖运行时工作目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 项目根目录绝对路径

# 微结构特征存放目录（由特征提取脚本生成，供 CT_main.py 等读取）
FEATURES_DIR = os.path.join(BASE_DIR, "Features")  # 微结构特征路径

# 原始数据文件（初始收集的高温合金成分-性能数据，未做单位统一）
DATA_FILE_ORIGINAL = os.path.join(BASE_DIR, "data", "data.xlsx")

# 单位统一后的初始数据（对 data.xlsx 做单位换算后得到，作为后续处理的基准）
DATA_FILE = os.path.join(BASE_DIR, "data", "data_converted.xlsx")  # （统一单位后）初始数据

# 将成分与微结构特征合并到一起后的初始数据（供模型训练直接使用）
DATA_FILE_MIC = os.path.join(BASE_DIR, "data", "data_with_microstructure.xlsx")  # 将成分与微结构放到一起后的初始数据

# GAN 生成的扩充数据路径（默认生成 10000 条样本，用于数据增强）
GENERATED_DATA_PATH = os.path.join(BASE_DIR, "generated_data", "gan_generated_data_10000.xlsx")

# 真实数据 + GAN 生成数据合并后的最终训练集路径
COMBINED_DATA_PATH = os.path.join(BASE_DIR, "generated_data", "combined_data.xlsx")

# 成分元素列名列表（共 22 种合金元素）
# 顺序与 data.xlsx / data_converted.xlsx 中的成分列保持一致
composition_columns = [
    'Al', 'W', 'Ta', 'Ti', 'Cr', 'Ni', 'Mo', 'Hf', 'C', 'Co',
    'B', 'V', 'Si', 'Fe', 'Nb', 'Zr', 'Re', 'Cb', 'Ce', 'Mn',
    'S', 'P'
]

# ===================== 模型参数 =====================
N_ELEM = 22  # 输入特征中的元素种类数（与 composition_columns 长度一致）
LEARNING_RATE = 1e-4  # 模型学习率（典型值 1e-3 ~ 1e-5，此处取较小值以保证训练稳定）
BATCH_SIZE = 32  # 训练批次大小（典型值 16 / 32 / 64）
PCA_TARGET_DIM = 70  # PCA 降维后的目标维度（用于特征压缩）

# ===================== 训练参数 =====================
EPOCHS = 500  # 训练轮次（增加轮次以保证模型充分收敛）
TEST_SIZE = 0.2  # 验证集比例（20% 数据用于验证，80% 用于训练）
RANDOM_STATE = 70  # 随机种子，保证实验可复现

# ===================== 输出文件 =====================
# 模型预测结果输出路径（由 app.py / CT_main.py 等写入）
OUTPUT_FILE = os.path.join(BASE_DIR, "results", "predictions.xlsx")

# ===================== PCA 对比实验配置 =====================
# 在config.py末尾添加
PCA_COMPONENTS = [47, 70, 140]  # 要测试的 PCA 维度列表（用于对比不同降维维度对模型效果的影响）
PCA_RESULTS_FILE = os.path.join(BASE_DIR, "results", "pca_comparison.xlsx")  # PCA 对比结果保存路径

# ===================== 强化学习（DDPG）参数 =====================
COMPOSITION_INTERVAL = 0.005  # 成分调整步长（每次动作改变的成分比例，典型值 0.001 ~ 0.01）
COMPOSITION_ROUNDUP_DIGITS = 4  # 成分保留小数位数（输出最终成分时的精度）
EPISODE_LEN = len(composition_columns) - 1  # 单回合需选择的元素数量（21 步：留 1 种元素作基准）
RL_TRAINING_EPOCHS = 1000  # RL 训练轮次（总回合数）
RL_SAMPLE_BATCH_SIZE = 128  # RL 采样批次大小（从经验回放中采样的样本数）
GAMMA = 0.9  # 折扣因子（越大越重视未来回报，典型值 0.9 ~ 0.99）
EPSILON_START = 0.9  # 初始探索率（ε-greedy 策略起始 ε，前期偏探索）
EPSILON_END = 0.1  # 最小探索率（ε 衰减下限，保证后期仍有一定探索）
EPSILON_DECAY = 0.995  # 探索率衰减率（每个回合 ε *= 0.995，逐步由探索转向利用）
PRIORITY_ALPHA = 0.6  # 优先级经验回放 α，控制优先级的影响程度（0~1，0 表示均匀采样）
PRIORITY_BETA = 0.4   # 优先级经验回放 β，控制重要性采样权重的影响程度（0~1，趋近 1 修正完全）
REPLAY_BUFFER_CAPACITY = 100000  # 经验回放缓冲区容量（存储 transition 的最大条数）
