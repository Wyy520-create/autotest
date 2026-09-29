# -*- coding: utf-8 -*-
"""UI 登录失败场景：错误密码 / 不存在用户。"""

import allure
import pytest

from pages.login import LoginPage


@allure.feature("用户登录")
@pytest.mark.ui
class TestLoginFailed:
    @allure.story("密码错误时展示错误提示")
    def test_wrong_password_shows_error(self, driver, base_url, web_user):
        username, _ = web_user
        page = LoginPage(driver, base_url)
        page.open()
        page.login(username, "bad-password")
        assert page.has_error(), "密码错误登录后未出现错误提示"
        assert "Invalid" in page.error_message()

    @allure.story("用户不存在时展示错误提示")
    def test_unknown_user_shows_error(self, driver, base_url):
        page = LoginPage(driver, base_url)
        page.open()
        page.login(f"nobody_{pytest.test_id}", "whatever")
        assert page.has_error(), "不存在用户登录后未出现错误提示"
        assert "Invalid" in page.error_message()
