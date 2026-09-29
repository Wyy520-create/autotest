# -*- coding: utf-8 -*-
"""数据库操作封装：按 config/database.driver 选择 SQLite 或 MySQL。

- SQLite（默认）：零第三方依赖直连被测系统数据库文件；
  路径取环境变量 AUTOTEST_DB_PATH，未设置时使用 config 中的 path。
- MySQL：需安装 pymysql，仅在 driver 配置为 mysql 时惰性导入。
对外方法签名一致，占位符按驱动自动适配（? / %s）。
"""

import os
import sqlite3

import yaml

from core.logger import log

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DBManager:
    def __init__(self):
        with open(os.path.join(PROJECT_ROOT, "config", "config.yaml"), encoding="utf-8") as f:
            self.config = yaml.safe_load(f).get("database", {})
        self.driver = self.config.get("driver", "sqlite")
        self.placeholder = "%s" if self.driver == "mysql" else "?"
        self.connection = None
        self.cursor = None

    def _resolve_sqlite_path(self):
        path = os.environ.get("AUTOTEST_DB_PATH") or self.config.get("path", "dev.db")
        if not os.path.isabs(path):
            path = os.path.join(PROJECT_ROOT, path)
        return path

    def connect(self):
        log.info(f"连接数据库 (driver={self.driver}) ...")
        try:
            if self.driver == "mysql":
                import pymysql  # 惰性导入：SQLite 场景无需安装

                self.connection = pymysql.connect(
                    host=self.config.get("host", "localhost"),
                    port=self.config.get("port", 3306),
                    user=self.config.get("username", "root"),
                    password=self.config.get("password", ""),
                    database=self.config.get("database", "test"),
                    charset=self.config.get("charset", "utf8mb4"),
                    cursorclass=pymysql.cursors.DictCursor,
                )
            else:
                db_path = self._resolve_sqlite_path()
                if not os.path.exists(db_path):
                    log.warning(f"SQLite 数据库文件不存在，将新建空库: {db_path}")
                self.connection = sqlite3.connect(db_path)
                self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            log.info("数据库连接成功")
            return True
        except Exception as e:
            log.error(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            log.info("数据库连接已关闭")

    @staticmethod
    def _to_dicts(rows, is_mysql):
        return list(rows) if is_mysql else [dict(r) for r in rows]

    def execute_query(self, sql, params=None):
        log.info(f"查询: {sql} | 参数: {params}")
        try:
            self.cursor.execute(sql, params or ())
            results = self._to_dicts(self.cursor.fetchall(), self.driver == "mysql")
            log.info(f"查询结果: {len(results)} 行")
            return results
        except Exception as e:
            log.error(f"查询失败: {e}")
            return None

    def execute_update(self, sql, params=None):
        """执行写操作并自动提交；失败自动回滚，返回影响行数。"""
        log.info(f"更新: {sql} | 参数: {params}")
        try:
            self.cursor.execute(sql, params or ())
            self.connection.commit()
            affected = self.cursor.rowcount
            log.info(f"影响行数: {affected}")
            return affected
        except Exception as e:
            self.connection.rollback()
            log.error(f"更新失败: {e}")
            return 0

    # 语义化 CRUD ------------------------------------------------------------------
    def insert(self, table, data):
        keys = ", ".join(data.keys())
        values = ", ".join([self.placeholder] * len(data))
        return self.execute_update(
            f"INSERT INTO {table} ({keys}) VALUES ({values})", tuple(data.values())
        )

    def update(self, table, data, where_clause, where_params=None):
        set_clause = ", ".join(f"{k}={self.placeholder}" for k in data)
        params = tuple(data.values()) + tuple(where_params or ())
        return self.execute_update(f"UPDATE {table} SET {set_clause} WHERE {where_clause}", params)

    def delete(self, table, where_clause, where_params=None):
        return self.execute_update(f"DELETE FROM {table} WHERE {where_clause}", where_params or ())

    def select(self, table, columns="*", where_clause=None, where_params=None, limit=None):
        sql = f"SELECT {columns} FROM {table}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if limit:
            sql += f" LIMIT {self.placeholder}"
            where_params = tuple(where_params or ()) + (limit,)
        return self.execute_query(sql, where_params)

    def count(self, table, where_clause=None, where_params=None):
        sql = f"SELECT COUNT(*) AS count FROM {table}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        result = self.execute_query(sql, where_params or ())
        return result[0]["count"] if result else 0

    # 上下文管理器协议 ---------------------------------------------------------------
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
