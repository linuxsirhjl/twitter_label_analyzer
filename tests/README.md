# 测试指南

## API 测试

### 测试 Flask /extract 接口

```python
import requests

api_url = 'http://192.168.51.40:5000/extract'
test_content = "测试文本内容"
files = {'file': ('test.txt', test_content, 'text/plain')}

response = requests.post(api_url, files=files, timeout=120)
print(response.json())
```

### 诊断 LLM 服务

检查服务状态：
- Flask 服务：http://192.168.51.40:5000
- vLLM 服务：http://127.0.0.1:5001

确保 vLLM 服务已启动：
```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen3.5-35B-A3B-FP8 \
  --port 5001 \
  --host 127.0.0.1
```

## 单元测试

运行所有测试：
```bash
pytest tests/
```

## 注意事项

- API 响应时间较长（约50秒），需设置足够的超时时间
- 使用 multipart/form-data 格式上传文件
- 确保 vLLM 服务在 Flask 服务之前启动
