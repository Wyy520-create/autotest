# -*- coding: utf-8 -*-
"""pytest 全局钩子与共享 fixture。"""

import os
import uuid

import allure
import pytest

from core.logger import log
from core.webdriver import WebDriverManager

# 截图保存目录（失败截图同时自动附加到 Allure 报告）
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "reports", "screenshots")


def pytest_runtest_setup(item):
    """为每条用例生成唯一 ID，供工作流用例构造隔离数据，避免用例间相互污染。"""
    pytest.test_id = uuid.uuid4().hex[:8]
    log.info(f"[{item.name}] 开始执行")


@pytest.fixture(scope="session")
def driver():
    """浏览器驱动实例（整个测试会话共享一个）。"""
    manager = WebDriverManager()
    d = manager.create_driver()
    yield d
    manager.quit_driver(d)


@pytest.fixture(scope="session")
def base_url():
    """被测系统 Web 站点根地址。"""
    return os.environ.get("AUTOTEST_BASE_URL", "http://127.0.0.1:8520")


@pytest.fixture(scope="function")
def web_user():
    """通过 API 注册一个随机用户，供 UI 登录类用例使用。

    返回 (username, password)；注册失败直接断言中断，暴露被测系统异常。
    """
    from api.users_api import UsersAPI

    username = f"ui_{pytest.test_id}"
    password = "Passw0rd!"
    resp = UsersAPI().register(username, f"{username}@example.com", password)
    assert resp.status_code == 200, f"预置用户注册失败: {resp.text}"
    return username, password


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """用例失败时自动截图并附加到 Allure 报告（仅对使用 driver 的 UI 用例生效）。"""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    if "driver" not in item.fixturenames:
        return
    drv = item.funcargs.get("driver")
    if drv is None:
        return
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        filename = f"{item.name}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(SCREENSHOT_DIR, filename)
        drv.save_screenshot(path)
        allure.attach.file(path, name="失败截图", attachment_type=allure.attachment_type.PNG)
        log.info(f"失败截图已保存: {path}")
    except Exception as e:  # noqa: BLE001
        log.error(f"失败截图保存异常: {e}")
