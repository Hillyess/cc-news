# 贡献指南

感谢您对 Claude Code 新闻状态栏插件的关注！我们欢迎各种形式的贡献。

## 🤝 如何贡献

### 报告 Bug

如果发现问题，请在 [Issues](https://github.com/Hillyess/claude-code-news-statusline/issues) 页面创建新问题，包含：

- **环境信息**：操作系统、Python 版本、Claude Code 版本
- **问题描述**：清楚描述遇到的问题
- **重现步骤**：详细的重现步骤
- **预期行为**：描述您期望的正确行为
- **错误日志**：相关的错误信息或日志

### 功能建议

我们欢迎新功能建议！请在提交前：

1. 确保功能符合项目目标（轻量级、高性能）
2. 检查是否已有类似建议
3. 详细描述功能的用途和实现方式

### 代码贡献

#### 开发环境设置

1. Fork 项目到您的 GitHub 账户
2. 克隆您的 fork 到本地：
   ```bash
   git clone https://github.com/your-username/claude-code-news-statusline.git
   cd claude-code-news-statusline
   ```

3. 创建虚拟环境：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. 创建功能分支：
   ```bash
   git checkout -b feature/your-feature-name
   ```

#### 代码标准

- **Python 代码**：遵循 PEP 8 规范
- **Shell 脚本**：使用 shellcheck 检查
- **注释**：为复杂逻辑添加清晰注释
- **函数**：保持函数简洁，单一职责

#### 添加新新闻源

1. 在 `news_service.py` 中添加新闻源配置：
   ```python
   'new_source': {
       'enabled': True,
       'name': '新闻源名称',
       'url': 'https://example.com',
       'selectors': [
           'CSS选择器1',
           'CSS选择器2'  # 备用选择器
       ],
       'icon': '📰'
   }
   ```

2. 在 `status_line.sh` 中添加图标映射：
   ```bash
   "新闻源名称") echo "📰" ;;
   ```

3. 测试新闻源抓取：
   ```bash
   python3 -c "
   from news_service import NewsPool
   pool = NewsPool()
   # 检查新闻源是否正常工作
   "
   ```

#### 测试

在提交前请确保：

1. **功能测试**：
   ```bash
   # 测试新闻服务
   python3 news_service.py &
   sleep 5
   curl http://localhost:8765/status
   pkill -f news_service.py
   
   # 测试状态栏
   echo '{"workspace":{"current_dir":"/"}}' | ./status_line.sh
   ```

2. **语法检查**：
   ```bash
   python3 -m py_compile news_service.py
   shellcheck status_line.sh install.sh
   ```

3. **集成测试**：确保与 Claude Code 的集成正常

#### 提交信息

使用清晰的提交信息：

```
类型(范围): 简短描述

详细描述（如需要）

- 变更点1
- 变更点2

关闭 #issue_number
```

类型示例：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 添加测试
- `chore`: 构建过程或工具变动

### Pull Request

1. 确保您的分支是最新的：
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-feature-branch
   git rebase main
   ```

2. 推送到您的 fork：
   ```bash
   git push origin your-feature-branch
   ```

3. 创建 Pull Request，包含：
   - 清晰的标题和描述
   - 相关 Issue 的链接
   - 测试结果
   - 截图（如适用）

## 📝 文档贡献

- 改进 README.md
- 添加使用示例
- 完善 API 文档
- 修正错别字或翻译

## 🎨 设计贡献

- 优化状态栏显示格式
- 设计新的图标
- 改进用户体验

## 🌟 认可贡献者

所有贡献者都会在 README.md 中得到认可。

## 📞 联系我们

- GitHub Issues: [项目问题页面](https://github.com/Hillyess/claude-code-news-statusline/issues)
- 讨论: [GitHub Discussions](https://github.com/Hillyess/claude-code-news-statusline/discussions)

感谢您的贡献！🎉