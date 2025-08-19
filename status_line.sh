#!/bin/bash
# 简化版 Claude Code Status Line 脚本
# 支持OSC 8超链接的新闻显示，移除翻译功能

# 读取输入的JSON数据
input=$(cat)

# 解析基本信息
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
current_time=$(date '+%H:%M')

# 配置文件路径
CONFIG_FILE="$HOME/.claude/news_statusline_config.json"

# 默认配置
DEFAULT_ENABLE_LINKS="true"
DEFAULT_MAX_LENGTH="120"

# 读取配置
read_config() {
    if [ -f "$CONFIG_FILE" ]; then
        # 读取链接设置
        ENABLE_LINKS=$(jq -r '.enable_links // true' "$CONFIG_FILE" 2>/dev/null)
        # 读取最大长度设置
        MAX_LENGTH=$(jq -r '.max_length // 120' "$CONFIG_FILE" 2>/dev/null)
    else
        ENABLE_LINKS="$DEFAULT_ENABLE_LINKS"
        MAX_LENGTH="$DEFAULT_MAX_LENGTH"
    fi
    
    # 确保数值有效
    if ! [[ "$MAX_LENGTH" =~ ^[0-9]+$ ]] || [ "$MAX_LENGTH" -lt 20 ]; then
        MAX_LENGTH="$DEFAULT_MAX_LENGTH"
    fi
}

# 获取源图标
get_source_icon() {
    local source="$1"
    case "$source" in
        "36kr") echo "💼" ;;
        "TechCrunch") echo "🚀" ;;
        "虎嗅") echo "🦆" ;;
        "钛媒体") echo "🔧" ;;
        "雷锋网") echo "⚡" ;;
        "财联社电报") echo "📈" ;;
        "财联社盘面") echo "💹" ;;
        "财联社深度") echo "📊" ;;
        *) echo "📰" ;;
    esac
}

# 计算字符串显示长度（排除转义序列）
calculate_display_length() {
    local text="$1"
    # 移除ANSI转义序列和OSC 8序列
    local clean_text=$(echo "$text" | sed -E 's/\x1b\[[0-9;]*m//g' | sed -E 's/\x1b\]8;;[^\\]*\\//g' | sed -E 's/\x1b\]8;;\\//g')
    echo ${#clean_text}
}

# 截断文本但保留转义序列
truncate_with_escapes() {
    local text="$1"
    local max_len="$2"
    
    # 如果实际显示长度已经够短，直接返回
    local display_len=$(calculate_display_length "$text")
    if [ "$display_len" -le "$max_len" ]; then
        echo "$text"
        return
    fi
    
    # 简单截断（可能需要更复杂的逻辑来保持转义序列完整）
    local truncated="${text:0:$((max_len-3))}..."
    echo "$truncated"
}

# 格式化新闻项
format_news_item() {
    local title="$1"
    local url="$2"
    local source="$3"
    
    # 获取源图标
    local icon=$(get_source_icon "$source")
    
    # 构建显示文本
    local display_text="$icon $title"
    
    # 创建带链接的文本（如果启用）
    if [ "$ENABLE_LINKS" = "true" ] && [ -n "$url" ]; then
        # OSC 8 hyperlink format: \e]8;;URL\e\\TEXT\e]8;;\e\\
        local linked_text
        printf -v linked_text "\e]8;;%s\e\\%s\e]8;;\e\\" "$url" "$display_text"
        display_text="$linked_text"
    fi
    
    # 截断过长的文本
    display_text=$(truncate_with_escapes "$display_text" "$MAX_LENGTH")
    
    echo "$display_text"
}

# 获取新闻数据
get_news_data() {
    local port="${NEWS_SERVICE_PORT:-8765}"
    local api_url="http://localhost:${port}/next"
    local timeout=3
    
    # 尝试从API获取新闻
    local response=$(curl -s --max-time "$timeout" "$api_url" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        # 解析JSON响应
        local title=$(echo "$response" | jq -r '.title // empty' 2>/dev/null)
        local url=$(echo "$response" | jq -r '.url // empty' 2>/dev/null)
        local source=$(echo "$response" | jq -r '.source // empty' 2>/dev/null)
        
        if [ -n "$title" ] && [ "$title" != "null" ]; then
            format_news_item "$title" "$url" "$source"
            return 0
        fi
    fi
    
    # 如果API失败，返回备用消息
    echo "📰 News service connecting..."
    return 1
}

# 主函数
main() {
    # 读取配置
    read_config
    
    # 格式化时间（灰色显示）
    local time_display
    printf -v time_display "\e[2m%s\e[0m" "$current_time"
    
    # 获取新闻内容
    local news_content=$(get_news_data)
    
    # 输出最终结果
    echo "$time_display $news_content"
}

# 执行主函数
main