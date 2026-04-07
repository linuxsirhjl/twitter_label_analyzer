# 社交媒体用户风险分析系统

从远程 MySQL 数据库读取用户数据，对用户进行多标签风险分类与画像生成，结果回写数据库，并支持定时调度与钉钉推送。

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 数据库 | MySQL（PyMySQL） |
| 模型调用 | OpenAI 兼容接口（内网部署 Qwen3.5-27B） |
| 定时调度 | APScheduler |
| URL 内容提取 | requests + BeautifulSoup4（支持代理） |
| 通知推送 | 钉钉机器人 Webhook |
| 配置管理 | YAML + python-dotenv |

---

## 项目结构

```
tweet-label-analyzer/
├── main.py                  # 手动执行入口
├── scheduler.py             # 定时调度入口
├── config.yaml              # 业务配置
├── .env                     # 敏感信息（DB密码、API Key）
├── requirements.txt
├── app/
│   ├── settings.py          # 统一配置加载
│   ├── db.py                # 数据库连接与事务封装
│   ├── models.py            # 数据模型（dataclass）
│   ├── constants.py         # 标签常量
│   ├── repositories/        # 数据访问层（所有 SQL 在此）
│   │   ├── user_repository.py       # 读取用户、回写结果
│   │   ├── tweets_repository.py
│   │   ├── replies_repository.py
│   │   ├── following_repository.py
│   │   ├── followers_repository.py
│   │   ├── political_repository.py  # 查询涉政用户
│   │   └── key_focus_repository.py  # 写入 key_focus_user 表
│   ├── services/            # 业务逻辑层
│   │   ├── user_analysis_service.py # 主流程编排
│   │   ├── rule_engine.py           # 规则预判（关注名单+关键词）
│   │   ├── llm_classifier.py        # LLM 标签判定与画像生成
│   │   ├── label_normalizer.py      # 标签归一化（唯一入口）
│   │   ├── text_cleaner.py          # 文本清洗与去重
│   │   ├── translator_service.py    # 翻译（可配置开关）
│   │   ├── url_enricher.py          # URL 展开与内容提取（支持代理）
│   │   └── dingtalk.py              # 钉钉推送
│   ├── prompts/
│   │   └── classify_user.txt        # LLM Prompt（外置）
│   └── utils/
│       ├── logger.py / retry.py / json_utils.py / language.py
└── src/                     # 原有翻译/分类模块（保留复用）
    ├── translator.py
    └── classifier.py
```

---

## 实现原理

### 分析流程（每个用户）

1. 从 `users_basic_info` 分页读取用户
2. 关联查询 `users_tweets`、`users_replies`、`users_following`、`users_followers`
3. 文本清洗 → **URL 展开提取内容** → 去重截断
4. **规则预判**：检查是否关注涉政敏感账号名单，关键词匹配
5. **LLM 判定**：将用户资料 + 文本样本 + 规则候选标签发给模型，返回标签 + 画像
6. 标签归一化（去重、排序、互斥处理）
7. 事务回写 `user_category` 和 `user_profile_summary`
8. 分析完成后，涉政用户同步写入 `key_focus_user` 表

### 标签互斥规则

- 命中任意敏感标签 → 不输出"无敏感倾向"
- 未命中任何敏感标签 → 只输出"无敏感倾向"
- 标签顺序固定：涉政 → 涉恐怖极端 → 涉及传播淫秽赌博 → 涉及网络犯罪或者网络暴力 → 涉及仇恨言论 → 无敏感倾向

---

## 快速开始

### 1. 安装依赖

```bash
cd tweet-label-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置

编辑 `.env`：

```
DB_PASSWORD=你的数据库密码
OPENAI_API_KEY=local
```

编辑 `config.yaml`，确认数据库地址和模型地址正确。

---

## 运行方式

### 手动执行

```bash
source .venv/bin/activate

# 全量分析（覆盖所有用户）
python main.py --workers 4

# 增量分析（只分析 user_category 为空的用户）
python main.py --workers 4 --only-empty

# 增量分析（只分析 user_profile_summary 为空的用户）
python main.py --workers 4 --only-empty-profile

# 指定批次大小
python main.py --workers 4 --batch-size 50

# 开启调试日志
python main.py --workers 4 --debug
```

### 定时调度

```bash
# 进入调度模式（按 config.yaml 中配置的时间每天自动触发）
python scheduler.py

# 立即执行一次（测试用，不等定时）
python scheduler.py --now
```

---

## 全量 vs 增量

在 `config.yaml` 中控制：

```yaml
analysis:
  update_only_empty_category: false   # true = 增量（只跑没有标签的用户）
  update_only_empty_profile: false    # true = 增量（只跑没有画像的用户）
```

或通过命令行参数覆盖：

```bash
python main.py --only-empty           # 等同于 update_only_empty_category: true
python main.py --only-empty-profile   # 等同于 update_only_empty_profile: true
```

---

## URL 短链展开

推文中常含 `t.co` 短链，系统会自动展开并抓取目标页面的 title / meta description，拼接到原文后送给模型分析，提升分类准确率。

### 代理配置（访问 t.co 需要代理）

```yaml
proxy:
  enabled: true
  http: "http://127.0.0.1:7897"
  https: "http://127.0.0.1:7897"
```

不需要代理时设 `enabled: false`。

---

## key_focus_user 表

每次分析完成后，系统自动将命中"涉政"标签的用户写入 `key_focus_user` 表（存在则更新，不存在则插入），字段包括：

| 字段 | 说明 |
|------|------|
| account | 账号 |
| account_id | 账号 ID |
| user_category | 标签 |
| user_profile_summary | 用户画像 |
| profile_url | 主页链接（https://x.com/{account}） |
| updated_at | 最后更新时间 |

---

## 修改定时执行时间

编辑 `config.yaml`：

```yaml
scheduler:
  hour: 12     # 每天几点执行（当前：12:00）
  minute: 0
  workers: 4
```

### 修改为每天多次执行

APScheduler 的 cron 触发器支持多个时间点，需修改 `scheduler.py` 中的 `add_job` 调用：

```python
# 每天 9:00 和 19:00 各执行一次
scheduler.add_job(run_analysis_job, trigger="cron", hour="9,19", minute=0, max_instances=1)
```

---

## 钉钉推送配置

```yaml
dingtalk:
  enabled: true
  webhook: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  secret_keyword: "需重点关注账号"   # 必须与钉钉机器人安全词一致
  at_mobiles: []
  at_user_ids: []
  is_at_all: false
  max_users_display: 20              # 涉政用户最多展示条数
```

推送内容包含：任务状态、耗时、成功/失败数、涉政用户列表（账号 + 主页链接 + 用户画像）。

---

## 涉政敏感账号名单

在 `config.yaml` 中维护，可随时增删，不需要改代码：

```yaml
political_sensitive_accounts:
  - "taocomic"
  - "chuxikuaile666"
  # ...
```

---

## 环境变量（.env）

| 变量 | 说明 |
|------|------|
| `DB_PASSWORD` | 数据库密码 |
| `OPENAI_API_KEY` | 模型 API Key（内网服务填 `local`） |
