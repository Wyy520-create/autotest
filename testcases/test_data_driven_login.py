# -*- coding: utf-8 -*-
"""CSV 数据驱动登录：成功与失败账号统一参数化执行。"""

import allure
import pytest

from api.users_api import UsersAPI
from pages.login import LoginPage
from utils.data_provider import read_csv

CASES = read_csv("testdata/login_data.csv")
SUCCESS_PASSWORD = "Demo@123"


@allure.feature("用户登录")
@pytest.mark.ui
@pytest.mark.data_driven
class TestDataDrivenLogin:
    @classmethod
    def setup_class(cls):
        """预注册 CSV 中 expected=success 的账号（已存在则 422，视为正常幂等）。"""
        usernames = {c["username"] for c in CASES if c["expected"] == "success"}
        api = UsersAPI()
        for name in usernames:
            resp = api.register(name, f"{name}@example.com", SUCCESS_PASSWORD)
            assert resp.status_code in (200, 422), f"预置用户 {name} 注册失败: {resp.text}"

    @allure.story("CSV 数据驱动登录")
    @pytest.mark.parametrize(
        "case", CASES,
        ids=[f"{c['username']}|{c['expected']}" for c in CASES],
    )
    def test_login_csv(self, driver, base_url, case):
        page = LoginPage(driver, base_url)
        page.open()
        home = page.login(case["username"], case["password"])
        if case["expected"] == "success":
            assert home.is_logged_in(case["username"]), "预期登录成功，但首页未见用户欢迎语"
        else:
            assert page.has_error(), "预期登录失败，但未出现错误提示"
