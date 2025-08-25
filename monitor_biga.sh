#!/bin/bash
# BigA模式监控脚本 - 实时显示系统状态

echo "=== BigA模式监控 ==="
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# 检查新闻服务状态
echo "1. 新闻服务状态:"
if pgrep -f "news_service.py" > /dev/null; then
    echo "  ✅ 新闻服务运行中 (PID: $(pgrep -f news_service.py))"
else
    echo "  ❌ 新闻服务未运行"
fi

# 检查API响应
echo
echo "2. API响应测试:"
response=$(curl -s --max-time 3 "http://localhost:8765/biga/next" 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$response" ]; then
    content_type=$(echo "$response" | jq -r '.type // "unknown"' 2>/dev/null)
    echo "  ✅ API响应正常，内容类型: $content_type"
    
    if [ "$content_type" = "telegraph" ]; then
        news_time=$(echo "$response" | jq -r '.content.news_time // "未知"' 2>/dev/null)
        title=$(echo "$response" | jq -r '.content.title // "未知"' 2>/dev/null)
        echo "  📰 电报时间: $news_time"
        echo "  📄 标题预览: ${title:0:50}..."
    fi
else
    echo "  ❌ API响应失败"
fi

# 显示最近的调试日志
echo
echo "3. 最近的调试日志 (最后5行):"
if [ -f "/tmp/biga_status_debug.log" ]; then
    tail -5 /tmp/biga_status_debug.log | sed 's/^/  /'
else
    echo "  📝 调试日志文件不存在"
fi

# 测试状态行输出
echo
echo "4. 状态行输出测试:"
output=$(echo '{"workspace":{"current_dir":"/home/ubuntu/cc-line"}}' | ./status_line_biga.sh 2>/dev/null)
if [ -n "$output" ]; then
    echo "  ✅ 状态行输出: $output"
else
    echo "  ❌ 状态行输出为空"
fi

echo
echo "=== 监控完成 ==="