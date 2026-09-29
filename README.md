# autotest —— 全栈自动化测试框架

基于 **Python + Pytest + Requests + Selenium** 的分层自动化测试框架，覆盖 **API / UI / 数据库 / 性能** 四个测试层次。

**被测系统 mini-blog 为本仓库自研**（`sut/` 目录，Flask + SQLite 单文件实现），框架代码同样全部原创：克隆仓库后无需任何外部服务，**3 条命令即可跑通全部用例**，Linux / Windows / macOS 通用。

## 特性

- **自研被测系统**：依赖仅 `flask>=2.0`，Python 3.8-3.12 全兼容，无版本地狱
- **40+ 条 API 用例**：对真实服务实测契约（含注册/登录/资料/文章/评论/收藏/标签全链路 + 异常与安全的 6 类场景）
- **数据库用例**：直接校验 SQLite 持久层（CRUD、条件查询、多表关联、事务回滚）
- **UI 用例**：POM 页面对象模式 + CSV 数据驱动 + 失败自动截图
- **性能压测**：Locust 脚本（读多写少的真实用户行为模型）
- **CI 全自包含**：GitHub Actions 自动安装依赖 → 启动被测系统 → 执行 API/DB/UI 用例

## 目录结构

```
autotest/
├── api/                    # 业务 API 封装（users_api / articles_api）
├── config/
│   └── config.yaml         # 框架配置（浏览器 / 被测地址 / 数据库等）
├── core/                   # 框架核心
│   ├── api_client.py       #   HTTP 客户端：Session 复用、Token 鉴权、超时重试
│   ├── db_manager.py       #   数据库封装：SQLite / MySQL 双驱动，语义化 CRUD
│   ├── logger.py           #   标准库 logging 封装（控制台 + 文件双输出）
│   └── webdriver.py        #   WebDriver 工厂：webdriver-manager 自动管理驱动
├── pages/                  # 页面对象（POM）
│   ├── base.py             #   基类：定位器、显式等待、常用操作
│   ├── login.py            #   登录页
│   └── home.py             #   首页
├── performance/
│   └── locustfile.py       # Locust 压测脚本
├── sut/                    # 被测系统 mini-blog（自研）
│   ├── app.py              #   单文件实现：API + 迷你 Web 页面 + SQLite
│   └── requirements.txt    #   被测系统依赖（仅 flask>=2.0）
├── testcases/              # 测试用例（api / ui / db / workflow / exception / data_driven）
├── testdata/               # CSV 测试数据
├── utils/
│   └── data_provider.py    # CSV 数据读取工具
├── conftest.py             # pytest 钩子与共享 fixture
├── pytest.ini              # pytest 配置（markers / 用例发现规则）
├── run.py                  # 统一测试入口
└── requirements.txt        # 框架依赖
```

## 快速开始

### 1. 环境要求

- Python 3.8+（推荐 3.10+）
- UI 用例需要本机安装 **Chrome 或 Firefox 任一浏览器**（驱动由 webdriver-manager 自动下载，无需手工安装）；无显示环境（CI / SSH）请把 `config/config.yaml` 的 `browser.headless` 改为 `true`

> 提示：部分 Linux 发行版只有 `python3` 命令，下文 `python` 请视情况替换为 `python3`。
>
> Linux 注意：Ubuntu 的 Firefox 是 snap 包，在容器 / 受限 shell 中可能因 snap 权限无法启动；此时推荐安装 Chrome，或用环境变量 `AUTOTEST_CHROME_BINARY` 指向一个独立的 Chrome for Testing 二进制。

### 2. 启动被测系统

Linux / macOS：

```bash
pip install -r requirements.txt
pip install -r sut/requirements.txt
python sut/app.py
```

Windows（CMD / PowerShell 同理）：

```bat
pip install -r requirements.txt
pip install -r sut/requirements.txt
python sut\app.py
```

启动成功后输出：`mini-blog SUT 已启动: http://127.0.0.1:8520`，SQLite 数据库文件自动创建于 `sut/blog.db`。

### 3. 运行测试

新开一个终端（保持被测系统运行）：

```bash
python run.py api      # 仅 API 用例（约 40 条）
python run.py db       # 仅数据库用例
python run.py ui       # 仅 UI 用例（需 Chrome）
python run.py smoke    # 仅冒烟用例
python run.py          # 全部用例
```

也可以直接使用 pytest：

```bash
pytest -m "api or db"                 # 按标记筛选
pytest testcases/test_api_users.py    # 指定文件
pytest --reruns 1                     # 失败重跑 1 次
```

### 4. 查看报告

```bash
# HTML 报告
pytest --html=reports/report.html --self-contained-html

# Allure 报告
pytest --alluredir=reports/allure-results
allure serve reports/allure-results
```

运行日志输出至 `logs/autotest_YYYYMMDD.log`；UI 用例失败截图保存在 `reports/screenshots/` 并自动附加到 Allure 报告。

## 配置说明（config/config.yaml）

| 配置项 | 说明 |
| --- | --- |
| `browser.name` / `browser.headless` | UI 浏览器类型与无头开关 |
| `environment.base_url` | 被测系统 Web 地址 |
| `api.base_url` | 被测系统 API 地址 |
| `api.token_prefix` | 鉴权头前缀，mini-blog 契约为 `Token` |
| `database.path` | SQLite 库文件，默认 `sut/blog.db`；可用环境变量 `AUTOTEST_DB_PATH` 覆盖 |

环境变量汇总：

| 变量 | 作用 |
| --- | --- |
| `AUTOTEST_DB_PATH` | 覆盖数据库文件路径（CI 中指向独立测试库） |
| `AUTOTEST_BASE_URL` | 覆盖被测系统 Web 地址 |
| `AUTOTEST_CHROME_BINARY` | 指定 Chrome 二进制路径（snap 受限环境 / 多版本共存时使用） |

## 被测系统 mini-blog

单文件 Flask 应用（`sut/app.py`，约 550 行），实现用户 / 文章 / 评论 / 收藏 / 标签域 API 与迷你 Web 页面（供 UI 用例）。

**有意保留的"缺陷"**（作为安全与异常测试锚点，修复前请同步更新测试基线）：

1. 注册缺字段时返回 500（未做入参完整性校验）
2. 空密码可注册成功（弱口令风险）
3. 超长用户名无长度校验
4. XSS 脚本用户名被原样存储（存储型 XSS 风险）
5. 密码错误 / 账号不存在统一返回 404
6. Authorization 头只认 `Token` 前缀，其余返回 422

常用启动参数：`python sut/app.py --port 9000 --db /tmp/blog.db`

## 性能压测

```bash
pip install locust
locust -f performance/locustfile.py --headless -u 10 -r 2 -t 60s --host http://127.0.0.1:8520
```

## 持续集成

`.github/workflows/ci.yml`：push / PR 自动触发，CI 内自动安装依赖、启动被测系统并执行 API+DB 与 UI（无头 Chrome）两组用例，Allure 结果作为构建产物上传。

## License

MIT License，Copyright (c) 2026 余阳辉
