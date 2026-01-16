# 贡献指南

感谢你对本项目的关注！欢迎提交 Issue 和 Pull Request。

## 如何贡献

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: 添加新功能'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `style:` 代码格式（不影响功能）
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具相关

## 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/

# 启动开发服务器
streamlit run app.py
```

## 代码规范

- 遵循 PEP 8 规范
- 使用中文注释
- 保持代码简洁清晰
