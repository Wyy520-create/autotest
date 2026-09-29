import pytest
import allure
from api.users_api import UsersAPI
from api.articles_api import ArticlesAPI


@allure.feature("API异常与边界测试")
class TestAPIException:
    """异常场景与边界值测试。

    所有断言均基于对真实被测服务的实测行为（见各用例注释）。
    其中 4 条用例锚定被测系统真实缺陷，作为回归基线：
    - 缺字段注册返回 500（预期应为 400/422）
    - 空密码可注册成功（预期应被拒绝）
    - 256 字符超长用户名可注册（预期应有长度校验）
    - XSS 脚本用户名被原样存储（存储型 XSS 风险）
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.users_api = UsersAPI()
        self.articles_api = ArticlesAPI()

    def _register(self, username, email, password="password123"):
        return self.users_api.register(username, email, password)

    @allure.story("认证异常")
    @allure.title("密码错误登录返回404")
    @pytest.mark.api
    @pytest.mark.exception
    def test_login_wrong_password(self):
        tid = pytest.test_id
        email = f"auto_exc_{tid}@example.com"
        with allure.step("注册前置用户"):
            assert self._register(f"auto_exc_{tid}", email).status_code == 200
        with allure.step("使用错误密码登录"):
            response = self.users_api.login(email, "wrong_password")
        with allure.step("验证返回 404（该实现将凭据错误统一为 404）"):
            assert response.status_code == 404, f"期望404，实际{response.status_code}"

    @allure.story("参数校验")
    @allure.title("无效邮箱格式注册返回422")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_invalid_email(self):
        with allure.step("提交无效邮箱"):
            response = self._register(f"auto_inv_{pytest.test_id}", "not-an-email")
        with allure.step("验证返回 422"):
            assert response.status_code == 422, f"期望422，实际{response.status_code}"

    @allure.story("重复数据")
    @allure.title("重复用户名注册返回422")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_duplicate_username(self):
        tid = pytest.test_id
        username = f"auto_dup_{tid}"
        with allure.step("首次注册成功"):
            assert self._register(username, f"{username}@example.com").status_code == 200
        with allure.step("换邮箱重复用户名再注册"):
            response = self._register(username, f"another_{tid}@example.com")
        with allure.step("验证返回 422"):
            assert response.status_code == 422, f"期望422，实际{response.status_code}"

    @allure.story("重复数据")
    @allure.title("重复邮箱注册返回422")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_duplicate_email(self):
        tid = pytest.test_id
        email = f"auto_dupe_{tid}@example.com"
        with allure.step("首次注册成功"):
            assert self._register(f"auto_dupe_a_{tid}", email).status_code == 200
        with allure.step("换用户名重复邮箱再注册"):
            response = self._register(f"auto_dupe_b_{tid}", email)
        with allure.step("验证返回 422"):
            assert response.status_code == 422, f"期望422，实际{response.status_code}"

    @allure.story("缺陷锚定")
    @allure.title("缺字段注册返回500（缺陷：应为400/422）")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_missing_fields(self):
        with allure.step("提交缺少 email/password 的注册请求"):
            response = self.users_api.client.post('/users', json={"user": {"username": f"only_name_{pytest.test_id}"}})
        with allure.step("锚定真实缺陷：服务返回 500 而非参数错误码"):
            assert response.status_code == 500, f"缺陷基线=500，实际{response.status_code}"
            allure.attach("缺字段注册触发服务端 500（ORM 层空值异常），预期应为 400/422",
                          name="缺陷说明", attachment_type=allure.attachment_type.TEXT)

    @allure.story("缺陷锚定")
    @allure.title("空密码注册成功（缺陷：应被拒绝）")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_empty_password(self):
        with allure.step("提交空密码注册"):
            response = self._register(f"auto_emptypwd_{pytest.test_id}", f"auto_emptypwd_{pytest.test_id}@example.com", "")
        with allure.step("锚定真实缺陷：空密码被接受"):
            assert response.status_code == 200, f"缺陷基线=200，实际{response.status_code}"
            allure.attach("空密码注册被放行，存在弱口令风险，预期应返回 400/422",
                          name="缺陷说明", attachment_type=allure.attachment_type.TEXT)

    @allure.story("缺陷锚定")
    @allure.title("256字符超长用户名注册成功（缺陷：无长度校验）")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_overlong_username(self):
        with allure.step("提交 256 字符用户名（末尾拼接用例ID保证唯一）"):
            # 248 个填充字符 + 8 位用例ID = 256 字符，既触发长度边界又避免撞库
            overlong_name = "a" * 248 + pytest.test_id
            response = self._register(overlong_name, f"auto_long_{pytest.test_id}@example.com")
        with allure.step("锚定真实缺陷：超长输入未校验"):
            assert response.status_code == 200, f"缺陷基线=200，实际{response.status_code}"
            allure.attach("用户名无长度上限校验（256 字符成功入库），可能撑爆展示层布局",
                          name="缺陷说明", attachment_type=allure.attachment_type.TEXT)

    @allure.story("缺陷锚定")
    @allure.title("XSS脚本用户名原样存储（缺陷：存储型XSS）")
    @pytest.mark.api
    @pytest.mark.exception
    def test_register_xss_username(self):
        # 拼接用例ID保证每次运行的用户名唯一（服务侧无过滤，历史脏数据会撞 422）
        xss_payload = f'<script>alert("xss_{pytest.test_id}")</script>'
        with allure.step("提交含脚本的用户名"):
            response = self._register(xss_payload, f"auto_xss_{pytest.test_id}@example.com")
        with allure.step("锚定真实缺陷：脚本被原样存储"):
            assert response.status_code == 200, f"缺陷基线=200，实际{response.status_code}"
            stored = response.json()["user"]["username"]
            assert stored == xss_payload, "脚本内容应原样返回（证明未做过滤）"
            allure.attach("恶意脚本未经过滤直接入库，前端渲染资料页时将触发存储型 XSS",
                          name="缺陷说明", attachment_type=allure.attachment_type.TEXT)

    @allure.story("权限测试")
    @allure.title("未携带Token访问受保护接口返回401")
    @pytest.mark.api
    @pytest.mark.exception
    def test_unauthorized_access(self):
        with allure.step("清除 Authorization 头后访问 /user"):
            self.users_api.client.session.headers.pop("Authorization", None)
            response = self.users_api.get_current_user()
        with allure.step("验证返回 401"):
            assert response.status_code == 401, f"期望401，实际{response.status_code}"

    @allure.story("认证契约")
    @allure.title("Bearer前缀Token被拒绝（契约要求Token前缀）")
    @pytest.mark.api
    @pytest.mark.exception
    def test_bearer_prefix_rejected(self):
        tid = pytest.test_id
        email = f"auto_bearer_{tid}@example.com"
        with allure.step("注册并登录拿 token"):
            assert self._register(f"auto_bearer_{tid}", email).status_code == 200
            login = self.users_api.login(email, "password123")
            token = login.json()["user"]["token"]
        with allure.step("使用 Bearer 前缀访问（被测系统契约要求 Token 前缀）"):
            self.users_api.client.session.headers["Authorization"] = f"Bearer {token}"
            response = self.users_api.get_current_user()
        with allure.step("验证被 422 拒绝"):
            assert response.status_code == 422, f"期望422，实际{response.status_code}"

    @allure.story("404错误")
    @allure.title("查询不存在的文章返回404")
    @pytest.mark.api
    @pytest.mark.exception
    def test_get_nonexistent_article(self):
        with allure.step("查询随机 slug"):
            response = self.articles_api.get_article(f"not-exist-slug-{pytest.test_id}")
        with allure.step("验证返回 404"):
            assert response.status_code == 404, f"期望404，实际{response.status_code}"

    @allure.story("404错误")
    @allure.title("查询不存在的用户资料返回404")
    @pytest.mark.api
    @pytest.mark.exception
    def test_get_nonexistent_profile(self):
        with allure.step("查询随机用户名"):
            response = self.users_api.get_profile(f"no_such_user_{pytest.test_id}")
        with allure.step("验证返回 404"):
            assert response.status_code == 404, f"期望404，实际{response.status_code}"

    @allure.story("方法不支持")
    @allure.title("PATCH方法访问返回404（路由不存在）")
    @pytest.mark.api
    @pytest.mark.exception
    def test_method_not_allowed(self):
        with allure.step("对未注册路由使用 PATCH"):
            response = self.users_api.client.request("PATCH", "/users/1")
        with allure.step("验证返回 404"):
            assert response.status_code == 404, f"期望404，实际{response.status_code}"
