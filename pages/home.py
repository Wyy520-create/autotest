# -*- coding: utf-8 -*-
"""mini-blog 首页页面对象。"""

from selenium.webdriver.common.by import By

from pages.base import BasePage


class HomePage(BasePage):
    """对应被测系统的 / 首页。"""

    PATH = "/"

    LOGGED_USER = (By.ID, "logged-user")
    LOGIN_LINK = (By.ID, "login-link")
    ARTICLE_TITLES = (By.CSS_SELECTOR, "#article-list .article-title")

    def is_logged_in(self, username=None):
        """判断当前是否已登录；传入 username 时同时校验欢迎语包含该用户名。"""
        if not self.is_visible(*self.LOGGED_USER):
            return False
        if username is None:
            return True
        welcome = self.text(*self.LOGGED_USER)
        self.log.info(f"欢迎语文本: {welcome}")
        return username in welcome

    def article_titles(self):
        """首页文章标题列表。"""
        return [el.text for el in self.find_all(*self.ARTICLE_TITLES)]
