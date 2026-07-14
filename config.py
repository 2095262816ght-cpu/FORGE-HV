# config.py
import os

# 文件路径配置（基于本文件所在目录，可移植）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEATURES_DIR = os.path.join(BASE_DIR, "Features") # 微结构特征路径
DATA_FILE_ORIGINAL = os.path.join(BASE_DIR, "data", "data.xlsx")
DATA_FILE = os.path.join(BASE_DIR, "data", "data_converted.xlsx") # （统一单位后）初始数据
DATA_FILE_MIC = os.path.join(BASE_DIR, "data", "data_with_microstructure.xlsx") # 将成分与微结构放到一起后的初始数据
GENERATED_DATA_PATH = os.path.join(BASE_DIR, "generated_data", "gan_generated_data_10000.xlsx")
COMBINED_DATA_PATH = os.path.join(BASE_DIR, "generated_data", "combined_data.xlsx")
composition_columns = [
    'Al', 'W', 'Ta', 'Ti', 'Cr', 'Ni', 'Mo', 'Hf', 'C', 'Co',
    'B', 'V', 'Si', 'Fe', 'Nb', 'Zr', 'Re', 'Cb', 'Ce', 'Mn',
    'S', 'P'
]
# 模型参数
N_ELEM = 22  # 输入特征中的元素种类数
LEARNING_RATE = 1e-4  # 降低学习率（关键修改）
BATCH_SIZE = 32
PCA_TARGET_DIM = 70
# 训练参数
EPOCHS = 500  # 增加训练轮次
TEST_SIZE = 0.2  # 验证集比例
RANDOM_STATE = 70

# 输出文件
OUTPUT_FILE = os.path.join(BASE_DIR, "results", "predictions.xlsx")

# 在config.py末尾添加
PCA_COMPONENTS = [47, 70, 140]  # 要测试的PCA维度列表
PCA_RESULTS_FILE = os.path.join(BASE_DIR, "results", "pca_comparison.xlsx")  # 结果保存路径

# RL参数
COMPOSITION_INTERVAL = 0.005  # 成分调整步长
COMPOSITION_ROUNDUP_DIGITS = 4  # 成分保留小数位数
EPISODE_LEN = len(composition_columns) - 1  # 需要选择的元素数量
RL_TRAINING_EPOCHS = 1000  # RL训练轮次
RL_SAMPLE_BATCH_SIZE = 128  # RL采样批次大小
GAMMA = 0.9  # 折扣因子
EPSILON_START = 0.9  # 初始探索率
EPSILON_END = 0.1  # 最小探索率
EPSILON_DECAY = 0.995  # 探索率衰减率
PRIORITY_ALPHA = 0.6  # 控制优先级的影响程度（0~1）
PRIORITY_BETA = 0.4   # 控制重要性采样权重的影响程度（0~1）
REPLAY_BUFFER_CAPACITY = 100000  # 经验回放缓冲区容量