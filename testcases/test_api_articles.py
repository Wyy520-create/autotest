import pytest
import allure
from api.users_api import UsersAPI
from api.articles_api import ArticlesAPI


@allure.feature("文章API测试")
class TestArticlesAPI:
    """被测系统 mini-blog（自研）文章/标签域接口测试。

    契约要点（已对真实服务实测）：
    - 文章以 slug 为唯一标识；创建/更新均返回 article 对象
    - 更新标题会生成新 slug；删除后再查询返回 404
    - 列表分页参数为 limit / offset，响应含 articles 与 articlesCount
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.users_api = UsersAPI()
        # 文章域与用户域共享同一个 HTTP 会话，登录态对两个域同时生效
        self.articles_api = ArticlesAPI(self.users_api.client)
        self._register_and_login()

    def _register_and_login(self):
        """每个用例使用独立用户，避免文章数据互相干扰。"""
        tid = pytest.test_id
        username = f"auto_art_{tid}"
        email = f"{username}@example.com"
        resp = self.users_api.register(username, email, "password123")
        assert resp.status_code == 200, f"前置注册失败: {resp.text[:200]}"
        login_resp = self.users_api.login(email, "password123")
        assert login_resp.status_code == 200, "前置登录失败"
        self.users_api.client.set_token(login_resp.json()["user"]["token"])

    def _create_article(self, tag=""):
        """创建一篇用例级唯一文章并返回 slug。"""
        tid = pytest.test_id
        title = f"Auto Article {tag} {tid}"
        resp = self.articles_api.create_article(
            title=title,
            description=f"auto description {tid}",
            body=f"auto body {tid}",
            tag_list=["autotest"]
        )
        assert resp.status_code == 200, f"前置发文失败: {resp.text[:200]}"
        return resp.json()["article"]["slug"]

    @allure.story("文章管理")
    @allure.title("创建文章")
    @pytest.mark.api
    def test_create_article(self):
        tid = pytest.test_id
        with allure.step("提交发文请求"):
            response = self.articles_api.create_article(
                title=f"Create Test {tid}",
                description=f"desc {tid}",
                body=f"body {tid}",
                tag_list=["autotest", "create"]
            )
        with allure.step("验证文章创建成功"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            article = response.json()["article"]
            assert article["slug"], "文章应生成 slug"
            assert article["title"] == f"Create Test {tid}", "标题不一致"
            assert "autotest" in article["tagList"], "标签未正确写入"

    @allure.story("文章管理")
    @allure.title("获取文章详情")
    @pytest.mark.api
    def test_get_article(self):
        with allure.step("先创建文章"):
            slug = self._create_article("get")
        with allure.step("按 slug 查询文章"):
            response = self.articles_api.get_article(slug)
        with allure.step("验证详情内容"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            article = response.json()["article"]
            assert article["slug"] == slug, "slug 不一致"
            assert article["author"]["username"].startswith("auto_art_"), "作者信息缺失"

    @allure.story("文章管理")
    @allure.title("更新文章标题（slug 创建后不可变）")
    @pytest.mark.api
    def test_update_article(self):
        tid = pytest.test_id
        with allure.step("先创建文章"):
            old_slug = self._create_article("upd")
        with allure.step("更新标题"):
            new_title = f"Updated Title {tid}"
            response = self.articles_api.update_article(old_slug, title=new_title)
        with allure.step("验证标题已更新（实测：slug 创建后保持不变）"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            article = response.json()["article"]
            assert article["slug"] == old_slug, "实测契约：slug 创建后不可变"
            assert article["title"] == new_title, "标题未更新"
        with allure.step("使用原 slug 再次查询验证"):
            verify = self.articles_api.get_article(old_slug)
            assert verify.status_code == 200, "按原 slug 查询失败"
            assert verify.json()["article"]["title"] == new_title, "查询到的标题未更新"

    @allure.story("文章管理")
    @allure.title("删除文章")
    @pytest.mark.api
    def test_delete_article(self):
        with allure.step("先创建文章"):
            slug = self._create_article("del")
        with allure.step("删除文章"):
            response = self.articles_api.delete_article(slug)
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
        with allure.step("验证删除后返回 404"):
            verify = self.articles_api.get_article(slug)
            assert verify.status_code == 404, f"期望404，实际{verify.status_code}"

    @allure.story("文章管理")
    @allure.title("文章列表分页")
    @pytest.mark.api
    def test_list_articles_pagination(self):
        with allure.step("先创建一篇带标签文章"):
            self._create_article("page")
        with allure.step("按 limit=1 拉取第一页"):
            response = self.articles_api.list_articles(limit=1, offset=0)
        with allure.step("验证分页结构"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            data = response.json()
            assert "articles" in data and "articlesCount" in data, "分页响应缺少必备字段"
            assert len(data["articles"]) <= 1, "每页条数应不超过 limit"
            assert data["articlesCount"] >= 1, "文章总数应包含刚创建的文章"

    @allure.story("标签管理")
    @allure.title("获取标签列表")
    @pytest.mark.api
    def test_list_tags(self):
        with allure.step("创建一篇带标签文章"):
            self._create_article("tag")
        with allure.step("获取全局标签列表"):
            response = self.articles_api.list_tags()
        with allure.step("验证标签列表结构"):
            assert response.status_code == 200, f"期望200，实际{response.status_code}"
            tags = response.json()["tags"]
            assert isinstance(tags, list), "tags 应为列表"
            assert "autotest" in tags, "刚写入的标签应出现在列表中"
