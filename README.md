# FORGE-HV

> **HGMX 高温合金机器学习实验台（四栈融合版）**  
> FORGE: FRamework for Optimizing superalloy GEneration

严格对照论文《基于深度确定性策略梯度的合金维氏硬度预测算法》，通过 **22 种元素成分 + 70 维 DINO-v2 微结构特征** 预测**维氏硬度（HV）**。

> **技术栈分项说明 + 换电脑迁移步骤** 见：[技术栈与迁移说明.md](./技术栈与迁移说明.md)

## 四栈融合架构

| 层 | 技术 | 目录 | 端口 | 职责 |
|---|---|---|---|---|
| 前端 | **Vue 3** + Vite + Element Plus + ECharts | `frontend-vue/` | 5173 | 实验台 UI、鉴权交互 |
| 业务后端 | **Java Spring Boot 3** + JWT + JPA | `backend/` | 8080 | 用户 / 历史 / 设置；代理 ML API |
| 数据库 | **MySQL** | `sql/init.sql` | 3306 | 用户、训练历史、系统设置 |
| ML 引擎 | **Python**（Flask 微服务） | `ml-service/` + 根目录算法 | 5001 | DDPG / GAN / LR / PR / SVR 等全部算法 |

```
浏览器 Vue(:5173)
   │  /api + JWT
   ▼
Spring Boot(:8080) ──JPA──► MySQL(forge_hv)
   │  RestClient 代理
   ▼
Python ML(:5001)  复用 app.py / DDPG.py / GAN-main.py / CT_main.py ...
```

**设计原则：** 保留并强化原有优秀的 Python 算法栈（DDPG、GAN、sklearn 对比实验、异常值检测等），业务鉴权与持久化交给 Spring Boot + MySQL，交互界面交给 Vue。

---

## 论文对齐说明

| 维度 | 论文章节 | 本项目实现 |
|---|---|---|
| 数据准备 | 第 2 章 | 149 条实测样本（70 微结构 + 22 成分 + 1 硬度） |
| 异常值检测 | 第 2 章公式(1)(2)(3) | quantile_clip / IsolationForest / IQR / Z-score |
| DDPG 网络 | 第 3 章 | Actor-Critic、优先经验回放、五段式奖励 |
| DDPG 训练 | 第 4 章 | 高斯噪声 + 异步训练 + 状态轮询 |
| 对比算法 | 第 5.1 节 | LinearRegression / PolynomialRegression / SVR / DDPG |
| 评估指标 | 第 5.2 节 | RMSE / MAE / R² / MAPE |
| 原始数据对比 | 第 5.3 节 | 4 算法横向对比 |
| GAN 扩充对比 | 第 5.4 节 | GAN 数据上 4 算法对比 |

---

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（推荐） |
| Python | 3.10+ |
| JDK | 17+ |
| Maven | 3.8+ |
| Node.js | 18+ |
| MySQL | 8.0+ |
| 浏览器 | Chrome / Edge |
| GPU | 可选（NVIDIA 可加速 DDPG） |

---

## 安装（只需做一次）

### 1. MySQL

```bash
mysql -u root -p < sql/init.sql
```

默认连接（可在 `backend/src/main/resources/application.yml` 或环境变量覆盖）：

- 库名：`forge_hv`
- 用户 / 密码：默认 `root` / `root`（**请改成你本机 MySQL 密码**）
- 环境变量：`FORGE_DB_URL`、`FORGE_DB_USER`、`FORGE_DB_PASSWORD`
- 或复制 `backend/src/main/resources/application-local.yml.example` → `application-local.yml`，启动时加 `--spring.profiles.active=local`

### 2. Python ML 依赖

```bash
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# 或
python -m pip install -r ml-service/requirements.txt
```

可选 GPU PyTorch：

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu126 --force-reinstall
```

### 3. Spring Boot

无需额外步骤；首次 `mvn spring-boot:run` 会拉依赖。需本机已装 JDK 17 + Maven。

### 4. Vue 前端

```bash
cd frontend-vue
npm install
```

---

## 运行（推荐：四栈主路径）

按顺序启动，或直接双击：

```text
scripts\start-all.bat
```

也可分别启动：

```text
scripts\start-ml.bat        → Python ML   :5001
scripts\start-backend.bat   → Spring Boot :8080
scripts\start-frontend.bat  → Vue         :5173
```

浏览器打开：**http://127.0.0.1:5173**

默认管理员：**admin / admin123**（首次启动创建；**请尽快修改密码**）

JWT 密钥可通过环境变量 `FORGE_JWT_SECRET` 覆盖（至少 32 字节）。

游客账号仅可浏览（GET）；训练 / 上传 / 改数据需普通用户或管理员。

健康检查：

```bash
curl http://127.0.0.1:8080/api/health
```

应看到 `backend: spring-boot` 与 `ml_service` 状态。

---

## 目录结构

```text
FORGE-HV/
├── frontend-vue/     # Vue3 主前端（日常入口）
├── backend/          # Spring Boot + MySQL
├── ml-service/       # Python ML 微服务入口
├── sql/init.sql      # MySQL 初始化
├── scripts/          # Windows 启动脚本
├── app.py            # 原 Flask 单体（备份兼容）
├── frontend/         # 原静态前端（备份兼容）
├── DDPG.py / GAN-main.py / CT_main.py ...  # Python 算法核心
└── requirements.txt
```

---

## 备份 / 兼容入口（旧 Flask 单体）

旧方式仍可用（SQLite + 静态页），**不作为日常主路径**：

```bash
python app.py
# 浏览器打开 frontend/index.html 或访问 Flask 托管端口
```

四栈模式下，ML 服务会 noop 掉 Flask 内的鉴权与 SQLite 历史写入；用户与历史统一由 Spring Boot + MySQL 管理。

---

## 功能页面（Vue）

| 分组 | 页面 |
|---|---|
| 数据准备 | 数据可视化 / 异常值检测 / 元素相关性 / 数据库管理 |
| DDPG 模型 | DDPG 训练 / 模型架构 / GAN 数据生成过程 |
| 实验对比 | 5.3 原始数据对比 / 5.4 GAN 扩充对比 |
| 系统管理 | 数据管理 / 历史记录 / 用户管理 / 系统设置 |

---

## 常见问题

**Q: Spring Boot 连不上 MySQL？**  
检查服务是否启动、库是否已建、账号密码是否与 `application.yml` / 环境变量一致。

**Q: 前端能开但训练报错？**  
确认 ML 服务已在 5001 端口运行；查看 `http://127.0.0.1:8080/api/health`。

**Q: DDPG 很慢？**  
无 GPU 时用 CPU 训练较慢，可先减小 epochs；有 NVIDIA 时安装 CUDA 版 PyTorch。

---

## License

见 [LICENSE](LICENSE)。
