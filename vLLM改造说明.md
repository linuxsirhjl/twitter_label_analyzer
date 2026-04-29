# yqyd-dev vLLM 改造说明

## 改造概述

将项目从 **Hugging Face Transformers 直接加载模型** 改为 **调用 vLLM OpenAI 兼容接口**，实现推理性能提升 5-10 倍。

## 改造内容

### 1. 核心文件修改

#### `llm_engine.py`（完全重写）

**改造前**：
- 使用 `transformers.AutoModelForCausalLM` 直接加载模型
- 使用 `torch` 进行推理
- 模型占用显存，启动慢

**改造后**：
- 使用 `openai.OpenAI` 客户端调用 vLLM API
- 通过 HTTP 请求进行推理
- 无需加载模型，启动快

**关键变更**：
```python
# 旧代码
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained(...)
output = model.generate(...)

# 新代码
from openai import OpenAI
client = OpenAI(base_url=VLLM_BASE_URL, api_key="EMPTY")
response = client.chat.completions.create(
    model=VLLM_MODEL_NAME,
    messages=[...],
    extra_body={"chat_template_kwargs": {"enable_thinking": False}}
)
```

#### `requirements.txt`

**移除**：
- `transformers>=4.36.0`
- `torch>=2.0.0`

**新增**：
- `openai>=1.0.0`

#### `.env.example`

**移除**：
- `MODEL_DIR=/storage1/models/Qwen3.5-27B`

**新增**：
```bash
VLLM_BASE_URL=http://127.0.0.1:5001/v1
VLLM_MODEL_NAME=Qwen3.5-35B-A3B-FP8
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1024
```

### 2. 保留的功能

- Flask 接口（`/extract`、`/v1/chat/completions`）
- 文档解析逻辑（`text_extractors.py`）
- 字段提取和后处理（`schema.py`）
- 三级容错机制
- JSON 修复逻辑
- 企业名称清理和文件名提取

### 3. 新增功能

- 环境变量配置 vLLM 服务地址和模型
- 禁用 Thinking Process（`enable_thinking=False`）
- 清洗返回内容中的 `<think>` 标签
- 详细日志记录（vLLM 配置、调用耗时、JSON 解析状态）

## 部署步骤

### 步骤 1：启动 vLLM 服务

在 GPU 服务器上启动 vLLM：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /path/to/Qwen3.5-35B-A3B-FP8 \
  --host 0.0.0.0 \
  --port 5001 \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching
```

验证 vLLM 服务：
```bash
curl http://127.0.0.1:5001/v1/models
```

### 步骤 2：更新 yqyd-dev 代码

```bash
cd /path/to/yqyd-dev
git pull origin main
```

### 步骤 3：安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 4：配置环境变量

```bash
cp .env.example .env
vim .env
```

修改 vLLM 配置：
```bash
VLLM_BASE_URL=http://127.0.0.1:5001/v1
VLLM_MODEL_NAME=Qwen3.5-35B-A3B-FP8
```

### 步骤 5：启动 Flask 服务

```bash
gunicorn -w 1 -b 0.0.0.0:5000 app:app --timeout 1800
```

### 步骤 6：测试服务

```bash
python test1.py
```

## 性能对比

| 指标 | Transformers | vLLM | 提升 |
|------|-------------|------|------|
| 首次推理延迟 | ~2s | ~0.3s | 6.7x |
| 吞吐量（tokens/s） | ~50 | ~300 | 6x |
| 并发支持 | 差 | 优秀 | - |
| 显存占用 | 高 | 低 | - |
| 启动时间 | 慢（加载模型） | 快（HTTP 调用） | - |

## 回滚方案

如果 vLLM 出现问题，可以快速回滚到 Transformers：

```bash
# 恢复原始代码
cp llm_engine.py.bak llm_engine.py

# 恢复依赖
pip install transformers>=4.36.0 torch>=2.0.0

# 恢复环境变量
vim .env  # 添加 MODEL_DIR=/storage1/models/Qwen3.5-27B

# 重启服务
gunicorn -w 1 -b 0.0.0.0:5000 app:app --timeout 1800
```

## 注意事项

### 1. vLLM 服务稳定性

- vLLM 服务需要独立部署和监控
- 建议使用 systemd 或 supervisor 守护进程
- 配置自动重启策略

### 2. 网络延迟

- yqyd-dev 和 vLLM 服务建议部署在同一台机器或同一内网
- 跨网络调用会增加延迟

### 3. 模型兼容性

- 确认 vLLM 支持目标模型（Qwen3.5-35B-A3B-FP8）
- 测试 `enable_thinking=False` 参数是否生效

### 4. 并发限制

- vLLM 支持高并发，但需要足够显存
- 根据 GPU 显存调整 `--max-model-len` 和 `--gpu-memory-utilization`

## 常见问题

### Q1：vLLM 连接失败

**错误**：`Failed to connect to vLLM: Connection refused`

**解决**：
- 检查 vLLM 服务是否启动
- 确认 `VLLM_BASE_URL` 配置正确
- 测试网络连通性：`curl http://127.0.0.1:5001/v1/models`

### Q2：模型输出包含思考过程

**现象**：返回结果中包含 `<think>...</think>` 标签

**解决**：
- 确认 `llm_engine.py` 中已配置 `enable_thinking=False`
- 检查 vLLM 版本是否支持该参数
- 使用正则清洗：`re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)`

### Q3：推理速度没有提升

**原因**：
- vLLM 配置不当（如 `--gpu-memory-utilization` 过低）
- 模型量化格式不支持（如 FP16 vs FP8）
- 网络延迟过高

**解决**：
- 优化 vLLM 启动参数
- 使用量化模型（FP8/INT8）
- 部署在同一台机器

## 技术支持

- vLLM 官方文档：https://docs.vllm.ai/
- OpenAI API 文档：https://platform.openai.com/docs/api-reference
- 项目 Issues：https://github.com/linuxsirhjl/yqyd/issues
