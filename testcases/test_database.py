import pytest
import allure
from core.db_manager import DBManager


@allure.feature("数据库测试")
class TestDatabase:
    """针对被测系统 mini-blog（自研，见 sut/app.py）SQLite 库的持久层测试。

    真实表结构（sut/app.py SCHEMA 定义）：
    - users(id, username, email, password, bio, image, created_at, updated_at)
    - article(id, slug, title, description, body, tag_list, author_id, created_at, updated_at)
    - comment(id, body, article_id, author_id, created_at, updated_at)
    运行前通过环境变量 AUTOTEST_DB_PATH 指向 sut/blog.db。
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.db = DBManager()
        self.db.connect()
        yield
        self.db.disconnect()

    def _test_username(self):
        return f"db_{pytest.test_id}"

    @allure.story("连接测试")
    @allure.title("数据库连接测试")
    @pytest.mark.db
    def test_db_connection(self):
        with allure.step("验证数据库连接"):
            assert self.db.connection is not None, "数据库连接失败"
            assert self.db.cursor is not None, "游标创建失败"

    @allure.story("查询测试")
    @allure.title("查询用户表数据")
    @pytest.mark.db
    def test_select_users(self):
        with allure.step("查询用户表前 10 条"):
            results = self.db.select('users', limit=10)
            assert results is not None, "查询失败"
            assert isinstance(results, list), "结果应为列表"
            if results:
                allure.attach(str(list(results[0].keys())), name="表字段",
                              attachment_type=allure.attachment_type.TEXT)

    @allure.story("查询测试")
    @allure.title("统计用户表记录数")
    @pytest.mark.db
    def test_count_users(self):
        with allure.step("统计用户数量"):
            count = self.db.count('users')
            assert count >= 0, "记录数应为非负数"
            allure.attach(str(count), name="用户数量", attachment_type=allure.attachment_type.TEXT)

    @allure.story("插入测试")
    @allure.title("向用户表插入测试数据")
    @pytest.mark.db
    def test_insert_data(self):
        username = self._test_username()
        with allure.step("插入测试用户"):
            test_data = {
                'username': username,
                'email': f"{username}@example.com",
                'password': 'dbpass123',
                'created_at': '2026-09-19 00:00:00',
                'updated_at': '2026-09-19 00:00:00'
            }
            affected = self.db.insert('users', test_data)
            assert affected == 1, "插入应影响1行"

    @allure.story("更新测试")
    @allure.title("更新用户表测试数据")
    @pytest.mark.db
    def test_update_data(self):
        username = self._test_username()
        with allure.step("先插入前置数据"):
            self.db.insert('users', {
                'username': username,
                'email': f"{username}@example.com",
                'password': 'dbpass123',
                'created_at': '2026-09-19 00:00:00',
                'updated_at': '2026-09-19 00:00:00'
            })
        with allure.step("更新 bio 字段"):
            update_data = {'bio': f"db bio {pytest.test_id}"}
            affected = self.db.update('users', update_data, 'username=?', (username,))
            assert affected == 1, "更新应影响1行"
        with allure.step("验证更新结果"):
            rows = self.db.select('users', columns='bio', where_clause='username=?', where_params=(username,))
            assert rows and rows[0]['bio'] == update_data['bio'], "更新未生效"

    @allure.story("删除测试")
    @allure.title("删除用户表测试数据")
    @pytest.mark.db
    def test_delete_data(self):
        username = self._test_username()
        with allure.step("先插入前置数据"):
            self.db.insert('users', {
                'username': username,
                'email': f"{username}@example.com",
                'password': 'dbpass123',
                'created_at': '2026-09-19 00:00:00',
                'updated_at': '2026-09-19 00:00:00'
            })
        with allure.step("删除测试数据"):
            affected = self.db.delete('users', 'username=?', (username,))
            assert affected == 1, "删除应影响1行"
        with allure.step("验证已删除"):
            count = self.db.count('users', 'username=?', (username,))
            assert count == 0, "数据应已删除"

    @allure.story("条件查询")
    @allure.title("按用户名条件查询")
    @pytest.mark.db
    def test_select_with_condition(self):
        username = self._test_username()
        with allure.step("先插入前置数据"):
            self.db.insert('users', {
                'username': username,
                'email': f"{username}@example.com",
                'password': 'dbpass123',
                'created_at': '2026-09-19 00:00:00',
                'updated_at': '2026-09-19 00:00:00'
            })
        with allure.step("按条件查询"):
            results = self.db.select('users', where_clause='username=?', where_params=(username,), limit=5)
            assert results is not None and len(results) == 1, "条件查询应命中1条"
        with allure.step("清理数据"):
            self.db.delete('users', 'username=?', (username,))

    @allure.story("多表关联")
    @allure.title("文章-作者关联查询")
    @pytest.mark.db
    def test_join_query(self):
        with allure.step("执行 article 与 users 的关联查询"):
            sql = """
            SELECT u.username AS author, a.title, a.slug
            FROM article a
            LEFT JOIN users u ON a.author_id = u.id
            LIMIT 10
            """
            results = self.db.execute_query(sql)
            assert results is not None, "关联查询失败"
            allure.attach(f"命中 {len(results)} 行", name="查询结果", attachment_type=allure.attachment_type.TEXT)

    @allure.story("事务测试")
    @allure.title("事务回滚测试")
    @pytest.mark.db
    def test_transaction_rollback(self):
        username = f"rollback_{pytest.test_id}"
        with allure.step("绕过自动提交，直接执行 INSERT"):
            # DBManager.execute_update 设计为自动提交，验证回滚需直接操作游标
            self.db.cursor.execute(
                "INSERT INTO users (username, email, password, created_at, updated_at) VALUES (?,?,?,?,?)",
                (username, f"{username}@example.com", 'rollback', '2026-09-19 00:00:00', '2026-09-19 00:00:00'))
        with allure.step("回滚事务"):
            self.db.connection.rollback()
        with allure.step("验证数据不存在"):
            count = self.db.count('users', 'username=?', (username,))
            assert count == 0, "数据应已回滚"
