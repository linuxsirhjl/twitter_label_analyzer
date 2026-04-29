# 安全提示

## 敏感信息管理

### 环境变量配置

所有敏感信息应存储在 `.env` 文件中，不要提交到版本控制：

```bash
# 数据库密码
DB_PASSWORD=your_password

# OpenAI API Key
OPENAI_API_KEY=your_key

# 钉钉 Webhook
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### .gitignore 检查

确保以下文件已添加到 `.gitignore`：
- `.env`
- `*.log`
- `logs/`
- `__pycache__/`

## 生产环境建议

1. **修改默认密码**：更改数据库密码，不要使用示例密码
2. **限制网络访问**：配置防火墙规则，仅允许必要的 IP 访问
3. **启用 HTTPS**：生产环境使用 SSL/TLS 加密通信
4. **定期更新依赖**：运行 `pip list --outdated` 检查过期包
5. **监控日志**：定期检查 `logs/app.log` 中的异常和错误
6. **备份数据**：定期备份 MySQL 数据库

## 代理配置

如果代理服务不可用，系统会自动降级为直连。确保：
- 代理服务稳定可用
- 代理认证信息正确
- 网络策略允许直连作为备选方案

## 钉钉 Webhook 保护

- 不要在公开代码中暴露 webhook URL
- 使用钉钉的签名验证功能（可选）
- 定期轮换 access_token
- 监控异常推送行为
