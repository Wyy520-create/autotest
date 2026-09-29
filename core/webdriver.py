# -*- coding: utf-8 -*-
"""Selenium WebDriver 工厂：按配置创建浏览器实例并统一管理生命周期。

特性：
- 从 config/config.yaml 读取浏览器类型、无头模式与各类超时
- 借助 webdriver-manager 自动解析并下载匹配的浏览器驱动，免手工维护驱动版本
- 维护进程内驱动注册表，支持会话结束时统一回收（quit_all）
"""

import os
import re
import subprocess
import tempfile

import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from core.logger import log

DEFAULT_BROWSER_CONFIG = {
    "name": "chrome",
    "headless": False,
    "implicit_wait": 5,
    "page_load_timeout": 15,
    "script_timeout": 15,
}


def load_browser_config():
    """读取 config/config.yaml 的 browser 段，缺省项用默认值补齐。"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml"
    )
    config = dict(DEFAULT_BROWSER_CONFIG)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config.update(yaml.safe_load(f).get("browser", {}))
    except FileNotFoundError:
        log.warning(f"浏览器配置文件不存在，使用默认配置: {config_path}")
    return config


class WebDriverManager:
    """WebDriver 工厂 + 注册表。

    用法：
        manager = WebDriverManager()
        driver = manager.create_driver()   # 按配置创建并注册
        ...
        manager.quit_driver(driver)        # 单个回收
        WebDriverManager.quit_all()        # 全部回收
    """

    _registry = []

    def __init__(self, config=None):
        self.config = config or load_browser_config()

    def create_driver(self):
        """按配置创建浏览器实例并注册到回收表。"""
        name = str(self.config.get("name", "chrome")).lower()
        headless = bool(self.config.get("headless", False))
        log.info(f"启动浏览器: {name}, headless={headless}")

        if name == "chrome":
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            # 容器 / CI 环境常见的兼容性参数
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1440,900")
            # 支持通过环境变量指定浏览器二进制（如 snap 受限环境下的独立 Chrome）
            chrome_binary = os.environ.get("AUTOTEST_CHROME_BINARY")
            driver_version = None
            if chrome_binary:
                options.binary_location = chrome_binary
                # webdriver-manager 在标准路径外检测不到版本，直接解析二进制版本号
                try:
                    out = subprocess.check_output([chrome_binary, "--version"], text=True)
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
                    driver_version = match.group(1) if match else None
                except Exception as e:  # noqa: BLE001
                    log.warning(f"解析 Chrome 版本失败，将下载最新驱动: {e}")
                log.info(f"使用指定 Chrome 二进制: {chrome_binary}")
            manager = (
                ChromeDriverManager(driver_version=driver_version)
                if driver_version
                else ChromeDriverManager()
            )
            driver = webdriver.Chrome(service=ChromeService(manager.install()), options=options)
        elif name == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            # 独立 profile 目录，两个目的：
            # 1. 避免与桌面已运行的 Firefox 实例发生单实例委托冲突
            # 2. 目录放 $HOME 下 —— snap 打包的 Firefox 有文件系统隔离，看不到 /tmp
            profile_root = os.path.expanduser("~/.cache/autotest/ff_profiles")
            os.makedirs(profile_root, exist_ok=True)
            profile_dir = tempfile.mkdtemp(prefix="profile_", dir=profile_root)
            options.add_argument("-profile")
            options.add_argument(profile_dir)
            driver = webdriver.Firefox(
                service=FirefoxService(GeckoDriverManager().install()), options=options
            )
        else:
            raise ValueError(f"不支持的浏览器类型: {name}（当前支持 chrome / firefox）")

        driver.implicitly_wait(int(self.config.get("implicit_wait", 5)))
        driver.set_page_load_timeout(int(self.config.get("page_load_timeout", 15)))
        driver.set_script_timeout(int(self.config.get("script_timeout", 15)))

        self._registry.append(driver)
        return driver

    @classmethod
    def quit_driver(cls, driver):
        """回收单个驱动实例。"""
        if driver in cls._registry:
            cls._registry.remove(driver)
        try:
            driver.quit()
            log.info("浏览器已关闭")
        except Exception as e:  # noqa: BLE001
            log.warning(f"关闭浏览器出现异常: {e}")

    @classmethod
    def quit_all(cls):
        """回收注册表中全部驱动实例。"""
        for driver in cls._registry[:]:
            cls.quit_driver(driver)
