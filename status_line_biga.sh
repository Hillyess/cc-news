#!/bin/bash
# BigA 模式状态栏脚本 - 实时股市数据与财联社电报轮播显示
# 10秒循环：0-5秒电报，5-10秒股指+板块数据

# 读取输入的JSON数据
input=$(cat)

# 解析基本信息
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')

# 配置文件路径
CONFIG_FILE="$HOME/.claude/news_statusline_config.json"

# 默认配置
DEFAULT_ENABLE_LINKS="true"
DEFAULT_MAX_LENGTH="150"  # BigA模式显示更多内容

# 读取配置
read_config() {
    if [ -f "$CONFIG_FILE" ]; then
        # 读取链接设置
        ENABLE_LINKS=$(jq -r '.enable_links // true' "$CONFIG_FILE" 2>/dev/null)
        # 读取最大长度设置
        MAX_LENGTH=$(jq -r '.max_length // 150' "$CONFIG_FILE" 2>/dev/null)
    else
        ENABLE_LINKS="$DEFAULT_ENABLE_LINKS"
        MAX_LENGTH="$DEFAULT_MAX_LENGTH"
    fi
    
    # 确保数值有效
    if ! [[ "$MAX_LENGTH" =~ ^[0-9]+$ ]] || [ "$MAX_LENGTH" -lt 50 ]; then
        MAX_LENGTH="$DEFAULT_MAX_LENGTH"
    fi
}

# 获取源图标
get_source_icon() {
    local source="$1"
    case "$source" in
        "财联社电报") echo "📈" ;;
        *) echo "📰" ;;
    esac
}

# 为股票涨跌幅添加红绿颜色编码
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

# 格式化电报内容
format_telegraph_content() {
    local title="$1"
    local url="$2"
    local source="$3"
    local news_time="$4"
    local stock_info="$5"
    
    # 安全清理标题中的换行符和控制字符，保护数字内容
    # 先用tr删除普通换行符，再用sed处理特殊空白字符
    title=$(echo "$title" | tr -d '\n\r' | sed 's/[\x09\x0B\x0C]/ /g' | sed 's/[[:space:]]\+/ /g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    # 数字保护验证 - 检查关键数字是否被误删
    original_digits=$(echo "$1" | grep -o '[0-9]' | wc -l)
    processed_digits=$(echo "$title" | grep -o '[0-9]' | wc -l)
    
    # 记录文本处理过程和数字保留情况
    echo "[$(date '+%H:%M:%S')] 文本处理前: ${1:0:50}... (数字数量: $original_digits)" >> "/tmp/biga_status_debug.log" 2>/dev/null || true
    echo "[$(date '+%H:%M:%S')] 文本处理后: ${title:0:50}... (数字数量: $processed_digits)" >> "/tmp/biga_status_debug.log" 2>/dev/null || true
    
    # 如果数字明显减少，记录警告
    if [ "$processed_digits" -lt "$((original_digits - 1))" ]; then
        echo "[$(date '+%H:%M:%S')] ⚠️ 警告: 数字可能被误删！原始: $original_digits, 处理后: $processed_digits" >> "/tmp/biga_status_debug.log" 2>/dev/null || true
    fi
    
    # 对于财联社新闻，只提取中括号内的标题部分
    if [[ "$source" =~ 财联社 ]] && [[ "$title" =~ 【([^】]+)】 ]]; then
        title="${BASH_REMATCH[1]}"
    fi
    
    # 获取源图标
    local icon=$(get_source_icon "$source")
    
    # 格式化新闻时间显示 - 保留完整时间信息
    local time_display=""
    if [ -n "$news_time" ] && [ "$news_time" != "null" ] && [ "$news_time" != "empty" ]; then
        # 记录原始时间信息到调试日志
        echo "[$(date '+%H:%M:%S')] 处理时间: $news_time" >> "/tmp/biga_status_debug.log" 2>/dev/null || true
        
        if [[ "$news_time" =~ [0-9]{4}年[0-9]{2}月[0-9]{2}日[[:space:]]+([0-9]{1,2}:[0-9]{2}:[0-9]{2}) ]]; then
            # 完整日期时间格式，保留秒数
            time_display="${BASH_REMATCH[1]:0:5} "
        elif [[ "$news_time" =~ ([0-9]{1,2}:[0-9]{2}:[0-9]{2}) ]]; then
            # HH:MM:SS格式，保留到分钟（避免状态行过长）
            time_display="${BASH_REMATCH[1]:0:5} "
        elif [[ "$news_time" =~ ([0-9]{1,2}:[0-9]{2}) ]]; then
            # HH:MM格式
            time_display="${BASH_REMATCH[1]} "
        else
            # 如果格式不匹配，尝试直接使用前5个字符
            time_display="${news_time:0:5} "
        fi
        
        echo "[$(date '+%H:%M:%S')] 时间显示: $time_display" >> "/tmp/biga_status_debug.log" 2>/dev/null || true
    fi
    
    # 构建显示文本
    local display_text="$icon $title"
    
    # 创建带链接的文本（如果启用）
    if [ "$ENABLE_LINKS" = "true" ] && [ -n "$url" ]; then
        printf -v linked_text "\033]8;;%s\033\\%s\033]8;;\033\\" "$url" "$display_text"
        display_text="$linked_text"
    fi
    
    # 如果有股票信息，添加到内容中
    if [ -n "$stock_info" ] && [ "$stock_info" != "null" ] && [ "$stock_info" != "empty" ]; then
        local colored_stock_info=$(add_stock_colors "$stock_info")
        printf "%s%s | 💹 %s" "$time_display" "$display_text" "$colored_stock_info"
    else
        printf "%s%s" "$time_display" "$display_text"
    fi
}

# 格式化股指数据显示
format_indices_display() {
    local indices="$1"
    local display_parts=()
    
    # 解析JSON数组中的每个股指
    local count=$(echo "$indices" | jq '. | length')
    
    for ((i=0; i<count; i++)); do
        local index=$(echo "$indices" | jq -r ".[$i]")
        local name=$(echo "$index" | jq -r '.name // "未知"')
        local change_percent=$(echo "$index" | jq -r '.change_percent // 0')
        local current_price=$(echo "$index" | jq -r '.current_price // 0')
        
        # 简化指数名称
        case "$name" in
            "上证指数") name="沪指" ;;
            "深证成指") name="深指" ;;
            "创业板指") name="创业" ;;
            "科创50") name="科创" ;;
            "北证50") name="北证" ;;
        esac
        
        # 格式化价格和涨跌幅
        local formatted_price=$(printf "%.0f" "$current_price")
        local formatted_change=$(printf "%+.2f%%" "$change_percent")
        
        # 根据涨跌添加颜色
        if (( $(echo "$change_percent > 0" | bc -l) )); then
            # 上涨用红色
            display_parts+=("$(printf '%s\033[31m%s\033[0m' "$name$formatted_price" "$formatted_change")")
        elif (( $(echo "$change_percent < 0" | bc -l) )); then
            # 下跌用绿色
            display_parts+=("$(printf '%s\033[32m%s\033[0m' "$name$formatted_price" "$formatted_change")")
        else
            # 平盘
            display_parts+=("${name}${formatted_price}${formatted_change}")
        fi
    done
    
    # 用空格连接所有股指
    local IFS=" "
    echo "${display_parts[*]}"
}

# 格式化板块数据显示
format_sectors_display() {
    local sectors="$1"
    local gainers=()
    local losers=()
    
    # 解析JSON数组中的每个板块
    local count=$(echo "$sectors" | jq '. | length')
    
    for ((i=0; i<count; i++)); do
        local sector=$(echo "$sectors" | jq -r ".[$i]")
        local name=$(echo "$sector" | jq -r '.name // "未知板块"')
        local change_percent=$(echo "$sector" | jq -r '.change_percent // 0')
        local sector_type=$(echo "$sector" | jq -r '.sector_type // "gainer"')
        
        # 格式化涨跌幅
        local formatted_change=$(printf "%+.1f%%" "$change_percent")
        
        if [ "$sector_type" = "gainer" ]; then
            gainers+=("$(printf '\033[31m%s%s\033[0m' "$name" "$formatted_change")")
        else
            losers+=("$(printf '\033[32m%s%s\033[0m' "$name" "$formatted_change")")
        fi
    done
    
    local result=""
    if [ ${#gainers[@]} -gt 0 ]; then
        local IFS=" "
        result="🔥${gainers[*]}"
    fi
    
    if [ ${#losers[@]} -gt 0 ]; then
        local IFS=" "
        if [ -n "$result" ]; then
            result="$result | ❄️${losers[*]}"
        else
            result="❄️${losers[*]}"
        fi
    fi
    
    echo "$result"
}

# 获取BigA模式数据并显示
get_biga_data() {
    local port="${NEWS_SERVICE_PORT:-8765}"
    local api_url="http://localhost:${port}/biga/next"
    local timeout=5
    local max_retries=2
    local response=""
    
    # 记录调试信息到临时文件
    local debug_file="/tmp/biga_status_debug.log"
    echo "[$(date '+%H:%M:%S')] 开始获取BigA数据" >> "$debug_file" 2>/dev/null || true
    
    # 重试机制获取API数据
    for retry in $(seq 1 $max_retries); do
        echo "[$(date '+%H:%M:%S')] 尝试第$retry次API调用: $api_url" >> "$debug_file" 2>/dev/null || true
        
        # 添加微小延迟确保获取最新数据，避免过长等待
        sleep 0.1
        
        response=$(curl -s --max-time "$timeout" "$api_url" 2>/dev/null)
        
        if [ $? -eq 0 ] && [ -n "$response" ]; then
            echo "[$(date '+%H:%M:%S')] API调用成功，获得响应数据" >> "$debug_file" 2>/dev/null || true
            break
        else
            echo "[$(date '+%H:%M:%S')] API调用失败，重试..." >> "$debug_file" 2>/dev/null || true
            response=""
            sleep 1
        fi
    done
    
    if [ -n "$response" ]; then
        local content_type=$(echo "$response" | jq -r '.type // empty' 2>/dev/null)
        echo "[$(date '+%H:%M:%S')] 内容类型: $content_type" >> "$debug_file" 2>/dev/null || true
        
        if [ "$content_type" = "telegraph" ]; then
            # 显示电报内容
            local content=$(echo "$response" | jq -r '.content')
            local title=$(echo "$content" | jq -r '.title // empty')
            local url=$(echo "$content" | jq -r '.url // empty')
            local source=$(echo "$content" | jq -r '.source // empty')
            local news_time=$(echo "$content" | jq -r '.news_time // empty')
            local stock_info=$(echo "$content" | jq -r '.stock_info // empty')
            
            # 记录获取到的电报数据
            echo "[$(date '+%H:%M:%S')] 获取电报: 时间=$news_time, 标题=${title:0:30}..." >> "$debug_file" 2>/dev/null || true
            
            if [ -n "$title" ] && [ "$title" != "null" ] && [ "$title" != "empty" ]; then
                local result=$(format_telegraph_content "$title" "$url" "$source" "$news_time" "$stock_info")
                echo "[$(date '+%H:%M:%S')] 最终输出: $result" >> "$debug_file" 2>/dev/null || true
                echo "$result"
                return 0
            fi
            
        elif [ "$content_type" = "market" ]; then
            # 显示股指和板块数据
            local indices=$(echo "$response" | jq -r '.indices')
            local sectors=$(echo "$response" | jq -r '.sectors')
            
            local indices_display=$(format_indices_display "$indices")
            local sectors_display=$(format_sectors_display "$sectors")
            
            if [ -n "$indices_display" ] || [ -n "$sectors_display" ]; then
                if [ -n "$indices_display" ] && [ -n "$sectors_display" ]; then
                    printf "%s | %s" "$indices_display" "$sectors_display"
                elif [ -n "$indices_display" ]; then
                    printf "%s" "$indices_display"
                else
                    printf "%s" "$sectors_display"
                fi
                return 0
            fi
        fi
    fi
    
    # 如果API失败，返回备用消息
    echo "📊 BigA模式连接中..."
    return 1
}

# 主函数
main() {
    # 读取配置
    read_config
    
    # 获取BigA模式内容并显示
    get_biga_data
}

# 执行主函数
main