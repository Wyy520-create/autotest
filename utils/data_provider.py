# -*- coding: utf-8 -*-
"""测试数据读取工具：把 testdata/ 下的 CSV 文件转成参数化数据。"""

import csv
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_csv(file_path):
    """读取 CSV 文件，返回字典列表（首行为表头）。

    相对路径基于项目根目录解析，便于用例中以 "testdata/xxx.csv" 短路径引用。
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(PROJECT_ROOT, file_path)
    with open(file_path, newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]
