# Claude Code 新闻状态栏插件

[![GitHub release](https://img.shields.io/github/release/Hillyess/cc-news.svg)](https://github.com/Hillyess/cc-news/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

为 Claude Code 提供实时新闻聚合和状态栏显示的插件，支持多种新闻源、财经资讯和可点击超链接。

![Demo](docs/demo.gif)

## ✨ 特性

- 🚀 **一键安装** - 单行命令完成所有配置
- 📰 **多源聚合** - 8个优质新闻源，实时更新
- 📈 **财经资讯** - 专业财联社实时行情播报
- 🔗 **可点击链接** - OSC 8 超链接支持，点击新闻直接跳转
- ⚙️ **可配置** - 灵活的新闻源开关和个性化设置
- 🔄 **智能轮播** - 基于时间的智能新闻轮播
- 🎨 **美观显示** - 彩色图标和优雅的状态栏格式

## 📊 支持的新闻源

| 新闻源 | 图标 | 类型 | 描述 |
|--------|------|------|------|
| 36kr | 💼 | 创投科技 | 创业投资和科技资讯 |
| TechCrunch | 🚀 | 国际科技 | 全球科技新闻和创业资讯 |
| 虎嗅 | 🦆 | 商业科技 | 深度商业分析和科技报道 |
| 钛媒体 | 🔧 | TMT资讯 | 科技、媒体、通信行业资讯 |
| 雷锋网 | ⚡ | AI科技 | 人工智能和新兴科技 |
| 财联社电报 | 📈 | 财经快讯 | 实时财经资讯和市场动态 |
| 财联社盘面 | 📈 | 股市直播 | A股实时行情异动播报 |
| 财联社深度 | 📊 | 深度分析 | 财经深度分析和研究报告 |

## 🚀 安装方式

### 方式一：一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/Hillyess/cc-news/main/install.sh | bash
```

### 方式二：手动安装

```bash
# 1. 克隆项目
git clone https://github.com/Hillyess/cc-news.git
cd cc-news

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 运行安装脚本
./install.sh
```

**安装脚本会自动：**
- ✅ 检查系统依赖（Python 3 + pip3）
- ✅ 安装 Python 依赖包
- ✅ 复制插件文件到用户目录
- ✅ 配置 Claude Code 钩子和状态栏
- ✅ 测试安装完成度

## 📋 系统要求

- **Claude Code CLI** - [下载安装](https://claude.ai/code)
- **Python 3.6+** - 系统 Python（无需虚拟环境）
- **pip3** - Python 包管理器
- **git** - 用于克隆项目（一键安装需要）

## 🎯 快速开始

### 1. 安装插件

选择上面任一安装方式

### 2. 重启 Claude Code

安装完成后，重启 Claude Code 以加载新配置。

### 3. 享受实时新闻

新闻将自动在状态栏中显示，格式如下：
```
15:42 💼 ChatGPT：关于AI的一切你需要知道的...
```

点击新闻标题可以直接打开原文链接！

## ⚙️ 配置说明

### 端口配置

插件默认使用 **8765** 端口运行新闻服务。如果端口被占用或需要自定义，可以通过环境变量配置：

```bash
# 检查端口是否被占用
lsof -i :8765

# 自定义端口（例如使用 9000 端口）
export NEWS_SERVICE_PORT=9000
```

**注意：** 修改端口后需要重启 Claude Code 以生效。

### 新闻源配置

配置文件位置：`~/.claude/news_sources_config.json`

```json
{
  "sources": {
    "36kr": {
      "enabled": true,
      "name": "36kr",
      "url": "https://36kr.com",
      "icon": "💼"
    },
    "cls_telegraph": {
      "enabled": true,
      "name": "财联社电报",
      "url": "https://www.cls.cn/telegraph",
      "icon": "📈"
    }
  }
}
```

### Claude Code 配置

配置文件位置：`~/.claude/settings.json`

插件会自动配置 Claude Code 的钩子和状态栏设置。

## 故障排除

### 服务无法启动
```bash
# 检查端口占用
lsof -i :8765

# 查看日志
tail -f /tmp/news_service.log

# 检查虚拟环境
ls -la ../venv/bin/python3
```

### 状态栏不显示
```bash
# 手动测试状态栏脚本
echo '{"workspace":{"current_dir":"/test"}}' | ./status_line.sh

# 检查API连接
curl -s http://localhost:8765/status

# 检查配置
cat ~/.claude/settings.json | jq .statusLine

# 修复脚本权限（如果需要）
chmod +x ~/.claude-news-statusline/news_service.py
chmod +x ~/.claude-news-statusline/status_line.sh
```

### 状态栏显示 "News service connecting..."

如果状态栏一直显示连接中，可能是服务进程卡住：

```bash
# 1. 检查服务进程
lsof -i :8765

# 2. 强制终止卡住的进程
pkill -f news_service.py
# 或者根据PID强制终止：kill -9 <PID>

# 3. 重新启动服务
python3 ~/.claude-news-statusline/news_service.py &

# 4. 测试服务响应
curl -s http://localhost:8765/status --max-time 5

# 5. 如果服务正常，重启 Claude Code
```

### 重置配置
```bash
# 恢复备份（如果有）
cp ~/.claude/settings.json.backup.* ~/.claude/settings.json

# 重新运行安装
./install.sh

# 手动重启服务
pkill -f news_service.py
python3 ~/.claude-news-statusline/news_service.py &
```



## 功能性能
- **新闻抓取**: 支持多站点新闻，2分钟自动刷新
- **API响应**: <100ms本地响应时间
- **轮播切换**: 30秒智能时间轮播
- **错误恢复**: 自动重试和降级机制

## 兼容性

- Python 3.7+
- Claude Code v1.0.81+
