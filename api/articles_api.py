from core.api_client import APIClient
from core.logger import log


class ArticlesAPI:
    """被测系统 mini-blog（自研博客服务，见 sut/app.py）文章/标签域 API 封装。

    分页约定：limit / offset 查询参数；文章以 slug 为唯一标识。
    """

    def __init__(self, client=None):
        # 支持注入共享的 APIClient，便于与用户域共用同一个鉴权会话
        self.client = client or APIClient()

    def list_articles(self, tag=None, author=None, limit=20, offset=0):
        params = {'limit': limit, 'offset': offset}
        if tag:
            params['tag'] = tag
        if author:
            params['author'] = author
        log.info(f"获取文章列表: {params}")
        return self.client.get('/articles', params=params)

    def get_feed(self, limit=20, offset=0):
        log.info(f"获取关注流: limit={limit}, offset={offset}")
        return self.client.get('/articles/feed', params={'limit': limit, 'offset': offset})

    def get_article(self, slug):
        log.info(f"获取文章详情: {slug}")
        return self.client.get(f'/articles/{slug}')

    def create_article(self, title, description, body, tag_list=None):
        log.info(f"创建文章: {title}")
        return self.client.post('/articles', json={
            "article": {
                "title": title,
                "description": description,
                "body": body,
                "tagList": tag_list or []
            }
        })

    def update_article(self, slug, **fields):
        log.info(f"更新文章: {slug}, 字段: {list(fields.keys())}")
        return self.client.put(f'/articles/{slug}', json={"article": fields})

    def delete_article(self, slug):
        log.info(f"删除文章: {slug}")
        return self.client.delete(f'/articles/{slug}')

    def favorite_article(self, slug):
        log.info(f"收藏文章: {slug}")
        return self.client.post(f'/articles/{slug}/favorite')

    def add_comment(self, slug, body):
        log.info(f"文章添加评论: {slug}")
        return self.client.post(f'/articles/{slug}/comments', json={"comment": {"body": body}})

    def list_comments(self, slug):
        log.info(f"获取文章评论: {slug}")
        return self.client.get(f'/articles/{slug}/comments')

    def delete_comment(self, slug, comment_id):
        log.info(f"删除评论: {slug} / {comment_id}")
        return self.client.delete(f'/articles/{slug}/comments/{comment_id}')

    def list_tags(self):
        log.info("获取标签列表")
        return self.client.get('/tags')