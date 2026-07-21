# FORGE-HV

> **HGMX 高温合金机器学习实验台（论文对齐版 v3.1）**
> FORGE: FRamework for Optimizing superalloy GEneration

严格对照论文《基于深度确定性策略梯度的合金维氏硬度预测算法》裁剪，仅保留论文涉及的功能与算法。通过 **22 种元素成分 + 70 维 DINO-v2 微结构特征** 预测**维氏硬度（HV）**。

- 前端：`frontend/index.html`（浏览器打开即可，浅色主题）
- 后端：`app.py`（Flask 服务，端口 5000）

---

## 论文对齐说明

| 维度 | 论文章节 | 本项目实现 |
|---|---|---|
| 数据准备 | 第 2 章 | 149 条实测样本（70 微结构 + 22 成分 + 1 硬度），支持 Excel/CSV 导入 |
| 异常值检测 | 第 2 章公式(1)(2)(3) | 分位数截断（quantile_clip）+ IsolationForest / IQR / Z-score |
| DDPG 网络设计 | 第 3 章 | Actor-Critic 网络、优先经验回放、五段式奖励 |
| DDPG 训练策略 | 第 4 章 | 高斯噪声探索 + 异步训练 + 状态轮询 |
| 对比算法 | 第 5.1 节 | **严格 4 种**：LinearRegression / PolynomialRegression / SVR / DDPG |
| 评估指标 | 第 5.2 节 | **严格 4 个**：RMSE / MAE / R² / MAPE |
| 原始数据对比 | 第 5.3 节 | 4 算法在 149 条实测数据上的横向对比 |
| GAN 数据扩充对比 | 第 5.4 节 | 4 算法在 GAN 扩充数据上的横向对比 |

---

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11 |
| Python | 3.10+（conda 方式会自动装，无需手动装） |
| 浏览器 | Chrome / Edge（推荐最新版） |
| GPU | 可选（有 NVIDIA 显卡可启用 DDPG，无则自动 CPU） |

---

## 安装步骤（只需做一次）

项目根目录已内置依赖清单文件（类比 Maven 的 `pom.xml`）：

- `requirements.txt` — pip 依赖清单
- `environment.yml` — conda 环境定义（连 Python 一起装）
- `install.bat` — 交互式一键安装脚本

任选以下一种方式即可（**推荐方式 A 或 C**）：

### 方式 A：一键脚本（最简单，零配置）

双击运行 `install.bat`，按提示选择 `[1] pip` 或 `[2] conda`，脚本会自动用清华镜像装好全部依赖（含 PyTorch CPU 版）。

### 方式 B：pip 安装（需已有 Python 3.10+）

```bash
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

### 方式 C：conda 环境（推荐，最接近 Maven，连 Python 一起装）

先安装 Miniconda：https://docs.conda.io/en/latest/miniconda.html

```bash
conda env create -f environment.yml      # 创建环境 forge-hv（首次较慢）
conda activate forge-hv                   # 激活环境（以后每次用都要先激活）
```

### （可选）安装 PyTorch GPU 版

默认装的是 CPU 版 PyTorch，训练较慢。如需 GPU 加速，在装完上面依赖后单独执行：

```bash
nvidia-smi                               # 先看右上角 CUDA Version
pip install torch --index-url https://download.pytorch.org/whl/cu126 --force-reinstall
# CUDA 11.8 用 cu118，12.1 用 cu121，12.6 用 cu126
```

### 验证安装

```bash
python -c "import flask, sklearn, pandas, numpy; print('基础依赖 OK')"
python -c "import torch; print('PyTorch', torch.__version__, 'CUDA', torch.cuda.is_available())"
```

输出 `基础依赖 OK` 和 `PyTorch 2.x.x CUDA True/False` 即安装成功。

---

## 运行步骤（每次使用）

### 方式 A：PyCharm 运行（推荐）

1. 用 PyCharm 打开项目文件夹
2. 配置项目解释器：`File → Settings → Project → Python Interpreter` → 齿轮图标 → `Add` → `System Interpreter` → 选择 `E:\Miniconda\envs\forge-hv\python.exe`（conda 环境 forge-hv 的解释器，含全部依赖 + CUDA 版 PyTorch）
3. 打开 `app.py`，右键 → `Run 'app'`
4. 控制台出现 `Running on http://127.0.0.1:5000` 表示后端启动成功
5. 在文件树里找到 `frontend/index.html`，右键 → `Open in` → `Browser` → `Chrome`

### 方式 B：命令行运行（conda 环境）

```bash
# 激活 forge-hv 环境（每次使用都要先激活）
conda activate forge-hv
# 或免激活直接用: E:\Miniconda\envs\forge-hv\python.exe app.py

# 切到项目根目录后启动后端
python app.py
# 看到 "Running on http://127.0.0.1:5000" 后保持窗口不关
# 浏览器打开 frontend/index.html
```

---

## 页面结构（7 个功能页，严格对齐论文章节）

浏览器打开 `index.html` 后，左侧导航栏按论文章节分组：

| 页面 | 论文章节 | 功能 |
|---|---|---|
| 数据可视化 | 第 2 章 | 数据导入（Excel/CSV）+ 元素分布 + 硬度直方图 + 数据结构说明 |
| 异常值检测 | 第 2 章公式(1)(2)(3) | 分位数截断（quantile_clip）+ IsolationForest / IQR / Z-score |
| 元素相关性 | 第 2 章 | 22 种元素成分相关性矩阵（Pearson / Spearman / Kendall） |
| 数据库管理 | — | 结构化查询构建器（保留） |
| DDPG 训练 | 第 3-4 章 | Actor-Critic 异步训练 + 实时进度轮询 + 测试集散点图 |
| 5.3 硬度预测对比 | 第 5.3 节 | 原始 149 条数据：LR / PR / SVR / DDPG 横向对比 |
| 5.4 GAN 数据扩充对比 | 第 5.4 节 | GAN 扩充数据：LR / PR / SVR / DDPG 横向对比 |

**对比算法（论文 5.1 节，严格 4 种）**：
- LinearRegression（LR）
- PolynomialRegression（PR，二次多项式 + Ridge）
- SVR（支持向量回归，RBF 核）
- DDPG（深度确定性策略梯度）

**评估指标（论文 5.2 节，严格 4 个）**：
- RMSE — 均方根误差
- MAE — 平均绝对误差
- R² — 决定系数
- MAPE — 平均绝对百分比误差

训练后可点击"导出 CSV"下载预测结果，或"导出模型"下载 pkl 文件。

---

## 数据结构与导入

**数据集构成**（论文第 2 章）：
- 样本数：**149 条**实测合金数据
- 每条样本 = **70 维微结构特征**（DINO-v2 自监督模型提取 → PCA 降维）
            + **22 维成分特征**（Al/W/Ta/Ti/Cr/Ni/Mo/Hf/C/Co/B/V/Si/Fe/Nb/Zr/Re/Cb/Ce/Mn/S/P）
            + **1 维目标值**（维氏硬度 HV）
- GAN 扩充数据：10000 条生成样本（论文 5.4 节用）

**数据导入功能**：
- 在「数据可视化」页面点击「导入数据文件」按钮
- 支持 `.xlsx` / `.xls` / `.csv` 三种格式
- 文件必须包含目标列 `Vickers Hardness (HV)`（或含 hardness/HV 的列）
- 导入后自动切换数据源，点击「恢复默认数据」可切回原始 149 条数据

---

## 目录结构

```
FORGE-HV/
├── app.py                # 后端 Flask 服务（核心，1119 行，论文对齐版）
├── config.py             # 配置文件（22 元素列名、路径、模型参数）
├── CT_main.py            # GAN 数据加载与特征工程工具
├── run_all.py            # 一键流水线（可选）
├── plot_utils.py         # 绘图工具
├── DDPG.py               # DDPG 离线脚本
├── DDPG-gan.py           # DDPG+GAN 离线脚本
├── GAN-main.py           # GAN 离线脚本
├── README.md             # 项目说明文档（本文件）
├── requirements.txt      # pip 依赖清单
├── environment.yml       # conda 环境定义
├── install.bat           # 一键安装脚本
│
├── data/                 # 数据文件
│   ├── data.xlsx                  # 原始数据
│   ├── data_converted.xlsx        # 单位换算后
│   └── data_with_microstructure.xlsx  # 含微结构特征（后端读这个，149 条实测）
│
├── frontend/             # 前端代码（浅色主题 v3.1）
│   ├── index.html        # 页面结构（7 页面，643 行）
│   ├── app.js            # 交互逻辑（1065 行）
│   └── styles.css        # 浅色主题样式（1121 行）
│
├── generated_data/       # GAN 生成数据 + 用户上传数据
├── results/              # 输出结果
├── model/                # 模型保存
└── output/               # 其他输出
```

---

## 技术说明

| 项 | 内容 |
|---|---|
| 数据集 | 149 条实测高温合金样本 + 10000 条 GAN 生成样本 |
| 特征 | 22 元素成分 + 70 维 DINO-v2 微结构特征 = 92 维 |
| 目标 | 维氏硬度 HV（范围约 174~489，σ ≈ 62.4） |
| 对比算法 | LR / PR / SVR / DDPG（论文 5.1 节） |
| 评估指标 | RMSE / MAE / R² / MAPE（论文 5.2 节） |
| 前端主题 | 浅灰白底（#F7F8FA）+ 蓝色强调（#0A84FF），Apple/iOS 设计语言 |

---

## 常见问题

**Q：浏览器打开后页面显示"后端未启动"？**
A：后端 `app.py` 没运行。按"运行步骤"启动后端。

**Q：启动后端报错 `ModuleNotFoundError: No module named 'flask'`？**
A：依赖没装。按"安装步骤"重装，确认装到了正确的 Python/conda 环境。

**Q：DDPG 训练很慢？**
A：没有 GPU 会用 CPU 很慢。epochs 建议先设 500 试水，有 GPU 可设 2000+。前端默认 30s 超时，对比实验 DDPG 轮询最大等待 10 分钟。

**Q：5.3 / 5.4 对比实验 DDPG 卡在"训练中"？**
A：DDPG 是异步训练，前端会每 2 秒轮询一次状态，最大等待 10 分钟。若超时请检查后端控制台是否报错。

**Q：导入数据后怎么切回原始数据？**
A：在「数据可视化」页面点击「恢复默认数据」按钮，后端会重置数据源到 `data/data_with_microstructure.xlsx`。

**Q：端口 5000 被占用？**
A：修改 `app.py` 最后一行 `port=5000` 为其他端口（如 8080），同时修改 `frontend/app.js` 中 `API_BASE` 的端口。

---

## 依赖清单

| 包 | 最低版本 | 用途 |
|---|---|---|
| torch | 2.0.0 | 深度学习（DDPG 用，可选） |
| numpy | 1.24.0 | 数值计算 |
| pandas | 2.0.0 | 数据处理 |
| scikit-learn | 1.0.0 | 机器学习（LR/PR/SVR/IsolationForest） |
| matplotlib | 3.5.0 | 绘图（离线脚本用） |
| seaborn | 0.12.0 | 统计绘图（离线脚本用） |
| openpyxl | 3.0.0 | 读写 Excel |
| flask | 3.0.0 | Web 后端 |
| flask-cors | 4.0.0 | 跨域支持 |
| scipy | 1.10.0 | 科学计算 |
| joblib | 1.3.0 | 模型序列化 |

---

## License

MIT License — 他人可自由使用、修改、商业化，仅需保留版权声明。
