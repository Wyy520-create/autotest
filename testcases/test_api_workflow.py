import pytest
import allure
from api.users_api import UsersAPI
from api.articles_api import ArticlesAPI


@allure.feature("API业务流程测试")
class TestAPIWorkflow:
    """跨接口业务流测试：模拟真实用户完整动线。

    说明：mini-blog 未提供用户删除接口，用户流以"改资料后验证"收尾；
    文章/评论数据在各用例末尾清理（删除文章会级联清理其评论）。
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.users_api = UsersAPI()
        # 文章域与用户域共享同一个 HTTP 会话，登录态对两个域同时生效
        self.articles_api = ArticlesAPI(self.users_api.client)
        self._register_and_login()

    def _register_and_login(self):
        tid = pytest.test_id
        username = f"auto_wf_{tid}"
        email = f"{username}@example.com"
        resp = self.users_api.register(username, email, "password123")
        assert resp.status_code == 200, f"前置注册失败: {resp.text[:200]}"
        login_resp = self.users_api.login(email, "password123")
        assert login_resp.status_code == 200, "前置登录失败"
        self.users_api.client.set_token(login_resp.json()["user"]["token"])
        return username

    def _create_article(self, tag=""):
        tid = pytest.test_id
        resp = self.articles_api.create_article(
            title=f"Workflow Article {tag} {tid}",
            description=f"wf desc {tid}",
            body=f"wf body {tid}",
            tag_list=["workflow"]
        )
        assert resp.status_code == 200, f"前置发文失败: {resp.text[:200]}"
        return resp.json()["article"]["slug"]

    @allure.story("用户完整流程")
    @allure.title("注册→登录→获取当前用户→更新资料→验证")
    @pytest.mark.api
    @pytest.mark.workflow
    def test_user_full_journey(self):
        with allure.step("1. 注册新用户"):
            tid = pytest.test_id
            username = f"auto_journey_{tid}"
            email = f"{username}@example.com"
            reg = self.users_api.register(username, email, "password123")
            assert reg.status_code == 200, "注册失败"
            assert reg.json()["user"]["token"], "注册应返回 token"

        with allure.step("2. 登录获取 token"):
            login = self.users_api.login(email, "password123")
            assert login.status_code == 200, "登录失败"
            self.users_api.client.set_token(login.json()["user"]["token"])

        with allure.step("3. 获取当前用户并核对身份"):
            cur = self.users_api.get_current_user()
            assert cur.status_code == 200, "获取当前用户失败"
            assert cur.json()["user"]["username"] == username, "当前用户身份不一致"

        with allure.step("4. 更新个人简介"):
            new_bio = f"journey bio {tid}"
            upd = self.users_api.update_current_user({"bio": new_bio})
            assert upd.status_code == 200, "更新资料失败"

        with allure.step("5. 验证更新结果"):
            verify = self.users_api.get_current_user()
            assert verify.json()["user"]["bio"] == new_bio, "资料更新未生效"

    @allure.story("文章完整流程")
    @allure.title("发文→查询→更新→收藏→删除→验证404")
    @pytest.mark.api
    @pytest.mark.workflow
    def test_article_full_lifecycle(self):
        tid = pytest.test_id

        with allure.step("1. 发布文章"):
            create_resp = self.articles_api.create_article(
                title=f"Lifecycle {tid}",
                description=f"lifecycle desc {tid}",
                body=f"lifecycle body {tid}",
                tag_list=["lifecycle"]
            )
            assert create_resp.status_code == 200, "发文失败"
            slug = create_resp.json()["article"]["slug"]

        with allure.step("2. 查询文章详情"):
            get_resp = self.articles_api.get_article(slug)
            assert get_resp.status_code == 200, "查询文章失败"
            assert get_resp.json()["article"]["title"] == f"Lifecycle {tid}", "标题不一致"

        with allure.step("3. 更新文章"):
            new_title = f"Lifecycle Updated {tid}"
            upd_resp = self.articles_api.update_article(slug, title=new_title)
            assert upd_resp.status_code == 200, "更新文章失败"
            new_slug = upd_resp.json()["article"]["slug"]

        with allure.step("4. 收藏文章"):
            fav_resp = self.articles_api.favorite_article(new_slug)
            assert fav_resp.status_code == 200, "收藏文章失败"
            assert fav_resp.json()["article"]["favorited"] is True, "收藏状态未生效"

        with allure.step("5. 删除文章"):
            del_resp = self.articles_api.delete_article(new_slug)
            assert del_resp.status_code == 200, "删除文章失败"

        with allure.step("6. 验证文章已不存在"):
            verify_resp = self.articles_api.get_article(new_slug)
            assert verify_resp.status_code == 404, "文章删除后应返回404"

    @allure.story("评论业务流")
    @allure.title("发文→评论→查看评论→删除评论")
    @pytest.mark.api
    @pytest.mark.workflow
    def test_comment_workflow(self):
        tid = pytest.test_id

        with allure.step("1. 发布文章"):
            slug = self._create_article("comment")

        with allure.step("2. 添加评论"):
            comment_body = f"workflow comment {tid}"
            add_resp = self.articles_api.add_comment(slug, comment_body)
            assert add_resp.status_code == 200, "添加评论失败"
            comment_id = add_resp.json()["comment"]["id"]

        with allure.step("3. 查看评论列表"):
            list_resp = self.articles_api.list_comments(slug)
            assert list_resp.status_code == 200, "获取评论列表失败"
            bodies = [c["body"] for c in list_resp.json()["comments"]]
            assert comment_body in bodies, "新评论未出现在列表中"

        with allure.step("4. 删除评论"):
            del_resp = self.articles_api.delete_comment(slug, comment_id)
            assert del_resp.status_code == 200, "删除评论失败"

        with allure.step("5. 清理文章"):
            self.articles_api.delete_article(slug)

    @allure.story("分页一致性")
    @allure.title("连续分页拉取结果不重叠")
    @pytest.mark.api
    @pytest.mark.workflow
    def test_pagination_consistency(self):
        tid = pytest.test_id

        with allure.step("1. 连续发布 3 篇文章"):
            slugs = set()
            for i in range(3):
                resp = self.articles_api.create_article(
                    title=f"Page Consistency {tid} {i}",
                    description=f"desc {i}",
                    body=f"body {i}"
                )
                assert resp.status_code == 200, f"第{i + 1}篇发文失败"
                slugs.add(resp.json()["article"]["slug"])

        with allure.step("2. 按作者过滤，以 limit=2 分两次拉取"):
            author = f"auto_wf_{tid}"
            page1 = self.articles_api.list_articles(author=author, limit=2, offset=0)
            page2 = self.articles_api.list_articles(author=author, limit=2, offset=2)
            assert page1.status_code == 200 and page2.status_code == 200, "分页查询失败"

        with allure.step("3. 验证两页 slug 无重叠且覆盖全部新文章"):
            s1 = {a["slug"] for a in page1.json()["articles"]}
            s2 = {a["slug"] for a in page2.json()["articles"]}
            assert not (s1 & s2), "两页之间存在重复数据"
            assert slugs <= (s1 | s2), "新发布的文章未全部出现在分页结果中"

        with allure.step("4. 清理测试文章"):
            for slug in slugs:
                self.articles_api.delete_article(slug)
