# -*- coding: utf-8 -*-
"""UI 登录成功场景（页面对象模式）。"""

import allure
import pytest

from pages.login import LoginPage


@allure.feature("用户登录")
@pytest.mark.ui
@pytest.mark.smoke
class TestLoginSuccess:
    @allure.story("正确账号密码登录成功")
    def test_login_success(self, driver, base_url, web_user):
        username, password = web_user
        page = LoginPage(driver, base_url)
        page.open()
        home = page.login(username, password)
        assert home.is_logged_in(username), "登录成功后首页未出现包含用户名的欢迎语"
