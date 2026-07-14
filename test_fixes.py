# -*- coding: utf-8 -*-
"""验证所有修复"""
import urllib.request, json, time

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())

def get(url):
    return json.loads(urllib.request.urlopen(url, timeout=10).read())

print("="*60)
print("【1. 健康检查】")
r = get("http://127.0.0.1:5000/api/health")
print(f"  status={r['status']} file_exists={r['exists']}")

print("\n【2. 单一模型训练 + 增强选项】")
r = post("http://127.0.0.1:5000/api/train/traditional", {
    "model": "ExtraTreesRegressor",
    "test_size": 0.2, "data_source": "real",
    "feature_filter": "importance", "target_transform": "log",
})
print(f"  R²={r['test_metrics']['R2_value']:.4f} RMSE={r['test_metrics']['RMSE_value']:.2f}")
print(f"  特征数={r['n_features_used']} 变换={r['target_transform']}")
print(f"  trace字段: {'有' if 'trace' in r else '无（已移除）'}")

print("\n【3. GAN 数据源（测试 IsolationForest import）】")
r = post("http://127.0.0.1:5000/api/train/traditional", {
    "model": "ExtraTreesRegressor",
    "test_size": 0.2, "data_source": "gan",
    "feature_filter": "off", "target_transform": "off",
})
if "error" in r:
    print(f"  失败: {r['error']}")
else:
    print(f"  R²={r['test_metrics']['R2_value']:.4f} (GAN数据源正常)")

print("\n【4. 模型比较 + log 变换】")
r = post("http://127.0.0.1:5000/api/train/compare", {
    "models": ["ExtraTreesRegressor", "KernelRidge", "GaussianProcessRegressor"],
    "test_size": 0.2, "cv_folds": 5,
    "feature_filter": "auto", "target_transform": "log",
})
if "error" in r:
    print(f"  失败: {r['error']}")
else:
    print(f"  最佳: {r['best']}")
    for m in r["models"]:
        if m["r2"] is not None:
            print(f"    {m['model']:30s} R²={m['r2']:.4f} RMSE={m['rmse']:.2f}")

print("\n【5. DDPG 启动（50轮快速测试）】")
r = post("http://127.0.0.1:5000/api/ddpg/train", {
    "data_source": "real", "epochs": 50, "batch_size": 32,
    "lr_actor": 0.0001, "lr_critic": 0.0005, "test_size": 0.2,
})
task_id = r.get("task_id")
print(f"  task_id={task_id} status={r.get('status')}")
if task_id:
    for i in range(20):
        time.sleep(3)
        s = get(f"http://127.0.0.1:5000/api/ddpg/status/{task_id}")
        print(f"  [{i*3}s] {s['status']} epoch={s.get('epoch',0)}/{s.get('total_epochs',0)} r2={s.get('val_r2','?')}")
        if s["status"] in ("done", "error"):
            if s["status"] == "done":
                m = s.get("metrics", {})
                print(f"  测试集: R²={m.get('test',{}).get('r2',0):.4f}")
                print(f"  trace字段: {'有' if 'trace' in s else '无（已移除）'}")
            else:
                print(f"  错误: {s.get('error')}")
            break

print("\n【6. 系统信息（torch 处理）】")
r = get("http://127.0.0.1:5000/api/system/info")
print(f"  CPU={r.get('cpu_percent')}% MEM={r.get('mem_percent')}%")
print(f"  torch={r.get('torch', 'N/A')}")

print("\n【7. DDPG 边界检查（epochs=0, batch_size=1）】")
r = post("http://127.0.0.1:5000/api/ddpg/train", {
    "data_source": "real", "epochs": 0, "batch_size": 1,
})
if "error" in r:
    print(f"  正确拒绝: {r['error']}")
else:
    task_id = r.get("task_id")
    time.sleep(2)
    s = get(f"http://127.0.0.1:5000/api/ddpg/status/{task_id}")
    print(f"  epochs={s.get('total_epochs')} batch_size=1 → status={s['status']}")

print("\n" + "="*60)
print("验证完成")
