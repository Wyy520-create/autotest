# -*- coding: utf-8 -*-
"""页面对象基类：封装元素定位、显式等待与常用操作。"""

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.logger import get_logger


class BasePage:
    """所有页面对象的基类。

    子类约定：
    - 类属性以元组形式声明定位器，如 ``USERNAME_INPUT = (By.ID, "username")``
    - 页面相对路径放类属性 ``PATH``，配合 ``open()`` 跳转
    """

    PATH = "/"

    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.log = get_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # 导航与查找
    # ------------------------------------------------------------------
    def open(self, path=None):
        """打开页面。path 缺省时使用类属性 PATH。"""
        url = self.base_url + (path if path is not None else self.PATH)
        self.log.info(f"打开页面: {url}")
        self.driver.get(url)

    def find(self, by, value, timeout=10):
        """显式等待元素可见后返回。"""
        self.log.debug(f"定位元素: {by}={value}")
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )

    def find_all(self, by, value, timeout=10):
        """显式等待并返回全部匹配元素。"""
        WebDriverWait(self.driver, timeout).until(
            EC.presence_of_all_elements_located((by, value))
        )
        return self.driver.find_elements(by, value)

    def is_visible(self, by, value, timeout=5):
        """判断元素是否在超时时间内可见（不抛异常）。"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # 常用操作
    # ------------------------------------------------------------------
    def click(self, by, value, timeout=10):
        self.find(by, value, timeout).click()
        self.log.info(f"点击元素: {by}={value}")

    def type(self, by, value, text, timeout=10):
        element = self.find(by, value, timeout)
        element.clear()
        element.send_keys(text)
        self.log.info(f"输入文本: {by}={value} -> {text!r}")

    def text(self, by, value, timeout=10):
        return self.find(by, value, timeout).text

    def page_title(self):
        return self.driver.title
