# -*- coding: utf-8 -*-
"""pytest 全局钩子与共享 fixture。"""

import os
import re
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
        # 清洗文件名非法字符（parametrize id 可能含 []| 等），保证跨文件系统可用
        safe_name = re.sub(r"[^\w\-.]", "_", item.name)
        filename = f"{safe_name}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(SCREENSHOT_DIR, filename)
        drv.save_screenshot(path)
        allure.attach.file(path, name="失败截图", attachment_type=allure.attachment_type.PNG)
        log.info(f"失败截图已保存: {path}")
        # 失败现场取证：URL、表单实际值、页面关键标记（定位 CI 环境类问题）
        try:
            src = drv.page_source
            u = drv.find_elements("id", "username")
            p = drv.find_elements("id", "password")
            log.info(f"[取证] URL: {drv.current_url}")
            log.info(f"[取证] username实际值: {u[0].get_attribute('value') if u else '(页面无此元素)'}")
            log.info(f"[取证] password实际值: {p[0].get_attribute('value') if p else '(页面无此元素)'}")
            has_err = 'id="login-error"' in src
            has_user = 'id="logged-user"' in src
            log.info(f"[取证] login-error存在: {has_err} | logged-user存在: {has_user}")
            # 浏览器控制台日志（headless Chrome 会记录网络层错误，如 net::ERR_*）
            try:
                for entry in drv.get_log("browser")[-8:]:
                    log.info(f"[取证] browser日志: {entry.get('level')} | {str(entry.get('message'))[:200]}")
            except Exception as be:  # noqa: BLE001
                log.warning(f"[取证] browser日志采集异常: {be}")
            # 在页面上下文同步重放 POST /login：验证失败瞬间服务端可达且响应正常，
            # 从而把「服务端问题」与「浏览器表单提交问题」彻底分开
            try:
                xhr = drv.execute_script(
                    "var x = new XMLHttpRequest();"
                    "x.open('POST', '/login', false);"
                    "x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');"
                    "x.send('username=forensic_probe&password=x');"
                    "return x.status + ' | len=' + x.responseText.length"
                           " + ' | login-error=' + (x.responseText.indexOf('login-error') > -1);"
                )
                log.info(f"[取证] 页面内XHR重放POST /login: {xhr}")
            except Exception as xe:  # noqa: BLE001
                log.warning(f"[取证] XHR重放异常: {xe}")
        except Exception as fe:  # noqa: BLE001
            log.warning(f"[取证] 失败现场采集异常: {fe}")
    except Exception as e:  # noqa: BLE001
        log.error(f"失败截图保存异常: {e}")
