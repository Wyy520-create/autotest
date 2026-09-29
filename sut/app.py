#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mini-blog —— autotest 框架的自研被测系统（SUT, System Under Test）

一个迷你博客 API + Web 服务，契约风格参考 RealWorld 规范，
为 autotest 自动化框架提供稳定、零外部依赖的真实被测目标：
整个项目（被测系统 + 测试框架）完全自包含，不依赖任何第三方项目。

有意保留的"缺陷"（供安全/异常测试锚定，修复前请同步更新测试基线）：
  1. 注册缺字段时服务端返回 500（未做入参完整性校验）
  2. 空密码可注册成功（弱口令风险）
  3. 超长用户名无长度校验（256 字符可直接入库）
  4. XSS 脚本用户名被原样存储（存储型 XSS 风险）
  5. 密码错误 / 账号不存在统一返回 404
  6. Authorization 头只认 "Token" 前缀，其余返回 422

启动：
    pip install flask
    python sut/app.py            # 默认 127.0.0.1:8520，SQLite 自动建库
    python sut/app.py --port 9000 --db /tmp/blog.db
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, redirect, render_template_string, request
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "blog.db")
SECRET_KEY = "mini-blog-sut-secret"
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 天
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# 数据库层（SQLite，标准库实现，零额外依赖）
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    bio TEXT,
    image TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS article (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    body TEXT,
    tag_list TEXT DEFAULT '[]',
    author_id INTEGER NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    body TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS favorites (
    user_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    UNIQUE (user_id, article_id)
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 令牌（HMAC 签名的轻量 token，避免额外依赖 PyJWT）
# ---------------------------------------------------------------------------

def make_token(user_id):
    payload = base64.urlsafe_b64encode(
        json.dumps({"uid": user_id, "exp": time.time() + TOKEN_TTL}).encode()
    ).decode()
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token):
    try:
        payload, sig = token.rsplit(".", 1)
        expect = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data["uid"]
    except Exception:
        return None


def require_auth(view):
    """鉴权装饰器：无 Authorization 头返回 401；前缀非 Token 或令牌非法返回 422。"""

    @wraps(view)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return jsonify({"msg": "Missing Authorization Header"}), 401
        parts = auth.split()
        if len(parts) != 2 or parts[0] != "Token":
            return jsonify({"msg": "Invalid Authorization header, expected 'Token <token>'"}), 422
        uid = parse_token(parts[1])
        if uid is None:
            return jsonify({"msg": "Invalid or expired token"}), 422
        user = query_user(uid=uid)
        if user is None:
            return jsonify({"msg": "User not found"}), 422
        g.current_user = user
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# 数据访问与序列化
# ---------------------------------------------------------------------------

def query_user(uid=None, username=None, email=None):
    db = get_db()
    if uid is not None:
        return db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if username is not None:
        return db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if email is not None:
        return db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return None


def user_json(user, with_token=True):
    data = {
        "username": user["username"],
        "email": user["email"],
        "bio": user["bio"],
        "image": user["image"],
    }
    if with_token:
        data["token"] = make_token(user["id"])
    return {"user": data}


def profile_json(user):
    return {
        "profile": {
            "username": user["username"],
            "bio": user["bio"],
            "image": user["image"],
            "following": False,
        }
    }


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "article"


def unique_slug(title):
    db = get_db()
    base, slug, n = slugify(title), slugify(title), 2
    while db.execute("SELECT 1 FROM article WHERE slug=?", (slug,)).fetchone():
        slug = f"{base}-{n}"
        n += 1
    return slug


def article_json(row, viewer_id=None):
    author = query_user(uid=row["author_id"])
    favorited, fav_count = False, 0
    if viewer_id is not None:
        favorited = get_db().execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND article_id=?",
            (viewer_id, row["id"]),
        ).fetchone() is not None
    fav_count = get_db().execute(
        "SELECT COUNT(*) AS c FROM favorites WHERE article_id=?", (row["id"],)
    ).fetchone()["c"]
    return {
        "slug": row["slug"],
        "title": row["title"],
        "description": row["description"],
        "body": row["body"],
        "tagList": json.loads(row["tag_list"] or "[]"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "favorited": favorited,
        "favoritesCount": fav_count,
        "author": {
            "username": author["username"],
            "bio": author["bio"],
            "image": author["image"],
            "following": False,
        },
    }


def comment_json(row):
    author = query_user(uid=row["author_id"])
    return {
        "id": row["id"],
        "body": row["body"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "author": {"username": author["username"], "bio": author["bio"], "image": author["image"]},
    }


# ---------------------------------------------------------------------------
# 用户域 API
# ---------------------------------------------------------------------------

@app.post("/api/users")
def register():
    data = request.get_json(force=True)["user"]  # 缺陷1：缺字段时 KeyError 冒泡为 500
    username, email = data["username"], data["email"]
    password = data["password"]  # 缺陷2/3：无空密码校验、无长度/字符校验
    if not EMAIL_RE.match(email):
        return jsonify({"errors": {"body": ["invalid email format"]}}), 422
    db = get_db()
    if query_user(username=username) or query_user(email=email):
        return jsonify({"errors": {"body": ["User already registered"]}}), 422
    ts = now_iso()
    cur = db.execute(
        "INSERT INTO users (username, email, password, created_at, updated_at) VALUES (?,?,?,?,?)",
        (username, email, generate_password_hash(password), ts, ts),
    )
    db.commit()
    return jsonify(user_json(query_user(uid=cur.lastrowid))), 200


@app.post("/api/users/login")
def login():
    data = request.get_json(force=True)["user"]
    user = query_user(email=data["email"])
    # 缺陷5：账号不存在与密码错误统一返回 404，不区分两者（避免账号枚举）
    if user is None or not check_password_hash(user["password"], data["password"]):
        return jsonify({"errors": {"body": ["invalid email or password"]}}), 404
    return jsonify(user_json(user)), 200


@app.get("/api/user")
@require_auth
def get_current_user():
    return jsonify(user_json(g.current_user, with_token=False)), 200


@app.put("/api/user")
@require_auth
def update_current_user():
    data = request.get_json(force=True).get("user", {})
    db = get_db()
    for field in ("username", "email", "bio", "image"):
        if field in data:
            db.execute(f"UPDATE users SET {field}=?, updated_at=? WHERE id=?",
                       (data[field], now_iso(), g.current_user["id"]))
    db.commit()
    return jsonify(user_json(query_user(uid=g.current_user["id"]), with_token=False)), 200


@app.get("/api/profiles/<username>")
def get_profile(username):
    user = query_user(username=username)
    if user is None:
        return jsonify({"errors": {"body": ["profile not found"]}}), 404
    return jsonify(profile_json(user)), 200


# ---------------------------------------------------------------------------
# 文章 / 评论 / 标签 API
# ---------------------------------------------------------------------------

def list_articles_query(tag=None, author=None, limit=20, offset=0):
    sql = ("SELECT a.* FROM article a JOIN users u ON u.id=a.author_id WHERE 1=1")
    params = []
    if author:
        sql += " AND u.username=?"
        params.append(author)
    if tag:
        sql += " AND a.tag_list LIKE ?"
        params.append(f'%"{tag}"%')
    sql += " ORDER BY a.created_at DESC, a.id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return get_db().execute(sql, params).fetchall()


@app.get("/api/articles")
def list_articles():
    tag = request.args.get("tag")
    author = request.args.get("author")
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    rows = list_articles_query(tag, author, limit, offset)
    total = get_db().execute("SELECT COUNT(*) AS c FROM article").fetchone()["c"]
    return jsonify({"articles": [article_json(r) for r in rows], "articlesCount": total}), 200


@app.get("/api/articles/feed")
@require_auth
def get_feed():
    return jsonify({"articles": [], "articlesCount": 0}), 200


@app.post("/api/articles")
@require_auth
def create_article():
    data = request.get_json(force=True)["article"]
    db = get_db()
    ts = now_iso()
    slug = unique_slug(data["title"])
    cur = db.execute(
        "INSERT INTO article (slug, title, description, body, tag_list, author_id, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (slug, data["title"], data.get("description", ""), data.get("body", ""),
         json.dumps(data.get("tagList", [])), g.current_user["id"], ts, ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM article WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"article": article_json(row, g.current_user["id"])}), 200


def find_article(slug):
    return get_db().execute("SELECT * FROM article WHERE slug=?", (slug,)).fetchone()


@app.get("/api/articles/<slug>")
def get_article(slug):
    row = find_article(slug)
    if row is None:
        return jsonify({"errors": {"body": ["article not found"]}}), 404
    return jsonify({"article": article_json(row)}), 200


@app.put("/api/articles/<slug>")
@require_auth
def update_article(slug):
    row = find_article(slug)
    if row is None:
        return jsonify({"errors": {"body": ["article not found"]}}), 404
    data = request.get_json(force=True).get("article", {})
    db = get_db()
    for field in ("title", "description", "body"):
        if field in data:
            db.execute(f"UPDATE article SET {field}=?, updated_at=? WHERE id=?",
                       (data[field], now_iso(), row["id"]))
    db.commit()
    # 实测契约：slug 创建后不可变，仅内容更新
    return jsonify({"article": article_json(find_article(slug), g.current_user["id"])}), 200


@app.delete("/api/articles/<slug>")
@require_auth
def delete_article(slug):
    row = find_article(slug)
    if row is None:
        return jsonify({"errors": {"body": ["article not found"]}}), 404
    db = get_db()
    db.execute("DELETE FROM comment WHERE article_id=?", (row["id"],))
    db.execute("DELETE FROM favorites WHERE article_id=?", (row["id"],))
    db.execute("DELETE FROM article WHERE id=?", (row["id"],))
    db.commit()
    return jsonify({}), 200


@app.post("/api/articles/<slug>/favorite")
@require_auth
def favorite_article(slug):
    row = find_article(slug)
    if row is None:
        return jsonify({"errors": {"body": ["article not found"]}}), 404
    db = get_db()
    db.execute("INSERT OR IGNORE INTO favorites (user_id, article_id) VALUES (?,?)",
               (g.current_user["id"], row["id"]))
    db.commit()
    return jsonify({"article": article_json(find_article(slug), g.current_user["id"])}), 200


@app.get("/api/articles/<slug>/comments")
def list_comments(slug):
    row = find_article(slug)
    if row is None:
        return jsonify({"errors": {"body": ["article not found"]}}), 404
    rows = get_db().execute(
        "SELECT * FROM comment WHERE article_id=? ORDER BY id", (row["id"],)
    ).fetchall()
    return jsonify({"comments": [comment_json(r) for r in rows]}), 200


@app.post("/api/articles/<slug>/comments")
@require_auth
def add_comment(slug):
    row = find_article(slug)
    if row is None:
        return jsonify({"errors": {"body": ["article not found"]}}), 404
    body = request.get_json(force=True)["comment"]["body"]
    db = get_db()
    ts = now_iso()
    cur = db.execute(
        "INSERT INTO comment (body, article_id, author_id, created_at, updated_at) VALUES (?,?,?,?,?)",
        (body, row["id"], g.current_user["id"], ts, ts),
    )
    db.commit()
    new_row = db.execute("SELECT * FROM comment WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"comment": comment_json(new_row)}), 200


@app.delete("/api/articles/<slug>/comments/<int:comment_id>")
@require_auth
def delete_comment(slug, comment_id):
    row = get_db().execute("SELECT * FROM comment WHERE id=? AND article_id=?",
                           (comment_id, find_article(slug)["id"])).fetchone()
    if row is None:
        return jsonify({"errors": {"body": ["comment not found"]}}), 404
    get_db().execute("DELETE FROM comment WHERE id=?", (comment_id,))
    get_db().commit()
    return jsonify({}), 200


@app.get("/api/tags")
def list_tags():
    rows = get_db().execute("SELECT tag_list FROM article").fetchall()
    tags = []
    for r in rows:
        for t in json.loads(r["tag_list"] or "[]"):
            if t not in tags:
                tags.append(t)
    return jsonify({"tags": tags}), 200


# ---------------------------------------------------------------------------
# 迷你 Web 页面（供 UI 自动化测试使用）
# ---------------------------------------------------------------------------

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>mini-blog</title></head>
<body>
<h1>mini-blog</h1>
{% if user %}<h2 id="logged-user">Welcome, {{ user }}</h2>
{% else %}<a id="login-link" href="/login">Login</a>{% endif %}
<ul id="article-list">
{% for a in articles %}<li class="article-title">{{ a }}</li>
{% else %}<li class="article-title empty">No articles yet</li>
{% endfor %}
</ul>
</body>
</html>
"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>mini-blog login</title></head>
<body>
<h1>mini-blog</h1>
<form id="login-form" method="post" action="/login">
  <input id="username" name="username" type="text" placeholder="username">
  <input id="password" name="password" type="password" placeholder="password">
  <button id="submit" type="submit">Login</button>
</form>
{% if error %}<div id="login-error">{{ error }}</div>{% endif %}
</body>
</html>
"""


@app.get("/")
def index():
    rows = get_db().execute("SELECT title FROM article ORDER BY id DESC LIMIT 20").fetchall()
    return render_template_string(
        INDEX_HTML, user=request.args.get("user"), articles=[r["title"] for r in rows]
    )


@app.get("/login")
def login_page():
    return render_template_string(LOGIN_HTML, error=None)


@app.post("/login")
def login_form():
    user = query_user(username=request.form.get("username", ""))
    if user and check_password_hash(user["password"], request.form.get("password", "")):
        return redirect(f"/?user={user['username']}")
    return render_template_string(LOGIN_HTML, error="Invalid username or password"), 401


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="mini-blog 被测系统")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8520)
    parser.add_argument("--db", default=DB_PATH, help="SQLite 数据库文件路径")
    args = parser.parse_args()

    app.config["DB_PATH"] = args.db
    init_db()
    print(f"mini-blog SUT 已启动: http://{args.host}:{args.port}  (db: {args.db})")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
