"""
============================================================
  HGMX 一键运行流水线 (小白友好版)
  直接运行这个文件即可，会自动按顺序执行全部步骤
============================================================

  文件作用:
    本脚本是 FORGE-HV / HGMX 项目的一键流水线入口，串联整个项目
    的训练流程，无需手动依次运行多个子脚本。

  核心功能（依次执行，后一步依赖前一步的产物）:
    1) 原始数据训练  -> CT_main.py    : 传统 ML(LR/PR/SVR) 用 149 条原始数据
    2) GAN 生成数据  -> step3_train_gan: 用 GAN 伪造 10000 条数据并合并
    3) GAN 数据训练  -> GAN-main.py   : 传统 ML 用 原始+GAN 混合数据
    4) DDPG 训练     -> DDPG.py       : 深度强化学习，只用原始数据
    5) DDPG+GAN 训练 -> DDPG-gan.py   : 深度强化学习，用混合数据

    （前置步骤：单位换算、DINO-v2 图片特征提取 + PCA 降维）

  运行方式:
    python run_all.py
    （首次使用需先安装依赖：venv\\Scripts\\pip install -r requirements.txt）

  输出:
    各阶段结果保存到对应目录:
      data/             -> 单位换算 & 特征合并后的中间数据
      generated_data/   -> GAN 生成的 10000 条数据 + 真实+伪造合并数据
      model/            -> 训练好的模型权重 & PCA 模型
      output/           -> 模型预测结果
      results/          -> 各模型对比结果、PCA 对比等

  首次使用（学妹看这里）:
    1. 打开终端，cd 到这个文件夹
    2. python -m venv venv
    3. venv\\Scripts\\pip install -r requirements.txt
    4. venv\\Scripts\\python run_all.py

  之后每次运行只需第4步。

  整体流程说明:
  第1步: 单位换算 (GPa -> HV)          -> 几秒钟
  第2步: 提取图片特征 + PCA降维         -> 几秒钟
  第3步: GAN 伪造1万条数据             -> 比较慢，要几分钟
  第4步: 训练4种模型对比效果            -> 这个最慢

  快速体验: 把 SKIP_GAN 和 SKIP_DDPG 改成 True，秒级跑完
"""

import os
import sys
import time

# ============================================================
# 0. 自动检测工程路径（不用手动改任何东西！）
#    通过动态改写 config 模块的属性，保证后续所有子脚本读取的路径
#    都是基于当前 run_all.py 所在目录的绝对路径，免去手动配置。
# ============================================================
import config
config.BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 工程根目录

# 更新 config 中所有依赖 BASE_DIR 的路径（这些路径后续会传给各子脚本使用）
config.DATA_FILE_ORIGINAL = os.path.join(config.BASE_DIR, "data", "data.xlsx")                       # 原始数据
config.DATA_FILE = os.path.join(config.BASE_DIR, "data", "data_converted.xlsx")                     # 第1步输出: 单位换算后的数据
config.DATA_FILE_MIC = os.path.join(config.BASE_DIR, "data", "data_with_microstructure.xlsx")        # 第2步输出: 合并微观特征后的数据
config.FEATURES_DIR = os.path.join(config.BASE_DIR, "Features")                                     # DINO-v2 图片特征目录
config.GENERATED_DATA_PATH = os.path.join(config.BASE_DIR, "generated_data", "gan_generated_data_10000.xlsx")  # 第3步输出: GAN 生成的 1万条数据
config.COMBINED_DATA_PATH = os.path.join(config.BASE_DIR, "generated_data", "combined_data.xlsx")    # 第3步输出: 真实+GAN 合并数据(传给 GAN-main / DDPG-gan)
config.MODEL_PATH = os.path.join(config.BASE_DIR, "model", "best_model.pth")                         # 模型权重
config.OUTPUT_FILE = os.path.join(config.BASE_DIR, "results", "predictions.xlsx")                     # 预测结果
config.PCA_RESULTS_FILE = os.path.join(config.BASE_DIR, "results", "pca_comparison.xlsx")            # PCA 对比结果

# 确保必要的目录存在（首次运行时自动创建，避免后续写文件时报错）
for d in ["data", "generated_data", "model", "output", "results"]:
    os.makedirs(os.path.join(config.BASE_DIR, d), exist_ok=True)


# ============================================================
# 用户可选设置（改成 False 就跳过对应步骤）
# 通过这三个开关可以灵活控制流水线跑哪些阶段，便于调试和快速体验
# ============================================================
SKIP_GAN = False          # False=训练GAN伪造1万条数据；True=跳过（用已有数据）
SKIP_DDPG = False         # True=只跑传统ML（快）；False=也跑深度强化学习（很慢！）
SKIP_DDPG_GAN = False     # True=跳过 DDPG+GAN混合训练（更慢！）


# ============================================================
def print_step(title):
    """打印步骤标题，方便在控制台看到进度"""
    print("\n" + "=" * 60)
    print(f"  >>> {title}")
    print("=" * 60)


def step1_convert_units():
    """
    第1步：单位换算
    把原始数据中的 GPa（吉帕）统一转成 HV（维氏硬度）
    输入: data/data.xlsx
    输出: data/data_converted.xlsx
    """
    print_step("第1步: 单位换算 (GPa -> HV)")

    import pandas as pd

    if not os.path.exists(config.DATA_FILE_ORIGINAL):
        print(f"[ERR] 找不到输入文件 {config.DATA_FILE_ORIGINAL}")
        print("   请确保 data/data.xlsx 存在！")
        return False

    df = pd.read_excel(config.DATA_FILE_ORIGINAL, sheet_name="Sheet1")
    print(f"  [OK] 读取到 {len(df)} 条原始数据")

    hv_col = "Vickers Hardness (HV)"          # 目标列（HV 单位）
    gpa_col = "Vickers Hardness (Gpa) "       # 源列（GPa 单位，注意列名末尾有空格）

    # 强制转成数值，无法转换的置为 NaN（避免字符串干扰后续计算）
    df[hv_col] = pd.to_numeric(df[hv_col], errors='coerce')
    df[gpa_col] = pd.to_numeric(df[gpa_col], errors='coerce')

    # 行级换算：HV 列缺失时用 GPa * 102 补齐（1 GPa ≈ 102 HV），已有 HV 的保留原值
    df[hv_col] = df.apply(
        lambda row: row[gpa_col] * 102 if pd.isna(row[hv_col]) else row[hv_col],
        axis=1
    )
    # 换算完毕，删除冗余的 GPa 列
    df = df.drop(columns=[gpa_col], errors='ignore')

    # 输出第1步产物，供后续 step2 / step3 / step4 读取
    df.to_excel(config.DATA_FILE, index=False)
    print(f"  [OK] 转换完成 -> 保存到 {config.DATA_FILE}")
    return True


def step2_microstructure_features():
    """
    第2步：提取微观结构特征
    从 Features/ 目录读取每张合金图片的 DINO-v2 AI特征，
    用 PCA 压缩到 70 维，和"成分+硬度"数据合并成一张大表
    输入: data/data_converted.xlsx + Features/*.npy
    输出: data/data_with_microstructure.xlsx
          model/pca_model.npy （保存 PCA 参数，供后续推理对齐使用）
    """
    print_step("第2步: 提取图片特征 + PCA 降维到70维")

    import numpy as np
    import pandas as pd
    from sklearn.decomposition import PCA

    # 流水线衔接：如果第1步产物缺失，自动回退执行第1步
    if not os.path.exists(config.DATA_FILE):
        print("  [WARN] data_converted.xlsx 不存在，先执行第1步...")
        step1_convert_units()

    if not os.path.exists(config.FEATURES_DIR):
        print(f"  [ERR] Features/ 目录不存在 ({config.FEATURES_DIR})")
        print("   这个目录应该包含每张合金图片的 .npy 特征文件")
        print("   如果没有这个目录，说明还没有从图片提取过 DINO 特征")
        print("   请联系学姐获取这些特征文件，或跳过此步骤")
        return False

    df = pd.read_excel(config.DATA_FILE, sheet_name="Sheet1")

    all_micro_features = []   # 收集每张图片展开成一维后的特征向量
    valid_indices = []        # 记录有对应特征文件的行索引（缺失特征文件的样本会被丢弃）

    # 按 Image_Name 逐行匹配对应的 DINO-v2 特征文件
    for idx, img_name in enumerate(df["Image_Name"]):
        feature_file = os.path.join(config.FEATURES_DIR, f"{img_name}_dino_b.npy")

        if os.path.exists(feature_file):
            feature = np.load(feature_file)
            all_micro_features.append(feature.flatten())   # 展平成 1 维向量
            valid_indices.append(idx)
        else:
            print(f"  [WARN] 缺少特征文件: {feature_file}")

    if len(valid_indices) == 0:
        print("  [ERR] 一个特征文件都没找到！")
        return False

    # 只保留有图片特征的样本，与特征向量对齐
    df_valid = df.iloc[valid_indices].reset_index(drop=True)
    all_micro_features = np.array(all_micro_features)

    print(f"  [OK] 有效样本: {len(df_valid)} 条 (共 {len(df)} 条)")
    print(f"  [OK] 原始图片特征维度: {all_micro_features.shape[1]}")

    # PCA 降维到 70 维（DINO-v2 输出维度很高，压缩后便于后续训练且减少噪声）
    pca = PCA(n_components=70)
    pca_micro_features = pca.fit_transform(all_micro_features)

    print(f"  [OK] PCA 降维后: {pca_micro_features.shape[1]} 维")
    print(f"  [OK] PCA 保留信息量: {np.sum(pca.explained_variance_ratio_)*100:.1f}%")

    # 给 70 个主成分命名列名 Micro_1 ~ Micro_70
    micro_columns = [f"Micro_{i + 1}" for i in range(70)]
    micro_df = pd.DataFrame(pca_micro_features, columns=micro_columns)

    # 横向拼接：成分+硬度 | 微观特征 -> 形成后续训练用的大表
    combined_df = pd.concat([df_valid.reset_index(drop=True), micro_df], axis=1)

    # 输出第2步产物（同时保存 PCA 参数，保证推理时能用同一套变换）
    combined_df.to_excel(config.DATA_FILE_MIC, index=False)
    np.save(os.path.join(config.BASE_DIR, "model", "pca_model.npy"),
            {'components': pca.components_, 'mean': pca.mean_, 'explained_variance': pca.explained_variance_})

    print(f"  [OK] 完成 -> {config.DATA_FILE_MIC}")
    return True


def step3_train_gan():
    """
    第3步：用 GAN 伪造 1 万条数据
    在 149 条真实数据上训练一个"造假AI"（生成对抗网络），
    让它学会数据的分布规律，然后批量生成 10000 条逼真的假数据
    输入: data/data_with_microstructure.xlsx
    输出: generated_data/gan_generated_data_10000.xlsx
          generated_data/combined_data.xlsx (真实+伪造混合)

    [WARN] 这步最慢，没有 GPU 的话可能需要 5-10 分钟

    衔接关系：
      上游 <- step2 输出的 data_with_microstructure.xlsx
      下游 -> step4 的 GAN-main.py / DDPG-gan.py 会读取 combined_data.xlsx
    """
    print_step("第3步: GAN 训练 + 伪造 10000 条数据 (可能比较慢...)")

    import numpy as np
    import pandas as pd
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.preprocessing import StandardScaler

    # 流水线衔接：若第2步产物缺失，自动回退执行前两步
    if not os.path.exists(config.DATA_FILE_MIC):
        print("  [WARN] data_with_microstructure.xlsx 不存在，先执行前两步...")
        step1_convert_units()
        if not step2_microstructure_features():
            return False

    # 生成器：把 100 维噪声 -> 映射到数据空间（输出维度 = 特征总数）
    class Generator(nn.Module):
        def __init__(self, latent_dim, output_dim):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(latent_dim, 256), nn.BatchNorm1d(256), nn.LeakyReLU(0.2),
                nn.Linear(256, 128), nn.BatchNorm1d(128), nn.LeakyReLU(0.2),
                nn.Linear(128, output_dim), nn.Tanh()   # Tanh 把输出压到 [-1,1]（配合标准化数据）
            )
        def forward(self, x): return self.net(x)

    # 判别器：把一条数据 -> 判为真/假的概率
    class Discriminator(nn.Module):
        def __init__(self, input_dim):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 512), nn.LeakyReLU(0.2),
                nn.Linear(512, 256), nn.LeakyReLU(0.2),
                nn.Linear(256, 1), nn.Sigmoid()   # Sigmoid 输出 [0,1] 概率
            )
        def forward(self, x): return self.net(x)

    df = pd.read_excel(config.DATA_FILE_MIC)
    hardness_col = "Vickers Hardness (HV)"
    composition_cols = config.composition_columns            # 成分列名列表（来自 config）
    micro_cols = [f"Micro_{i + 1}" for i in range(70)]       # 第2步保存的 70 维微观特征列
    # 拼装训练特征顺序：硬度 + 成分 + 微观特征（共 93 列）
    all_feature_cols = [hardness_col] + composition_cols + micro_cols
    data = df[all_feature_cols].values

    print(f"  [OK] 原始数据: {data.shape} (149 行 x 93 列)")

    # 标准化到均值0方差1，配合生成器的 Tanh 输出
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"  [OK] 使用设备: {device} {'(有显卡，会很快)' if 'cuda' in str(device) else '(无显卡，会很慢...)'}")

    input_dim = data.shape[1]   # 93（特征维度）
    latent_dim = 100            # 噪声向量维度
    generator = Generator(latent_dim, input_dim).to(device)
    discriminator = Discriminator(input_dim).to(device)

    criterion = nn.BCELoss()   # 二分类交叉熵（真/假）
    # AdamW + (0.5, 0.999) 是 GAN 常用配置，能稳定训练
    opt_G = torch.optim.AdamW(generator.parameters(), lr=2e-4, betas=(0.5, 0.999))
    opt_D = torch.optim.AdamW(discriminator.parameters(), lr=2e-4, betas=(0.5, 0.999))

    real_data_tensor = torch.FloatTensor(data_scaled).to(device)
    epochs = 10000              # 训练轮次（数据量小，需要多轮才能收敛）

    print(f"  [...] 开始训练 {epochs} 轮... (每1000轮打印一次进度)")
    start_time = time.time()

    # 标准 GAN 训练循环：每轮先训判别器，再训生成器
    for epoch in range(epochs):
        # ---------- 1) 训练判别器 D ----------
        discriminator.zero_grad()
        # 真实数据 -> 应判为 1
        real_labels = torch.ones(real_data_tensor.size(0), 1).to(device)
        d_loss_real = criterion(discriminator(real_data_tensor), real_labels)

        # 噪声 -> 生成器造假 -> 判为 0
        z = torch.randn(real_data_tensor.size(0), latent_dim).to(device)
        fake_data = generator(z)
        fake_labels = torch.zeros(real_data_tensor.size(0), 1).to(device)
        # detach() 阻止梯度流回生成器，避免 D 训练时影响 G
        d_loss_fake = criterion(discriminator(fake_data.detach()), fake_labels)

        d_loss = (d_loss_real + d_loss_fake) / 2
        d_loss.backward()
        opt_D.step()

        # ---------- 2) 训练生成器 G ----------
        generator.zero_grad()
        # 生成器希望判别器把假数据判为真（用 real_labels 反过来骗 D）
        g_loss = criterion(discriminator(fake_data), real_labels)
        g_loss.backward()
        opt_G.step()

        if (epoch + 1) % 1000 == 0:
            elapsed = time.time() - start_time
            print(f"    Epoch {epoch + 1}/{epochs} | D Loss: {d_loss.item():.4f} | G Loss: {g_loss.item():.4f} | 已用时: {elapsed:.0f}秒")

    print(f"  [OK] GAN 训练完成！总用时: {time.time()-start_time:.0f} 秒")

    # ---------- 生成 10000 条假数据 ----------
    print("  [...] 开始生成 10000 条数据...")
    with torch.no_grad():
        z = torch.randn(10000, latent_dim).to(device)
        generated_scaled = generator(z).cpu().numpy()

    # 反标准化：从 [-1,1] 范围还原到原始量纲
    generated_data = scaler.inverse_transform(generated_scaled)
    generated_df = pd.DataFrame(generated_data, columns=all_feature_cols)

    # 后处理：成分/硬度不能为负 -> clip 到 0；微观特征可正可负只保留 4 位小数
    for col in composition_cols:
        generated_df[col] = generated_df[col].clip(lower=0).round(4)
    for col in micro_cols:
        generated_df[col] = generated_df[col].round(4)
    generated_df[hardness_col] = generated_df[hardness_col].clip(lower=0).round(4)

    # 给每条假数据生成唯一标识名（Image_Name），方便后续合并去重
    generated_df['Image_Name'] = [f'Generated_{i+1}' for i in range(10000)]
    cols = ['Image_Name'] + all_feature_cols
    generated_df = generated_df[cols]

    # 输出1: 仅 GAN 生成的数据（供单独分析使用）
    generated_df.to_excel(config.GENERATED_DATA_PATH, index=False)
    print(f"  [OK] 生成数据保存到: {config.GENERATED_DATA_PATH}")

    # 输出2: 真实 + 伪造合并数据（传给 step4 的 GAN-main.py / DDPG-gan.py）
    original_cols = ['Image_Name'] + all_feature_cols
    combined_df = pd.concat([df[original_cols], generated_df], ignore_index=True)
    combined_df.to_excel(config.COMBINED_DATA_PATH, index=False)
    print(f"  [OK] 合并数据保存到: {config.COMBINED_DATA_PATH}")
    print(f"  [OK] 总数据量: {len(combined_df)} 条 (真实149 + 伪造10000)")

    return True


def step4_train_models():
    """
    第4步：训练模型，对比效果
      - CT_main.py:   传统ML(LR/PR/SVR) -> 只用原始149条数据
      - GAN-main.py:  传统ML(LR/PR/SVR) -> 原始+GAN混合数据
      - DDPG.py:      深度强化学习       -> 只用原始149条数据 (可选跳过)
      - DDPG-gan.py:  深度强化学习       -> 原始+GAN混合数据 (可选跳过)

    衔接关系：
      上游 <- step1/step2/step3 输出的各类数据文件
      下游 -> 把对比结果写到 results/ 目录
    """
    print_step("第4步: 训练模型 & 对比效果")

    import importlib.util

    # 将当前内存里修改过的 config 路径同步写入 config.py 文件，
    # 保证后续动态加载的子脚本 import config 时读到的是正确路径
    _write_config_to_disk()

    # 按"原始数据 -> GAN混合 -> DDPG -> DDPG+GAN"的顺序组织待运行脚本
    scripts_to_run = []

    # 必跑：传统 ML（原始数据）
    scripts_to_run.append(("CT_main.py", "传统ML -> 原始数据"))

    # GAN-main 依赖 step3 输出的 combined_data.xlsx
    if os.path.exists(config.COMBINED_DATA_PATH):
        scripts_to_run.append(("GAN-main.py", "传统ML -> 原始+GAN混合数据"))
    else:
        print("  [WARN] combined_data.xlsx 不存在，跳过 GAN-main.py")

    # 可选：深度 RL（原始数据），受 SKIP_DDPG 开关控制
    if not SKIP_DDPG:
        scripts_to_run.append(("DDPG.py", "深度RL(DDPG) -> 原始数据"))
    else:
        print("  [SKIP] 跳过 DDPG.py (SKIP_DDPG=True)")

    # 可选：深度 RL（GAN混合数据），同时受 SKIP_DDPG_GAN 开关和 combined_data 是否存在控制
    if not SKIP_DDPG_GAN and os.path.exists(config.COMBINED_DATA_PATH):
        scripts_to_run.append(("DDPG-gan.py", "深度RL(DDPG) -> 原始+GAN混合数据"))
    elif not SKIP_DDPG_GAN:
        print("  [WARN] combined_data.xlsx 不存在，跳过 DDPG-gan.py")
    else:
        print("  [SKIP] 跳过 DDPG-gan.py (SKIP_DDPG_GAN=True)")

    # 依次执行每个子脚本（按顺序串行，保证日志可读、资源可控）
    for filename, desc in scripts_to_run:
        filepath = os.path.join(config.BASE_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  [ERR] 找不到 {filename}，跳过")
            continue

        print(f"\n  --- {desc} ({filename}) ---")

        # 用 importlib 动态加载子脚本作为模块，确保它 import config 时
        # 拿到的是我们前面修改过的全局 config（同一进程共享 sys.modules['config']）
        module_name = filename.replace(".py", "").replace("-", "_")
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
            # 入口约定：优先调用 main()，没有再退回到 train_ddpg_regressor()
            if hasattr(mod, 'main'):
                mod.main()
            elif hasattr(mod, 'train_ddpg_regressor'):
                mod.train_ddpg_regressor()
            else:
                print(f"  [WARN] {filename} 没有可调用的入口函数")
            print(f"  [OK] {filename} 完成")
        except Exception as e:
            print(f"  [WARN] {filename} 运行异常: {e}")


def _write_config_to_disk():
    """
    把内存中修改过的 config 路径写入 config.py 文件，
    这样后续子脚本 import config 时能读到正确的路径
    """
    config_path = os.path.join(config.BASE_DIR, "config.py")
    if not os.path.exists(config_path):
        return

    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 只改写 BASE_DIR 一行；其他配置保持不动（子脚本 import 时再从 config 读取）
    with open(config_path, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith("BASE_DIR"):
                f.write(f'BASE_DIR = r"{config.BASE_DIR}"\n')
            else:
                f.write(line)


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("""
    +======================================================+
    |        HGMX 高温合金硬度预测 -- 一键运行流水线          |
    |                                                      |
    |  流程: 单位换算 -> 特征提取 -> GAN造数据 -> 模型训练    |
    |                                                      |
    |  [提示]                                               |
    |  - 如果只想快速跑通看效果，把上面 SKIP_DDPG 改成 True  |
    |  - GAN (第3步) 没有GPU会很慢，约5-15分钟               |
    |  - DDPG (第4步) 更慢，建议先跳过                       |
    +======================================================+
    """)

    total_start = time.time()

    # ---- 第1步: 单位换算（产物存在则跳过，避免重复计算）----
    if not os.path.exists(config.DATA_FILE):
        step1_convert_units()
    else:
        print_step("第1步: 单位换算 -- 跳过 (data_converted.xlsx 已存在)")

    # ---- 第2步: 图片特征提取（产物存在则跳过）----
    if not os.path.exists(config.DATA_FILE_MIC):
        step2_microstructure_features()
    else:
        print_step("第2步: 特征提取 -- 跳过 (data_with_microstructure.xlsx 已存在)")

    # ---- 第3步: GAN 数据增强（受 SKIP_GAN 开关 + 产物是否存在双重控制）----
    if SKIP_GAN:
        print_step("第3步: GAN -- 跳过 (SKIP_GAN=True)")
    elif not os.path.exists(config.GENERATED_DATA_PATH):
        step3_train_gan()
    else:
        print_step("第3步: GAN -- 跳过 (gan_generated_data_10000.xlsx 已存在)")

    # ---- 第4步: 模型训练（始终执行，内部会根据开关决定跑哪些子脚本）----
    step4_train_models()

    # ---- 完成 ----
    total_time = time.time() - total_start
    print("\n" + "=" * 60)
    print(f"  [DONE] 全部完成！总用时: {total_time:.0f} 秒 ({total_time/60:.1f} 分钟)")
    print(f"  [FILE] 结果文件在: {os.path.join(config.BASE_DIR, 'results')}")
    print("=" * 60)
