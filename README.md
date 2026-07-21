# FORGE-HV

> **HGMX 高温合金机器学习实验台**
> FORGE: FRamework for Optimizing superalloy GEneration

通过 **22 种元素成分 + 70 维微结构特征** 预测**维氏硬度（HV）**，包含数据可视化、异常检测、特征工程、回归模型训练、模型比较、深度强化学习（DDPG）、主动学习优化等完整功能。

- 前端：`frontend/index.html`（浏览器打开即可）
- 后端：`app.py`（Flask 服务，端口 5000）

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
python -c "import flask, sklearn, pandas, numpy, xgboost; print('基础依赖 OK')"
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

## 使用流程

浏览器打开 `index.html` 后，左侧是导航栏。推荐按以下顺序体验：

| 模块 | 功能 |
|---|---|
| 数据可视化 | 查看元素分布、相关性矩阵 |
| 异常值检测 | IsolationForest 检测离群样本 |
| 数据库管理 | 可视化查询数据 |
| 特征相关性 | Pearson/Spearman 相关性 |
| 特征重要性 | 各元素对硬度的影响 |
| 聚类与降维 | PCA + K-Means 聚类 |
| 单一模型 | 训练单个回归模型（推荐 ExtraTrees + 特征筛选 importance + 目标变换 log） |
| 模型比较 | 横向对比多个算法 |
| 深度强化学习 | DDPG 异步训练（需 PyTorch） |
| 单目标优化 | 主动学习推荐新配方 |
| 代码优化 | 系统监控 + 参数推荐 |

训练后可点击"导出 CSV"下载预测结果，或"导出模型"下载 pkl 文件。

---

## 目录结构

```
FORGE-HV/
├── app.py                # 后端 Flask 服务（核心）
├── config.py             # 配置文件（路径、参数）
├── CT_main.py            # 离线训练脚本
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
│   └── data_with_microstructure.xlsx  # 含微结构特征（后端读这个）
│
├── frontend/             # 前端代码
│   ├── index.html        # 页面结构
│   ├── app.js            # 交互逻辑
│   └── styles.css        # 样式
│
├── generated_data/       # GAN 生成数据
├── results/              # 输出结果
├── model/                # 模型保存
└── output/               # 其他输出
```

---

## 技术说明

| 项 | 内容 |
|---|---|
| 数据集 | 149 条实测高温合金样本 |
| 特征 | 22 元素成分 + 70 维 DINO-v2 微结构特征 = 92 维 |
| 目标 | 维氏硬度 HV（范围约 160~500） |
| 最佳模型 | ExtraTrees + 特征筛选 Top30 + 目标 log 变换 |
| 测试集表现 | R² = 0.74，RMSE = 43 HV |

**支持的算法**：LinearRegression / Ridge / Lasso / BayesianRidge / HuberRegressor / PolynomialRegression / SVR(RBF/Linear) / RandomForest / ExtraTrees / GradientBoosting / AdaBoost / Bagging / MLP / XGBoost / Stacking / GaussianProcessRegressor / KernelRidge

---

## 常见问题

**Q：浏览器打开后页面显示"后端未启动"？**
A：后端 `app.py` 没运行。按"运行步骤"启动后端。

**Q：启动后端报错 `ModuleNotFoundError: No module named 'flask'`？**
A：依赖没装。按"安装步骤"重装，确认装到了正确的 Python/conda 环境。

**Q：DDPG 训练很慢？**
A：没有 GPU 会用 CPU 很慢。epochs 建议先设 500 试水，有 GPU 可设 2000+。

**Q：训练 R² 很低？**
A：开启"增强选项"面板，特征筛选选 `importance`，目标变换选 `log`，R² 可从 0.51 提升到 0.74。

**Q：端口 5000 被占用？**
A：修改 `app.py` 最后一行 `port=5000` 为其他端口（如 8080），同时修改 `frontend/app.js` 第 83 行 `API_BASE` 的端口。

**Q：怎么查看当前 R² 最高的模型？**
A：去"模型比较"页面训练一次，会自动列出各算法 R² 排名。

---

## 依赖清单

| 包 | 最低版本 | 用途 |
|---|---|---|
| torch | 2.0.0 | 深度学习（DDPG 用，可选） |
| numpy | 1.24.0 | 数值计算 |
| pandas | 2.0.0 | 数据处理 |
| scikit-learn | 1.0.0 | 机器学习 |
| matplotlib | 3.5.0 | 绘图（离线脚本用） |
| seaborn | 0.12.0 | 统计绘图（离线脚本用） |
| openpyxl | 3.0.0 | 读写 Excel |
| flask | 3.0.0 | Web 后端 |
| flask-cors | 4.0.0 | 跨域支持 |
| xgboost | 2.0.0 | XGBoost 算法 |
| scipy | 1.10.0 | 科学计算 |
| psutil | 5.9.0 | 系统监控 |
| joblib | 1.3.0 | 模型序列化 |
