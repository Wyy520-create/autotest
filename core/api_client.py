# -*- coding: utf-8 -*-
"""HTTP 客户端封装：基于 Requests.Session，支持统一配置与 token 鉴权。

- base_url / 默认请求头 / 鉴权方式均来自 config/config.yaml
- token_prefix 可配置（被测系统要求 Authorization: Token <jwt> 时设为 Token）
- 支持注入共享 Session，便于多业务域对象复用同一登录态
"""

import os

import requests
import yaml

from core.logger import log

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    with open(os.path.join(PROJECT_ROOT, "config", "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


class APIClient:
    def __init__(self, base_url=None, session=None):
        self.config = load_config()["api"]
        self.base_url = (base_url or self.config["base_url"]).rstrip("/")
        # 支持注入外部 Session：多个业务 API 对象可共享同一登录态
        self.session = session or requests.Session()
        self.session.headers.update(self.config.get("default_headers", {}))
        self._apply_static_auth()

    @property
    def token_prefix(self):
        return self.config.get("token_prefix", "Bearer")

    def _apply_static_auth(self):
        """按配置预置鉴权信息（适合全局静态 token 的场景）。"""
        if self.config.get("auth_type") == "token" and self.config.get("token"):
            self.set_token(self.config["token"])
        elif self.config.get("auth_type") == "basic":
            self.session.auth = (self.config.get("username", ""), self.config.get("password", ""))

    def set_token(self, token):
        """设置/更新 token；传 None 则清除鉴权头。"""
        if token:
            self.session.headers["Authorization"] = f"{self.token_prefix} {token}"
        else:
            self.session.headers.pop("Authorization", None)

    # requests.Session 的语义化封装 ------------------------------------------------
    def get(self, endpoint, **kwargs):
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self._request("POST", endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self._request("PUT", endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self._request("DELETE", endpoint, **kwargs)

    def request(self, method, endpoint, **kwargs):
        return self._request(method, endpoint, **kwargs)

    def _request(self, method, endpoint, params=None, json=None, data=None, headers=None, **kwargs):
        url = f"{self.base_url}{endpoint}"
        log.info(f"{method} {url}")
        if params:
            log.info(f"  params={params}")
        response = self.session.request(
            method, url, params=params, json=json, data=data, headers=headers, **kwargs
        )
        log.info(f"  -> {response.status_code}")
        return response

    def close(self):
        self.session.close()
