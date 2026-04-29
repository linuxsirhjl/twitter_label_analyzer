# 社交媒体用户风险分析系统

从远程 MySQL 数据库读取用户数据，对用户进行多标签风险分类与画像生成，结果回写数据库，并支持定时调度与钉钉推送。

## 新功能 ✨

- **多模态分析**：支持结合推文截图进行图文联合分析，提升分类准确率
- **性能监控**：每个用户分析完成后输出耗时统计
- **批次报告**：每1000个用户分析完成后，自动统计批次耗时并推送到钉钉群
- **数据库连接池**：使用 DBUtils 连接池管理数据库连接，支持多线程并发，避免频繁创建连接导致的性能问题

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 数据库 | MySQL（PyMySQL + DBUtils 连接池） |
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
│   ├── db.py                # 数据库连接池与事务封装（DBUtils）
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

#### 增量分析（推荐，只处理新增数据）

```bash
# 只分析 user_category 为空的用户（跳过已标注用户）
python main.py --only-empty --workers 4

# 只分析 user_profile_summary 为空的用户
python main.py --only-empty-profile --workers 4
```

#### 全量分析（重新处理所有用户）

```bash
# 重新分析所有用户，包括已标注的用户
python main.py --workers 4
```

#### 其他参数

```bash
# 指定批次大小（默认100）
python main.py --only-empty --batch-size 50

# 开启调试日志
python main.py --only-empty --debug

# 指定配置文件路径
python main.py --only-empty --config custom_config.yaml
```

### 定时调度

```bash
# 进入调度模式（按 config.yaml 中配置的时间每天自动触发）
python scheduler.py

# 立即执行一次（测试用，不等定时）
python scheduler.py --now
```

---

## 全量 vs 增量说明

| 模式 | 命令 | 说明 | 适用场景 |
|------|------|------|----------|
| **增量分析** | `python main.py --only-empty` | 只处理 `user_category` 为空的用户 | 日常运行，处理新增用户 |
| **全量分析** | `python main.py` | 重新分析所有用户，覆盖已有标签 | 标签定义修改后，需要重新标注 |

命令行参数会覆盖 `config.yaml` 中的配置：

```yaml
analysis:
  update_only_empty_category: false   # 默认全量
  update_only_empty_profile: false    # 默认全量
```

---

## URL 短链展开

推文中常含 `t.co` 短链，系统会自动展开并抓取目标页面的 title / meta description，拼接到原文后送给模型分析，提升分类准确率。

### 代理配置

**当前状态：已禁用**

```yaml
proxy:
  enabled: false  # 已禁用，不展开短链接
  http: "http://127.0.0.1:7897"
  https: "http://127.0.0.1:7897"
```

如需访问 `t.co` 短链并展开内容，设置 `enabled: true` 并确保代理服务可用。

---

## 多模态分析（图文联合）

系统支持结合推文截图进行多模态分析，提升对图片内容的理解能力。

### 数据库表结构

- **users_replies_and_tweets**：存储推文链接和截图文件名的映射关系
  - `链接`：推文链接（与 `users_tweets` 和 `users_replies` 表的 `被回复或转发帖子链接` 字段对应）
  - `名称`：截图文件名（不含路径）
  - `账号`：用户账号（注意：此表只有 `账号` 列，没有 `账号ID` 列）

### 截图路径规则

截图存放在本地路径：`D:\数据\用户"帖子"和"回复"数据截图\`

系统会自动拼接完整路径：`基础路径 + 名称字段`

### 工作流程

1. 查询 `users_replies_and_tweets` 表，获取用户的推文链接和截图文件名映射
2. 根据推文链接匹配 `users_tweets` 和 `users_replies` 中的内容
3. 将匹配到的截图编码为 base64 格式
4. 与文本内容一起发送给 LLM 进行多模态分析
5. 日志输出图片分析结果和截图数量

### 日志示例

```
INFO - 用户 example_user 找到 3 张截图
INFO - 用户 example_user 包含 3 张截图
INFO - 用户 example_user 最终标签: ['涉政']  LLM耗时: 45.2s  推理: 根据截图和文本内容判断...
INFO - 用户 example_user 分析完成，总耗时: 48.5s
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
  webhook: ""  # 从 .env 的 DINGTALK_WEBHOOK 读取
  secret_keyword: "需重点关注账号"   # 必须与钉钉机器人安全词一致
  at_mobiles: []
  at_user_ids: []
  is_at_all: false
  max_users_display: 20              # 涉政用户最多展示条数
```

**注意**：为了安全，webhook URL 应配置在 `.env` 文件中：
```bash
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### 推送内容

1. **任务完成报告**：任务状态、耗时、成功/失败数、涉政用户列表（账号 + 主页链接 + 用户画像）
2. **批次报告**（每1000个用户）：批次编号、批次耗时、平均每用户耗时

### 批次报告示例

```
批次 #1 完成: 已处理 1000 个用户
批次耗时: 3245.6秒
平均每用户: 3.2秒
```

---

## 性能监控

### 用户级耗时统计

每个用户分析完成后，日志会输出：
- LLM 推理耗时
- 总分析耗时（包括数据查询、文本处理、LLM调用、数据库写入）

```
INFO - 用户 example_user 最终标签: ['涉政']  LLM耗时: 45.2s  推理: ...
INFO - 用户 example_user 分析完成，总耗时: 48.5s
```

### 批次级统计

每处理完1000个用户，系统会：
1. 在日志输出批次统计信息
2. 自动推送批次报告到钉钉群
3. 重置计时器，开始下一批次统计

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

| 变量 | 说明 | 必填 |
|------|------|------|
| `DB_PASSWORD` | 数据库密码 | ✅ |
| `OPENAI_API_KEY` | 模型 API Key（内网服务填 `local`） | ✅ |
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook URL | ⚠️ 启用钉钉推送时必填 |

### 示例 .env 文件

```bash
# 数据库配置
DB_PASSWORD=your_database_password

# LLM API 配置
OPENAI_API_KEY=local

# 钉钉推送配置（可选）
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

---

## 性能优化

### 数据库连接池

系统使用 **DBUtils.PooledDB** 管理数据库连接，避免频繁创建/销毁连接导致的性能问题。

**连接池配置**（`app/db.py`）：
- `maxconnections=20`：最大连接数
- `mincached=2`：启动时预创建的空闲连接数
- `maxcached=10`：连接池中最多保留的空闲连接数
- `blocking=True`：连接池满时阻塞等待，而不是抛出异常
- `ping=1`：自动检测连接有效性，避免使用失效连接

**多线程并发**：
- 使用 `--workers 4` 参数时，4个线程会共享连接池
- 每个线程从池中获取连接，使用完毕后归还
- 避免了每次查询都创建新连接的开销

**性能提升**：
- 减少 TCP 握手和 MySQL 认证开销
- 避免触发 MySQL 最大连接数限制
- 消除多线程环境下的连接竞争和卡顿问题

如需调整连接池参数，修改 `app/db.py` 中的 `_init_pool()` 函数。

---

## 故障排查

### 1. 数据库列名错误

**错误信息**：`pymysql.err.OperationalError: (1054, "Unknown column '账号ID' in 'where clause'")`

**原因**：`users_replies_and_tweets` 表只有 `账号` 列，没有 `账号ID` 列

**解决方案**：已在代码中修复，使用 `账号` 列进行查询

---

### 2. 代理连接失败

**错误信息**：`ProxyError: Unable to connect to proxy... [WinError 10061] 由于目标计算机积极拒绝，无法连接`

**原因**：代理服务（如 Clash、V2Ray）未启动

**解决方案**：
- 方案1：启动代理服务，确保监听在配置的端口（如 7897）
- 方案2：禁用代理功能（推荐，如果不需要访问 t.co）
  ```yaml
  proxy:
    enabled: false
  ```

---

### 3. LLM 服务 500 错误

**错误信息**：`HTTP/1.1 500 INTERNAL SERVER ERROR` + `Connection refused` 到 127.0.0.1:5001

**原因**：Flask 服务（192.168.51.40:5000）无法连接到后端 vLLM 服务（127.0.0.1:5001）

**解决方案**：在服务器上重启 vLLM 服务
```bash
# 在 192.168.51.40 服务器上执行
cd /storage1/yqyd-dev
python -m vllm.entrypoints.openai.api_server \
    --model /path/to/Qwen3.5-27B \
    --port 5001 \
    --host 127.0.0.1
```

或检查 vLLM 服务的 systemd 状态：
```bash
systemctl status vllm.service
systemctl restart vllm.service
```

---

### 4. 截图文件路径错误

**错误信息**：`SyntaxError: invalid syntax` 在 `screenshot_repository.py`

**原因**：路径字符串中的中文引号与 Python 字符串引号冲突

**解决方案**：已修复，使用单引号包裹包含双引号的路径字符串

---

### 5. 日志轮转配置

系统已配置日志轮转：
- 单个日志文件最大 10MB
- 保留最近 5 个备份文件
- 自动清理旧日志

如需调整，修改 `app/utils/logger.py` 中的 `RotatingFileHandler` 参数。

---

### 6. 多线程运行时卡顿

**症状**：运行 `python main.py --workers 4` 时程序卡顿，按 Ctrl+C 后才恢复

**原因**：数据库连接池未配置或连接数不足

**解决方案**：
1. 确认已安装 `DBUtils`：
   ```bash
   pip install DBUtils
   ```

2. 检查 `app/db.py` 是否使用了连接池（应包含 `PooledDB` 导入）

3. 调整连接池参数（如果并发数很高）：
   ```python
   # app/db.py 中的 _init_pool() 函数
   maxconnections=20,  # 增加最大连接数
   maxcached=10,       # 增加空闲连接数
   ```

4. 检查 MySQL 服务器的 `max_connections` 配置：
   ```sql
   SHOW VARIABLES LIKE 'max_connections';
   ```

---
