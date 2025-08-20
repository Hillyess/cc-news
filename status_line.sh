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
    local clean_text=$(echo "$text" | sed -E 's/\033\[[0-9;]*m//g' | sed -E 's/\033\]8;;[^\033]*\033\\//g')
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
    
    # 对于包含OSC 8序列的文本，需要特殊处理
    if [[ "$text" =~ \\e\]8\;\; ]]; then
        # 简单处理：如果包含hyperlink，优先保持完整性，只做最小截断
        local plain_text=$(echo "$text" | sed -E 's/\\e\]8;;[^\\]*\\e\\([^\\]*)\\e\]8;;\\e\\/\1/')
        if [ ${#plain_text} -gt $((max_len-3)) ]; then
            # 如果超长，暂时返回无链接版本
            printf "%s" "${plain_text:0:$((max_len-3))}..."
            return
        fi
    fi
    
    # 普通文本的简单截断
    local truncated="${text:0:$((max_len-3))}..."
    printf "%s" "$truncated"
}

# 格式化新闻项
format_news_item() {
    local title="$1"
    local url="$2"
    local source="$3"
    
    # 清理标题中的换行符和多余空格
    title=$(echo "$title" | tr -d '\n\r' | sed 's/[[:space:]]\+/ /g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    # 对于财联社新闻，只提取中括号内的标题部分
    if [[ "$source" =~ 财联社 ]] && [[ "$title" =~ 【([^】]+)】 ]]; then
        title="${BASH_REMATCH[1]}"
    fi
    
    # 获取源图标
    local icon=$(get_source_icon "$source")
    
    # 构建显示文本
    local display_text="$icon $title"
    
    # 创建带链接的文本（如果启用）
    if [ "$ENABLE_LINKS" = "true" ] && [ -n "$url" ]; then
        # OSC 8 hyperlink format for Claude Code  
        linked_text="$(echo -e "\033]8;;${url}\033\\${display_text}\033]8;;\033\\")"
        display_text="$linked_text"
    fi
    
    # 截断过长的文本
    display_text=$(truncate_with_escapes "$display_text" "$MAX_LENGTH")
    
    printf "%s" "$display_text"
}

# 增强版新闻格式化（支持时间和股票信息）
format_news_item_enhanced() {
    local title="$1"
    local url="$2"
    local source="$3"
    local news_time="$4"
    local stock_info="$5"
    
    # 清理标题中的换行符和多余空格
    title=$(echo "$title" | tr -d '\n\r' | sed 's/[[:space:]]\+/ /g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    # 对于财联社新闻，只提取中括号内的标题部分
    if [[ "$source" =~ 财联社 ]] && [[ "$title" =~ 【([^】]+)】 ]]; then
        title="${BASH_REMATCH[1]}"
    fi
    
    # 获取源图标
    local icon=$(get_source_icon "$source")
    
    # 格式化新闻时间显示
    local time_display=""
    if [ -n "$news_time" ] && [ "$news_time" != "null" ] && [ "$news_time" != "empty" ]; then
        # 提取时间部分，简化显示 
        local simplified_time
        if [[ "$news_time" =~ [0-9]{4}年[0-9]{2}月[0-9]{2}日[[:space:]]+([0-9]{1,2}:[0-9]{2}) ]]; then
            # 匹配 "2025年08月20日 14:16:58" 格式，提取时分
            simplified_time="${BASH_REMATCH[1]}"
        elif [[ "$news_time" =~ ([0-9]{1,2}:[0-9]{2}:[0-9]{2}) ]]; then
            # 匹配 "HH:MM:SS" 格式，取前5位
            simplified_time="${BASH_REMATCH[1]:0:5}"
        elif [[ "$news_time" =~ ([0-9]{1,2}:[0-9]{2}) ]]; then
            # 匹配 "HH:MM" 格式
            simplified_time="${BASH_REMATCH[1]}"
        fi
        
        if [ -n "$simplified_time" ]; then
            printf -v time_display "\e[2m%s\e[0m " "$simplified_time"
        fi
    fi
    
    # 构建第一行显示文本
    local display_text="$icon $title"
    
    # 创建带链接的文本（如果启用）
    if [ "$ENABLE_LINKS" = "true" ] && [ -n "$url" ]; then
        # OSC 8 hyperlink format for Claude Code - 使用printf避免echo -e产生的换行问题
        printf -v linked_text "\033]8;;%s\033\\%s\033]8;;\033\\" "$url" "$display_text"
        display_text="$linked_text"
    fi
    
    # 截断过长的文本
    display_text=$(truncate_with_escapes "$display_text" "$MAX_LENGTH")
    
    # 如果有股票信息，添加到主行中
    if [ -n "$stock_info" ] && [ "$stock_info" != "null" ] && [ "$stock_info" != "empty" ]; then
        # 为股票信息添加颜色编码
        local colored_stock_info=$(add_stock_colors "$stock_info")
        # 合并到单行：时间 + 新闻内容 + 股票信息
        printf "%s%s | 📈 %s" "$time_display" "$display_text" "$colored_stock_info"
    else
        # 只有新闻内容，无股票信息
        printf "%s%s" "$time_display" "$display_text"
    fi
}

# 为股票信息添加红绿颜色编码
add_stock_colors() {
    local stock_info="$1"
    local colored_info=""
    
    # 按空格分割股票信息，处理每个股票和其涨跌幅
    local current_stock=""
    local current_change=""
    
    for word in $stock_info; do
        if [[ "$word" =~ ^[+-][0-9]+\.[0-9]+%$ ]]; then
            # 这是涨跌幅数据
            current_change="$word"
            
            # 根据正负号添加颜色
            if [[ "$current_change" =~ ^\+ ]]; then
                # 正数用红色（涨）
                colored_info="$colored_info$current_stock $(printf '\033[31m%s\033[0m' "$current_change") "
            elif [[ "$current_change" =~ ^\- ]]; then
                # 负数用绿色（跌）
                colored_info="$colored_info$current_stock $(printf '\033[32m%s\033[0m' "$current_change") "
            else
                # 无符号默认不着色
                colored_info="$colored_info$current_stock $current_change "
            fi
            
            # 重置
            current_stock=""
            current_change=""
        else
            # 这是股票名称
            if [ -n "$current_stock" ]; then
                current_stock="$current_stock $word"
            else
                current_stock="$word"
            fi
        fi
    done
    
    # 如果还有未处理的股票名称（没有涨跌幅）
    if [ -n "$current_stock" ]; then
        colored_info="$colored_info$current_stock"
    fi
    
    # 去除末尾多余的空格
    echo "${colored_info% }"
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
        local news_time=$(echo "$response" | jq -r '.news_time // empty' 2>/dev/null)
        local stock_info=$(echo "$response" | jq -r '.stock_info // empty' 2>/dev/null)
        
        if [ -n "$title" ] && [ "$title" != "null" ]; then
            format_news_item_enhanced "$title" "$url" "$source" "$news_time" "$stock_info"
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
    
    # 获取新闻内容（已包含时间和股票信息）
    get_news_data
}

# 执行主函数
main