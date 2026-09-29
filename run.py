# -*- coding: utf-8 -*-
"""autotest 统一测试入口。

用法：
    python run.py               # 运行全部用例
    python run.py api           # 仅 API 用例（-m api）
    python run.py ui            # 仅 UI 用例（-m ui）
    python run.py db            # 仅数据库用例（-m db）
    python run.py smoke         # 仅冒烟用例（-m smoke）
    python run.py all -- -x     # 透传额外 pytest 参数（"--" 之后的部分原样传给 pytest）

前置条件：被测系统已在 config/config.yaml 的 api.base_url 指向的地址运行
（本地启动：pip install flask && python sut/app.py）。
"""

import argparse
import subprocess
import sys

TARGETS = ("all", "api", "ui", "db", "smoke")


def build_cmd(target, extra):
    cmd = [sys.executable, "-m", "pytest"]
    if target == "all":
        cmd.append("testcases")
    else:
        cmd += ["-m", target]
    cmd += extra
    return cmd


def main():
    parser = argparse.ArgumentParser(description="autotest 统一测试入口")
    parser.add_argument("target", nargs="?", default="all", choices=TARGETS,
                        help="测试范围，默认 all")
    parser.add_argument("--", dest="dash", action="store_true", help=argparse.SUPPRESS)
    args, unknown = parser.parse_known_args()

    extra = unknown[1:] if unknown and unknown[0] == "--" else unknown
    cmd = build_cmd(args.target, extra)
    print(f"[run.py] 执行: {' '.join(cmd)}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
