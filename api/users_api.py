from core.api_client import APIClient
from core.logger import log


class UsersAPI:
    """被测系统 mini-blog（自研博客服务，见 sut/app.py）用户域 API 封装。

    契约要点（已对真实服务实测）：
    - 注册 POST   /api/users           body: {"user": {username, email, password}}
    - 登录 POST   /api/users/login     密码错误返回 404（该实现的特有行为）
    - 当前用户 GET/PUT /api/user       需 Authorization: Token <jwt>
    - 公开资料 GET /api/profiles/<username>
    """

    def __init__(self, client=None):
        # 支持注入共享的 APIClient，便于多业务对象在同一个会话中传递鉴权状态
        self.client = client or APIClient()

    def register(self, username, email, password):
        log.info(f"注册用户: {username}")
        return self.client.post('/users', json={
            "user": {"username": username, "email": email, "password": password}
        })

    def login(self, email, password):
        log.info(f"登录用户: {email}")
        return self.client.post('/users/login', json={
            "user": {"email": email, "password": password}
        })

    def get_current_user(self):
        log.info("获取当前登录用户")
        return self.client.get('/user')

    def update_current_user(self, user_data):
        log.info(f"更新当前用户: {list(user_data.keys())}")
        return self.client.put('/user', json={"user": user_data})

    def get_profile(self, username):
        log.info(f"获取用户公开资料: {username}")
        return self.client.get(f'/profiles/{username}')
