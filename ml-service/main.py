# -*- coding: utf-8 -*-
"""
FORGE-HV Python ML 微服务
端口 5001，复用原 app.py 的全部 ML 逻辑（DDPG / GAN / sklearn 对比算法等）
无鉴权：由 Spring Boot 统一鉴权后转发；业务历史写入 MySQL，由 Spring 负责。
"""
import os
import sys

# 必须在 import app 之前设置，装饰器运行时读取该开关跳过鉴权
os.environ["FORGE_ML_SERVICE"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import app as forge_app


def _noop_record_history(*args, **kwargs):
    """业务历史由 Spring Boot + MySQL 落库，ML 服务不再写 SQLite history。"""
    return None


forge_app._record_history = _noop_record_history

app = forge_app.app

if __name__ == "__main__":
    print("[ML Service] FORGE-HV ML 微服务启动于 http://127.0.0.1:5001")
    print("[ML Service] 复用 Python 算法栈: DDPG / GAN / LinearRegression / PR / SVR")
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
