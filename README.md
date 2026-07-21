# FORGE-HV

> **HGMX 高温合金机器学习实验台（论文对齐版 v3.2 · 含系统管理）**
> FORGE: FRamework for Optimizing superalloy GEneration

严格对照论文《基于深度确定性策略梯度的合金维氏硬度预测算法》裁剪，仅保留论文涉及的功能与算法。通过 **22 种元素成分 + 70 维 DINO-v2 微结构特征** 预测**维氏硬度（HV）**。v3.2 在论文对齐版基础上新增**用户系统、数据管理、历史记录、系统设置**四大基础模块。

- 前端：`frontend/index.html`（浏览器打开即可，浅色主题，11 个页面）
- 后端：`app.py`（Flask 服务，端口 5000，含 SQLite + JWT 鉴权）

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

## 页面结构（11 个功能页 = 7 论文页 + 4 系统管理页）

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
| **数据管理** | 系统管理 | 行级录入 / 批量导入 / 查询 / 修改 / 删除 / 导出 / 数据分析 |
| **历史记录** | 系统管理 | 训练任务自动落库 + 按算法/数据源/时间筛选 + 导出 CSV |
| **用户管理** | 系统管理 | 仅管理员可见：新建用户 / 角色分配 / 重置密码 / 删除账号 |
| **系统设置** | 系统管理 | 站点标题 / 默认数据源 / 上传限制 / 历史保留天数 / 游客开关 |

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

训练后可点击"导出 CSV"下载预测结果，或"导出模型"下载 pkl 文件。所有训练任务会**自动写入历史记录**（含算法、数据源、指标、样本数、耗时、状态）。

---

## 用户系统与权限（v3.2 新增）

**默认管理员账号**：`admin` / `admin123`（首次启动后端时自动创建）

- **鉴权方式**：本地账号 + JWT（HS256，24 小时过期），token 存浏览器 localStorage
- **密码安全**：SHA-256 + 随机 16 字节 salt（演示级，生产环境建议换 bcrypt）
- **三种角色**：
  - `admin`（管理员）— 可访问全部 11 页面，可管理用户、修改系统设置、删除历史记录
  - `user`（普通用户）— 可访问 10 页面（无用户管理），可训练/导入/增删改数据，不能改系统设置
  - `guest`（游客）— **只读模式**，仅可查看数据/图表/历史，不能训练/导入/增删改/管理
- **游客模式开关**：管理员在「系统设置」页将「允许游客浏览」设为"是"后，登录页会显示「👤 以游客身份浏览」按钮，访客点击即可无密码进入只读模式
- **数据库**：SQLite，文件 `forge.db`（项目根目录，首次运行自动创建，**不提交到 Git**）
- **登录流程**：
  1. 浏览器打开 `index.html`，未登录时显示全屏登录覆盖层
  2. 三种进入方式：
     - 输入用户名/密码 → `/api/auth/login` → 返回 JWT
     - 点击「游客访问」按钮 → `/api/auth/guest` → 返回游客 JWT（仅当管理员开启时）
     - 已登录过且 token 未过期 → 自动进入
  3. 前端将 token 存入 localStorage，后续所有 API 自动附加 `Authorization: Bearer <token>`
  4. token 过期或无效 → 自动触发 `auth:unauthorized` 事件 → 跳回登录页
- **权限拦截**：后端 `@login_required(admin_only, guest_allowed)` 装饰器三层校验；前端 `applyGuestRestrictions()` 在进入页面时禁用写入按钮
- **修改密码**：顶栏右上角头像 → 修改密码（弹窗输入原密码 + 新密码）
- **退出登录**：顶栏右上角头像 → 退出登录（清空 localStorage，显示登录页）

### 游客模式权限对照表

| 操作 | 游客 | 普通用户 | 管理员 |
|---|:---:|:---:|:---:|
| 查看数据可视化 / 元素相关性 / 异常值图表 | ✅ | ✅ | ✅ |
| 查看数据库管理 / 数据管理列表 / 数据分析 | ✅ | ✅ | ✅ |
| 查看历史记录 / 导出历史 CSV | ✅ | ✅ | ✅ |
| 查看系统设置（只读） | ✅ | ✅ | ✅ |
| 导出训练结果 CSV / 导出当前数据 Excel | ✅ | ✅ | ✅ |
| 导入数据文件 / 恢复默认数据 | ❌ | ✅ | ✅ |
| 数据管理：新增/编辑/删除/批量导入 | ❌ | ✅ | ✅ |
| 异常值检测运行 / DDPG 训练 / 5.3 5.4 对比 | ❌ | ✅ | ✅ |
| 导出模型 pkl | ❌ | ✅ | ✅ |
| 修改密码 | ❌（无密码） | ✅ | ✅ |
| 修改系统设置 / 开关游客模式 | ❌ | ❌ | ✅ |
| 用户管理（增删改） | ❌ | ❌ | ✅ |
| 删除历史记录 | ❌ | ❌ | ✅ |

---

## 数据管理与历史记录（v3.2 新增）

**数据管理页**（系统管理 → 数据管理）：
- 新增一行：弹窗输入各列值（自动识别 92 个特征列 + 目标列）
- 批量导入：上传 Excel/CSV，自动按列名对齐追加到当前数据源
- 查询：关键词搜索（任意列包含）+ 按列排序 + 分页（每页 20 条）
- 修改 / 删除：每行操作列提供「编辑」「删除」按钮
- 导出：一键导出当前数据为 Excel（.xlsx）或 CSV
- 数据分析：点击后展示 HV 分布直方图 + 元素相关性 Top 10 + 各列统计表（min/max/mean/std/median/Q1/Q3）

**历史记录页**（系统管理 → 历史记录）：
- 所有训练任务（`/api/train/traditional`、`/api/train/compare`）成功完成后自动落库
- 记录字段：ID、时间、用户、任务类型、算法、数据源、样本数、R²、RMSE、MAE、MAPE、状态
- 筛选：按算法（LR/PR/SVR/DDPG）+ 按数据源（real/gan/gan_train_real_test）+ 按日期范围
- 导出：一键导出筛选结果为 CSV
- 管理员可删除任意历史记录

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
├── app.py                # 后端 Flask 服务（核心，~1900 行，含 SQLite + JWT 鉴权）
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
├── .gitignore            # 忽略 forge.db / __pycache__ / uploads/ 等
│
├── data/                 # 数据文件
│   ├── data.xlsx                  # 原始数据
│   ├── data_converted.xlsx        # 单位换算后
│   └── data_with_microstructure.xlsx  # 含微结构特征（后端读这个，149 条实测）
│
├── frontend/             # 前端代码（浅色主题 v3.2 · 11 页面）
│   ├── index.html        # 页面结构（983 行）
│   ├── app.js            # 交互逻辑（1561 行，含鉴权 + 4 系统页）
│   └── styles.css        # 浅色主题样式（1541 行，含登录/modals/user-menu）
│
├── Paper/                # 论文文档（Markdown 版）
│   ├── paper.md          # 论文正文（与原 Word 内容一致）
│   └── images/           # 论文图片（70 张真 PNG）
│
├── generated_data/       # GAN 生成数据 + 用户上传数据
├── results/              # 输出结果
├── model/                # 模型保存
└── output/               # 其他输出

# 运行时生成（不提交）
└── forge.db              # SQLite 数据库（users / history / settings 三表）
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

**Q：忘记 admin 密码怎么办？**
A：停止后端，删除项目根目录下的 `forge.db` 文件，重启后端会自动重建默认管理员 `admin / admin123`。注意：这会清空所有用户和历史记录。

**Q：登录后页面一直显示"未登录或权限不足"？**
A：检查后端控制台是否报 PyJWT 未安装。执行 `pip install PyJWT` 后重启后端。

**Q：普通用户能看到用户管理页吗？**
A：不能。`user` 角色访问 `/api/users` 会返回 403，前端用户管理页对普通用户显示"仅管理员可访问"。

**Q：历史记录什么时候写入？**
A：训练任务成功完成时自动写入（在 `train_traditional` 接口成功返回前埋点）。失败的任务不会落库。

**Q：怎么让访客不用账号就能浏览？**
A：用 `admin` 登录 → 进「系统设置」→ 把「允许游客浏览」改为"是" → 保存。之后登录页会出现「👤 以游客身份浏览」按钮，访客点击即可进入只读模式（不能训练/导入/增删改/管理）。

**Q：游客模式有什么限制？**
A：游客只能看不能写。具体：可查看所有数据/图表/历史记录/导出 CSV，但不能训练模型、不能导入/上传数据、不能在数据管理页增删改行、不能修改系统设置、不能管理用户。游客身份 24 小时后自动过期，需重新点击游客按钮进入。

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
| PyJWT | 2.8.0 | JWT 鉴权（v3.2 用户系统用） |

---

## License

MIT License — 他人可自由使用、修改、商业化，仅需保留版权声明。
