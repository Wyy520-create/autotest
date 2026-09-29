# -*- coding: utf-8 -*-
"""mini-blog 登录页面对象。"""

from selenium.webdriver.common.by import By

from pages.base import BasePage
from pages.home import HomePage


class LoginPage(BasePage):
    """对应被测系统的 /login 页面。"""

    PATH = "/login"

    USERNAME_INPUT = (By.ID, "username")
    PASSWORD_INPUT = (By.ID, "password")
    SUBMIT_BUTTON = (By.ID, "submit")
    ERROR_MESSAGE = (By.ID, "login-error")

    def login(self, username, password):
        """执行登录并返回首页页面对象（无论成功失败都完成跳转/渲染）。"""
        self.log.info(f"执行登录: username={username}")
        self.type(*self.USERNAME_INPUT, username)
        self.type(*self.PASSWORD_INPUT, password)
        self.click(*self.SUBMIT_BUTTON)
        return HomePage(self.driver, self.base_url)

    def has_error(self):
        """登录失败提示是否可见。"""
        return self.is_visible(*self.ERROR_MESSAGE)

    def error_message(self):
        """读取登录失败提示文本。"""
        return self.text(*self.ERROR_MESSAGE) if self.has_error() else ""
