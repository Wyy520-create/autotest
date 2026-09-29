import csv
import os
import pytest
import allure
from api.users_api import UsersAPI


def _load_cases():
    """从 CSV 读取数据驱动用例（case_name, email, password, expected_status）。"""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'testdata', 'api_login_data.csv')
    with open(csv_path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


_LOGIN_CASES = _load_cases()


@allure.feature("数据驱动测试")
class TestDataDrivenAPI:
    """API 层数据驱动示例：登录接口多组凭证由 CSV 驱动。

    前置用户 ddt_probe@example.com 在类级 fixture 中确保存在
    （重复执行时注册返回 422，视为已存在）。
    """

    @pytest.fixture(scope="class", autouse=True)
    def ensure_probe_user(self):
        api = UsersAPI()
        resp = api.register("ddt_probe", "ddt_probe@example.com", "pass12345")
        assert resp.status_code in (200, 422), f"前置用户注册失败: {resp.text[:200]}"

    @allure.story("登录接口")
    @allure.title("数据驱动登录接口测试")
    @pytest.mark.api
    @pytest.mark.data_driven
    @pytest.mark.parametrize("case", _LOGIN_CASES, ids=[c["case_name"] for c in _LOGIN_CASES])
    def test_login_data_driven(self, case):
        api = UsersAPI()
        with allure.step(f"用例: {case['case_name']}（期望 {case['expected_status']}）"):
            response = api.login(case["email"], case["password"])
        with allure.step("验证状态码与预期一致"):
            assert response.status_code == int(case["expected_status"]), \
                f"用例[{case['case_name']}]期望{case['expected_status']}，实际{response.status_code}"
            if case["expected_status"] == "200":
                assert response.json()["user"]["token"], "登录成功应返回 token"
