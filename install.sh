#!/bin/bash
# Claude Code 新闻状态栏插件 - 简化安装脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 项目信息
REPO_URL="https://github.com/Hillyess/cc-news"
INSTALL_DIR="$HOME/.claude-news-statusline"

echo "=== Claude Code 新闻状态栏插件安装 ==="

# 检查系统要求
echo "检查系统要求..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 需要 Python 3，请先安装 Python 3${NC}"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}错误: 需要 pip3，请先安装 pip3${NC}"
    exit 1
fi

# 检测本地安装还是远程安装
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/news_service.py" ] && [ -f "$SCRIPT_DIR/status_line.sh" ]; then
    echo -e "${GREEN}检测到本地项目文件，使用本地安装模式...${NC}"
    SOURCE_DIR="$SCRIPT_DIR"
else
    echo "下载项目文件..."
    SOURCE_DIR="/tmp/claude-news-statusline"
    rm -rf "$SOURCE_DIR"
    
    if command -v git &> /dev/null; then
        git clone "$REPO_URL.git" "$SOURCE_DIR" || {
            echo -e "${YELLOW}Git 克隆失败，请手动下载项目${NC}"
            exit 1
        }
    else
        echo -e "${RED}需要 git 或手动下载项目${NC}"
        exit 1
    fi
fi

# 安装依赖
echo "安装 Python 依赖..."
pip3 install -r "$SOURCE_DIR/requirements.txt"

# 创建安装目录并复制文件
echo "安装插件文件..."
mkdir -p "$INSTALL_DIR"
cp "$SOURCE_DIR/news_service.py" "$INSTALL_DIR/"
cp "$SOURCE_DIR/status_line.sh" "$INSTALL_DIR/"
cp "$SOURCE_DIR/news_sources_config.json" "$INSTALL_DIR/"

# 设置权限
chmod +x "$INSTALL_DIR/news_service.py"
chmod +x "$INSTALL_DIR/status_line.sh"

# 配置 Claude Code
echo "配置 Claude Code..."
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

mkdir -p "$CLAUDE_DIR"

# 备份现有配置
if [ -f "$SETTINGS_FILE" ]; then
    cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 复制配置文件
cp "$INSTALL_DIR/news_sources_config.json" "$CLAUDE_DIR/"

# 生成 Claude Code 配置（安全模式，仅状态栏）
cat > "$SETTINGS_FILE" << EOF
{
  "statusLine": {
    "type": "command",
    "command": "$INSTALL_DIR/status_line.sh"
  }
}
EOF

# 简单测试
echo "测试安装..."
if python3 -c "import requests, bs4" 2>/dev/null; then
    echo -e "${GREEN}✅ Python 依赖测试成功${NC}"
else
    echo -e "${RED}❌ Python 依赖测试失败${NC}"
fi

# 清理临时文件
if [ "$SOURCE_DIR" != "$SCRIPT_DIR" ]; then
    rm -rf "$SOURCE_DIR"
fi

echo ""
echo -e "${GREEN}🎉 安装完成！${NC}"
echo ""
echo "下一步："
echo "1. 启动新闻服务："
echo "   python3 $INSTALL_DIR/news_service.py &"
echo "2. 重启 Claude Code"
echo "3. 新闻将在状态栏显示"
echo ""
echo "重要说明："
echo "- 每次重启系统后需要手动启动新闻服务"
echo "- 可以将启动命令添加到 ~/.bashrc 实现自动启动"
echo ""
echo "配置文件: ~/.claude/news_sources_config.json"
echo "安装目录: $INSTALL_DIR"