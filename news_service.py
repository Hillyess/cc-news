#!/usr/bin/env python3
"""
简化版新闻状态栏服务 - 集成新闻抓取、HTTP API和状态栏显示
移除未使用的翻译功能，保持核心新闻聚合和显示功能
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import json
import threading
import logging
import signal
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/news_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NewsItem:
    """新闻项数据结构"""
    def __init__(self, title: str, url: str, source: str = "", news_time: Optional[str] = None, stock_info: Optional[str] = None):
        self.title = title
        self.url = url
        self.source = source
        self.news_time = news_time  # 新闻实际发布时间
        self.stock_info = stock_info  # 相关股票信息
        self.timestamp = datetime.now()  # 抓取时间
        self.id = f"{source}_{hash(title)}_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict:
        result = {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'timestamp': self.timestamp.isoformat()
        }
        
        # 添加可选字段
        if self.news_time:
            result['news_time'] = self.news_time
        if self.stock_info:
            result['stock_info'] = self.stock_info
            
        return result

class NewsPool:
    """新闻池管理器"""
    def __init__(self, max_size: int = 100, refresh_interval: int = 60):
        self.news_items: List[NewsItem] = []
        self.max_size = max_size
        self.refresh_interval = refresh_interval
        self.lock = threading.Lock()
        self.last_refresh = None
        self.refresh_thread = None
        self.running = True
        
        # 加载新闻源配置
        self.load_news_sources_config()
        
        # 启动自动刷新
        self.start_auto_refresh()
        
        # 立即获取一次新闻
        self.refresh_news()
    
    def load_news_sources_config(self):
        """加载新闻源配置，支持可开关配置"""
        # 默认配置文件路径
        config_file = os.path.expanduser('~/.claude/news_sources_config.json')
        
        # 默认新闻源配置（所有源默认启用）
        default_config = {
            'sources': {
                '36kr': {
                    'enabled': True,
                    'name': '36kr',
                    'url': 'https://36kr.com',
                    'selectors': [
                        'a[href*="/p/"]',
                        'a.item-title',
                        '.article-title',
                        'h3.title a'
                    ],
                    'icon': '💼'
                },
                'techcrunch': {
                    'enabled': True,
                    'name': 'TechCrunch',
                    'url': 'https://techcrunch.com',
                    'selectors': [
                        'h2.post-block__title a',
                        '.post-title a',
                        'h3 a',
                        '.article-title'
                    ],
                    'icon': '🚀'
                },
                'huxiu': {
                    'enabled': True,
                    'name': '虎嗅',
                    'url': 'https://www.huxiu.com',
                    'selectors': [
                        '.article-title',
                        'h3.title a',
                        '.news-title',
                        'a.item-title'
                    ],
                    'icon': '🦆'
                },
                'tmtpost': {
                    'enabled': True,
                    'name': '钛媒体',
                    'url': 'https://www.tmtpost.com',
                    'selectors': [
                        'a._tit',
                        '.item ._tit',
                        'h3 a',
                        '.article-title'
                    ],
                    'icon': '🔧'
                },
                'leiphone': {
                    'enabled': True,
                    'name': '雷锋网',
                    'url': 'https://www.leiphone.com',
                    'selectors': [
                        'h3 a',
                        'a[href*="news"]',
                        '.article-title',
                        '.news-title'
                    ],
                    'icon': '⚡'
                },
                'cls_telegraph': {
                    'enabled': True,
                    'name': '财联社电报',
                    'url': 'https://www.cls.cn/telegraph',
                    'selectors': [
                        '.telegraph-content a',
                        'a[href*="/telegraph/"]',
                        '.telegraph-item a',
                        'a'
                    ],
                    'icon': '📈'
                },
                'cls_finance': {
                    'enabled': True,
                    'name': '财联社盘面',
                    'url': 'https://www.cls.cn/subject/1103',
                    'selectors': [
                        'a[href*="/detail/"]',
                        '.article-item a',
                        '.news-item a',
                        'a'
                    ],
                    'icon': '💹'
                },
                'cls_depth': {
                    'enabled': True,
                    'name': '财联社深度',
                    'url': 'https://www.cls.cn/depth?id=1000',
                    'selectors': [
                        'a[href*="/depth/"]',
                        '.depth-item a',
                        'h3 a',
                        'a'
                    ],
                    'icon': '📊'
                }
            }
        }
        
        # 尝试加载配置文件
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 合并用户配置和默认配置
                    for source_key, source_config in default_config['sources'].items():
                        if source_key in user_config.get('sources', {}):
                            # 更新用户自定义的设置
                            source_config.update(user_config['sources'][source_key])
                    
                    logger.info(f"已加载用户配置文件: {config_file}")
            else:
                # 创建默认配置文件
                os.makedirs(os.path.dirname(config_file), exist_ok=True)
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                logger.info(f"已创建默认配置文件: {config_file}")
        except Exception as e:
            logger.warning(f"配置文件处理错误: {e}，使用默认配置")
        
        # 只启用已启用的新闻源
        self.news_sources = {
            key: config for key, config in default_config['sources'].items()
            if config.get('enabled', True)
        }
        
        enabled_sources = list(self.news_sources.keys())
        logger.info(f"已启用的新闻源: {enabled_sources}")
    
    def start_auto_refresh(self):
        """启动自动刷新线程"""
        if self.refresh_thread is None or not self.refresh_thread.is_alive():
            self.refresh_thread = threading.Thread(target=self._auto_refresh_worker, daemon=True)
            self.refresh_thread.start()
            logger.info("自动刷新线程已启动")
    
    def _auto_refresh_worker(self):
        """自动刷新工作线程"""
        while self.running:
            try:
                time.sleep(self.refresh_interval)
                if self.running:
                    self.refresh_news()
            except Exception as e:
                logger.error(f"自动刷新错误: {e}")
    
    def refresh_news(self):
        """刷新新闻池"""
        logger.info("开始刷新新闻...")
        
        new_items = []
        for source_key, source_config in self.news_sources.items():
            try:
                items = self._fetch_news_from_source(source_config)
                new_items.extend(items)
                logger.info(f"从 {source_config['name']} 获取到 {len(items)} 条新闻")
            except Exception as e:
                logger.error(f"从 {source_config['name']} 获取新闻失败: {e}")
        
        with self.lock:
            # 合并新旧新闻，去重
            all_items = new_items + self.news_items
            unique_items = []
            seen_titles = set()
            
            for item in all_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    unique_items.append(item)
            
            # 按时间排序，保留最新的
            unique_items.sort(key=lambda x: x.timestamp, reverse=True)
            
            # 清理过期内容（6小时前）
            cutoff_time = datetime.now() - timedelta(hours=6)
            fresh_items = [item for item in unique_items if item.timestamp > cutoff_time]
            
            # 限制池大小
            self.news_items = fresh_items[:self.max_size]
            self.last_refresh = datetime.now()
            
            logger.info(f"新闻池刷新完成，当前有 {len(self.news_items)} 条新闻")
    
    def _fetch_news_from_source(self, source_config: Dict) -> List[NewsItem]:
        """从单个新闻源获取新闻"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(source_config['url'], headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            news_items = []
            
            # 尝试不同的选择器
            for selector in source_config['selectors']:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                    break
            
            if not elements:
                logger.warning(f"未找到新闻元素: {source_config['name']}")
                return []
            
            for element in elements[:20]:  # 限制每个源最多20条
                try:
                    if element.name == 'a':
                        title = element.get_text(strip=True)
                        url = element.get('href', '')
                    else:
                        link = element.find('a')
                        if link:
                            title = link.get_text(strip=True)
                            url = link.get('href', '')
                        else:
                            title = element.get_text(strip=True)
                            url = ''
                    
                    if title and len(title) > 10:  # 过滤太短的标题
                        # 处理相对URL
                        if url and not url.startswith('http'):
                            if url.startswith('/'):
                                # 获取基础域名
                                from urllib.parse import urlparse
                                parsed_url = urlparse(source_config['url'])
                                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                                url = f"{base_url}{url}"
                            else:
                                url = f"{source_config['url'].rstrip('/')}/{url}"
                        
                        # 对财联社来源提取额外信息
                        news_time = None
                        stock_info = None
                        
                        if "财联社" in source_config['name'] and url:
                            extracted_data = self._extract_cls_data(url, soup, element)
                            news_time = extracted_data.get('news_time')
                            stock_info = extracted_data.get('stock_info')
                        
                        news_item = NewsItem(title, url, source_config['name'], news_time, stock_info)
                        news_items.append(news_item)
                
                except Exception as e:
                    logger.debug(f"处理新闻项错误: {e}")
                    continue
            
            return news_items[:20]  # 返回最多20条
            
        except Exception as e:
            logger.error(f"获取新闻失败 {source_config['name']}: {e}")
            return []
    
    def _extract_cls_data(self, url: str, soup: BeautifulSoup, element) -> Dict:
        """提取财联社特定数据：时间和股票信息"""
        result = {'news_time': None, 'stock_info': None}
        
        try:
            # 如果是详情页面，需要访问页面提取信息
            if '/detail/' in url:
                result = self._fetch_detail_page_data(url)
                
            elif 'telegraph' in url:
                # 如果是电报页面，直接从当前页面提取
                result = self._extract_from_telegraph_page(soup, element)
                
        except Exception as e:
            logger.debug(f"提取CLS数据错误: {e}")
        
        return result
    
    def _fetch_detail_page_data(self, url: str) -> Dict:
        """访问详情页面获取时间和股票信息"""
        result = {'news_time': None, 'stock_info': None}
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            detail_soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取时间信息 - 财联社详情页的时间格式
            # 查找可能的时间元素
            time_selectors = [
                '.time',
                '.publish-time',
                '[class*="time"]',
                '.article-time',
                'time'
            ]
            
            for selector in time_selectors:
                time_element = detail_soup.select_one(selector)
                if time_element:
                    time_text = time_element.get_text(strip=True)
                    if time_text and ('年' in time_text or '月' in time_text or ':' in time_text):
                        result['news_time'] = time_text
                        break
            
            # 提取股票信息 - 查找股票相关元素
            stock_selectors = [
                '.industry-stock a',
                '[class*="stock"] a',
                'a[href*="stock"]'
            ]
            
            for selector in stock_selectors:
                stock_elements = detail_soup.select(selector)
                if stock_elements:
                    stock_items = []
                    for elem in stock_elements[:5]:  # 最多5只股票
                        name_span = elem.find('span', class_='c-222') or elem.find('span')
                        change_span = elem.find('span', class_='c-de0422') or elem.find_all('span')[-1] if elem.find_all('span') else None
                        
                        if name_span and change_span:
                            name = name_span.get_text(strip=True)
                            change = change_span.get_text(strip=True)
                            if '+' in change or '-' in change or '%' in change:
                                stock_items.append(f"{name} {change}")
                    
                    if stock_items:
                        result['stock_info'] = ' '.join(stock_items)
                        break
                        
        except Exception as e:
            logger.debug(f"获取详情页面数据错误: {e}")
            
        return result
    
    def _extract_from_telegraph_page(self, soup: BeautifulSoup, element) -> Dict:
        """从电报页面提取数据"""
        result = {'news_time': None, 'stock_info': None}
        
        try:
            # 提取时间信息
            time_element = soup.find('span', class_='telegraph-time-box')
            if time_element:
                time_text = time_element.get_text(strip=True)
                if time_text and ':' in time_text:
                    # 格式化时间（添加今天的日期）
                    today = datetime.now().strftime('%Y-%m-%d')
                    result['news_time'] = f"{today} {time_text}"
            
            # 提取股票信息
            stock_container = soup.find('div', class_='industry-stock')
            if stock_container:
                stock_items = []
                stock_links = stock_container.find_all('a')
                for link in stock_links[:5]:  # 最多5只股票
                    name_span = link.find('span', class_='c-222')
                    change_span = link.find('span', class_='c-de0422')
                    if name_span and change_span:
                        name = name_span.get_text(strip=True)
                        change = change_span.get_text(strip=True)
                        stock_items.append(f"{name} {change}")
                
                if stock_items:
                    result['stock_info'] = ' '.join(stock_items)
                    
        except Exception as e:
            logger.debug(f"从电报页面提取数据错误: {e}")
            
        return result
    
    def get_next_news(self) -> Optional[NewsItem]:
        """获取下一条新闻（时间轮播）"""
        with self.lock:
            if not self.news_items:
                return None
            
            # 基于时间的伪随机轮播
            current_epoch = int(time.time())
            rotation_interval = 5  # 5秒轮播一次
            rotation_index = (current_epoch // rotation_interval) % len(self.news_items)
            
            return self.news_items[rotation_index]
    
    def get_random_news(self, count: int = 5) -> List[NewsItem]:
        """获取随机新闻"""
        with self.lock:
            if not self.news_items:
                return []
            return random.sample(self.news_items, min(count, len(self.news_items)))
    
    def get_status(self) -> Dict:
        """获取服务状态"""
        with self.lock:
            return {
                'total_news': len(self.news_items),
                'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
                'sources': list(self.news_sources.keys()),
                'auto_refresh_interval': self.refresh_interval
            }
    
    def stop(self):
        """停止服务"""
        self.running = False
        if self.refresh_thread:
            self.refresh_thread.join(timeout=1)

class NewsAPIHandler(BaseHTTPRequestHandler):
    """HTTP API处理器"""
    
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        try:
            if path == '/status':
                self._handle_status()
            elif path == '/next':
                self._handle_next()
            elif path == '/random':
                count = int(query_params.get('count', ['5'])[0])
                self._handle_random(count)
            elif path == '/refresh':
                self._handle_refresh()
            else:
                self._send_error(404, "Not Found")
        except Exception as e:
            logger.error(f"API错误: {e}")
            self._send_error(500, str(e))
    
    def _handle_status(self):
        status = news_pool.get_status()
        self._send_json_response(status)
    
    def _handle_next(self):
        news_item = news_pool.get_next_news()
        if news_item:
            self._send_json_response(news_item.to_dict())
        else:
            self._send_json_response({'error': 'No news available'})
    
    def _handle_random(self, count: int):
        news_items = news_pool.get_random_news(count)
        response = [item.to_dict() for item in news_items]
        self._send_json_response(response)
    
    def _handle_refresh(self):
        threading.Thread(target=news_pool.refresh_news, daemon=True).start()
        self._send_json_response({'message': 'Refresh started'})
    
    def _send_json_response(self, data):
        response = json.dumps(data, ensure_ascii=False, indent=2)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def _send_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))
    
    def log_message(self, format, *args):
        # 减少HTTP日志输出
        pass

def signal_handler(signum, frame):
    """信号处理器"""
    logger.info("收到退出信号，正在停止服务...")
    global news_pool, httpd
    if news_pool:
        news_pool.stop()
    if httpd:
        httpd.shutdown()
    sys.exit(0)

def check_existing_service():
    """检查是否已有健康的服务在运行，如果有则跳过启动"""
    import subprocess
    try:
        # 先检查端口是否被占用
        result = subprocess.run(['lsof', '-ti:8765'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            # 端口被占用，检查服务是否健康
            try:
                response = requests.get('http://localhost:8765/status', timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    if 'total_news' in data:
                        logger.info(f"检测到健康的新闻服务正在运行 (新闻数: {data.get('total_news', 0)})，跳过启动")
                        sys.exit(0)
                    else:
                        logger.warning("服务响应格式异常，需要重启")
                else:
                    logger.warning(f"服务响应异常 (状态码: {response.status_code})，需要重启")
            except Exception as e:
                logger.warning(f"服务健康检查失败: {e}，需要重启")
            
            # 服务不健康，清理进程
            pids = result.stdout.strip().split('\n')
            logger.info("检测到端口被占用但服务不健康，正在清理...")
            for pid in pids:
                if pid.strip():
                    try:
                        logger.info(f"正在停止进程 PID: {pid}")
                        subprocess.run(['kill', '-9', pid.strip()], timeout=3)
                    except Exception as e:
                        logger.warning(f"停止进程 {pid} 时出错: {e}")
            
            # 等待端口释放
            import time
            time.sleep(2)
            logger.info("进程已清理，准备启动新服务")
        else:
            logger.info("端口8765空闲，准备启动服务")
                
    except Exception as e:
        logger.warning(f"检查现有服务时出错: {e}")
        pass

def main():
    global news_pool, httpd
    
    # 检查是否已有服务运行
    check_existing_service()
    
    # 注册信号处理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # 初始化新闻池
        logger.info("初始化新闻池...")
        news_pool = NewsPool()
        
        # 启动HTTP服务器
        port = int(os.getenv('NEWS_SERVICE_PORT', '8765'))
        server_address = ('localhost', port)
        httpd = HTTPServer(server_address, NewsAPIHandler)
        
        logger.info(f"新闻服务已启动在 http://{server_address[0]}:{server_address[1]}")
        logger.info("API endpoints:")
        logger.info("  GET /status  - 服务状态")
        logger.info("  GET /next    - 下一条新闻")
        logger.info("  GET /random?count=N - 随机新闻")
        logger.info("  GET /refresh - 手动刷新")
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    news_pool = None
    httpd = None
    main()