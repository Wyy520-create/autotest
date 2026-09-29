import pytest
import allure
from api.users_api import UsersAPI


@allure.feature("用户API测试")
class TestUsersAPI:
    """被测系统 mini-blog（自研）用户域接口测试。

    契约要点（已对真实服务实测）：
    - 注册 POST /api/users，响应 200 且 body.user 含 token
    - 登录 POST /api/users/login，密码错误返回 404（该实现特有行为）
    - 当前用户 GET/PUT /api/user，需 Authorization: Token <jwt>
    - 公开资料 GET /api/profiles/<username>，无需登录
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.api = UsersAPI()

    def _register_and_login(self, tag="user"):
        """注册并登录一个用例级唯一用户（凭 pytest.test_id 隔离数据），返回 (username, email)。"""
        tid = pytest.test_id
        username = f"auto_{tag}_{tid}"
        email = f"{username}@example.com"
        password = "password123"
        resp = self.api.register(username, email, password)
        assert resp.status_code == 200, f"前置注册失败: {resp.text[:200]}"
        login_resp = self.api.login(email, password)
        assert login_resp.status_code == 200, "前置登录失败"
        token = login_resp.json()["user"]["token"]
        self.api.client.set_token(token)
        return username, email

    @allure.story("用户管理")
    @allure.title("注册新用户")
    @pytest.mark.api
    def test_register_user(self):
        tid = pytest.test_id
        username = f"auto_reg_{tid}"
        with allure.step("提交注册请求"):
            response = self.api.register(username, f"{username}@example.com", "password123")
        with allure.step("验证响应状态码与数据结构"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            user = response.json()["user"]
            assert user["username"] == username, "注册后用户名不一致"
            assert user["token"], "注册响应应携带 token"
            allure.attach(user["token"][:30] + "...", name="Token前缀", attachment_type=allure.attachment_type.TEXT)

    @allure.story("用户管理")
    @allure.title("用户登录")
    @pytest.mark.api
    def test_login_user(self):
        username = f"auto_login_{pytest.test_id}"
        email = f"{username}@example.com"
        with allure.step("先注册前置用户"):
            reg = self.api.register(username, email, "password123")
            assert reg.status_code == 200, "前置注册失败"
        with allure.step("使用正确凭据登录"):
            response = self.api.login(email, "password123")
        with allure.step("验证登录成功并返回 token"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            assert response.json()["user"]["token"], "登录响应应携带 token"

    @allure.story("用户管理")
    @allure.title("获取当前登录用户信息")
    @pytest.mark.api
    def test_get_current_user(self):
        with allure.step("注册并登录"):
            username, _ = self._register_and_login("cur")
        with allure.step("携带 token 获取当前用户"):
            response = self.api.get_current_user()
        with allure.step("验证返回的正是当前登录用户"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            assert response.json()["user"]["username"] == username, "当前用户与登录用户不一致"

    @allure.story("用户管理")
    @allure.title("更新当前用户信息")
    @pytest.mark.api
    def test_update_current_user(self):
        with allure.step("注册并登录"):
            self._register_and_login("upd")
        with allure.step("更新 bio 字段"):
            new_bio = f"auto bio {pytest.test_id}"
            response = self.api.update_current_user({"bio": new_bio})
        with allure.step("验证更新生效"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            assert response.json()["user"]["bio"] == new_bio, "bio 更新未生效"
            verify = self.api.get_current_user()
            assert verify.json()["user"]["bio"] == new_bio, "重新查询后 bio 不一致"

    @allure.story("用户管理")
    @allure.title("获取用户公开资料")
    @pytest.mark.api
    def test_get_user_profile(self):
        with allure.step("注册一个用户"):
            username, _ = self._register_and_login("prof")
        with allure.step("无需登录即可访问公开资料页"):
            # 公开资料接口不需要鉴权，先清掉 Authorization 头模拟匿名访问
            self.api.client.session.headers.pop("Authorization", None)
            response = self.api.get_profile(username)
        with allure.step("验证资料内容"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            profile = response.json()["profile"]
            assert profile["username"] == username, "资料页用户名不一致"
            assert "following" in profile, "资料页应包含 following 字段"
