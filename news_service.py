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
from typing import List, Dict, Optional, Union
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import re

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

class StockIndex:
    """股指数据结构"""
    def __init__(self, name: str, code: str, current_price: float, change: float, change_percent: float):
        self.name = name
        self.code = code 
        self.current_price = current_price
        self.change = change
        self.change_percent = change_percent
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'code': self.code,
            'current_price': self.current_price,
            'change': self.change,
            'change_percent': self.change_percent,
            'timestamp': self.timestamp.isoformat()
        }

class SectorData:
    """板块数据结构"""
    def __init__(self, name: str, change_percent: float, sector_type: str = "gainer"):
        self.name = name
        self.change_percent = change_percent
        self.sector_type = sector_type  # "gainer" or "loser"
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'change_percent': self.change_percent,
            'sector_type': self.sector_type,
            'timestamp': self.timestamp.isoformat()
        }

class BigAPool:
    """大A模式数据管理器"""
    def __init__(self):
        self.lock = threading.Lock()
        self.indices: List[StockIndex] = []
        self.sectors: List[SectorData] = []
        self.telegraph_items: List[NewsItem] = []
        self.last_indices_update = datetime.min
        self.last_sectors_update = datetime.min
        self.last_telegraph_update = datetime.min
        
        # 更新间隔设置
        self.indices_update_interval = 60  # 股指每分钟更新
        self.sectors_update_interval = 300  # 板块每5分钟更新
        self.telegraph_update_interval = 30  # 电报每30秒更新
        
        # 启动数据更新线程
        self.running = True
        self.update_thread = threading.Thread(target=self._update_worker, daemon=True)
        self.update_thread.start()
    
    def _update_worker(self):
        """后台数据更新工作线程"""
        while self.running:
            try:
                now = datetime.now()
                
                # 更新股指数据
                if (now - self.last_indices_update).total_seconds() >= self.indices_update_interval:
                    self._update_indices()
                    self.last_indices_update = now
                
                # 更新板块数据
                if (now - self.last_sectors_update).total_seconds() >= self.sectors_update_interval:
                    self._update_sectors()
                    self.last_sectors_update = now
                
                # 更新电报数据
                if (now - self.last_telegraph_update).total_seconds() >= self.telegraph_update_interval:
                    self._update_telegraph()
                    self.last_telegraph_update = now
                
                time.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"BigA数据更新错误: {e}")
    
    def _update_indices(self):
        """更新股指数据"""
        try:
            new_indices = self._fetch_stock_indices()
            with self.lock:
                self.indices = new_indices
            logger.info(f"已更新{len(new_indices)}个股指数据")
        except Exception as e:
            logger.error(f"更新股指数据失败: {e}")
    
    def _update_sectors(self):
        """更新板块数据"""
        try:
            new_sectors = self._fetch_sector_data()
            with self.lock:
                self.sectors = new_sectors
            logger.info(f"已更新{len(new_sectors)}个板块数据")
        except Exception as e:
            logger.error(f"更新板块数据失败: {e}")
    
    def _update_telegraph(self):
        """更新电报数据 - 每30秒完全替换为最新5条"""
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.info(f"开始更新电报数据 - 当前时间: {current_time}")
            
            new_telegraph = self._fetch_recent_telegraph()
            with self.lock:
                # 完全替换池子内容为最新的5条电报
                self.telegraph_items = new_telegraph[:5]
                
            # 记录更新后的电报时间
            times = [item.news_time for item in self.telegraph_items if item.news_time]
            logger.info(f"已更新电报数据，完全替换为最新{len(self.telegraph_items)}条电报")
            logger.info(f"更新后电报时间: {times}")
        except Exception as e:
            logger.error(f"更新电报数据失败: {e}")
    
    def _fetch_stock_indices(self) -> List[StockIndex]:
        """获取股指数据 - 从新浪财经API"""
        indices = []
        
        # 定义需要获取的股指代码
        index_codes = {
            'sh000001': '上证指数',
            'sz399001': '深证成指', 
            'sz399006': '创业板指',
            'sh000688': '科创50',
            'bj899050': '北证50'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        
        try:
            # 构建API URL
            codes_param = ','.join(index_codes.keys())
            api_url = f"https://hq.sinajs.cn/list={codes_param}"
            
            response = requests.get(api_url, headers=headers, timeout=10)
            response.encoding = 'gbk'  # 新浪API返回GBK编码
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                for line in lines:
                    if '=' in line and '"' in line:
                        # 解析数据格式: var hq_str_sh000001="上证指数,3234.12,3245.67,..."
                        code = line.split('=')[0].replace('var hq_str_', '')
                        if code in index_codes:
                            data_str = line.split('"')[1]
                            if data_str:
                                fields = data_str.split(',')
                                if len(fields) >= 4:
                                    try:
                                        current_price = float(fields[3])
                                        prev_close = float(fields[2])
                                        change = current_price - prev_close
                                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                                        
                                        index = StockIndex(
                                            name=index_codes[code],
                                            code=code,
                                            current_price=current_price,
                                            change=change,
                                            change_percent=change_percent
                                        )
                                        indices.append(index)
                                    except (ValueError, IndexError):
                                        continue
        except Exception as e:
            logger.error(f"获取股指数据失败: {e}")
        
        return indices
    
    def _fetch_sector_data(self) -> List[SectorData]:
        """获取板块数据"""
        sectors = []
        
        try:
            # 从东方财富获取板块数据
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 板块排行API
            api_url = "http://push2.eastmoney.com/api/qt/clist/get"
            params = {
                'pn': '1',
                'pz': '50',
                'po': '1',
                'np': '1',
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fltt': '2',
                'invt': '2',
                'fid': 'f3',  # 按涨跌幅排序
                'fs': 'm:90+t:2',  # 板块分类
                'fields': 'f1,f2,f3,f4,f12,f14'
            }
            
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and data['data'].get('diff'):
                    items = data['data']['diff']
                    
                    # 按涨跌幅排序
                    items.sort(key=lambda x: float(x.get('f3', 0)), reverse=True)
                    
                    # 取前5涨幅
                    for item in items[:5]:
                        if float(item.get('f3', 0)) > 0:
                            sector = SectorData(
                                name=item.get('f14', '未知板块'),
                                change_percent=float(item.get('f3', 0)),
                                sector_type="gainer"
                            )
                            sectors.append(sector)
                    
                    # 取后3跌幅
                    for item in items[-3:]:
                        if float(item.get('f3', 0)) < 0:
                            sector = SectorData(
                                name=item.get('f14', '未知板块'),
                                change_percent=float(item.get('f3', 0)),
                                sector_type="loser"
                            )
                            sectors.append(sector)
                            
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
        
        return sectors
    
    def _fetch_recent_telegraph(self) -> List[NewsItem]:
        """获取最近30分钟的财联社电报"""
        telegraph_items = []
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get('https://www.cls.cn/telegraph', headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找电报内容 - 尝试多种选择器
            telegraph_blocks = soup.find_all('div', class_=lambda x: x and 'telegraph-content-box' in x)
            
            # 如果第一个选择器没找到，尝试其他选择器
            if not telegraph_blocks:
                logger.info("使用备选选择器查找电报内容")
                telegraph_blocks = soup.find_all('div', class_=lambda x: x and 'telegraph' in str(x).lower())
                
            if not telegraph_blocks:
                # 尝试查找包含时间格式的内容块
                telegraph_blocks = soup.find_all('div', string=lambda text: text and ':' in text and len(text.split(':')) >= 3)
            logger.info(f"找到 {len(telegraph_blocks)} 个电报块")
            
            fifteen_minutes_ago = datetime.now() - timedelta(minutes=15)
            
            for i, block in enumerate(telegraph_blocks[:20]):  # 限制处理数量
                try:
                    # 提取时间
                    time_element = block.find('span', class_='telegraph-time-box')
                    if time_element:
                        time_text = time_element.get_text(strip=True)
                        logger.info(f"电报块 {i}: 时间 {time_text}")
                        # 解析时间格式 HH:MM:SS
                        if re.match(r'^\d{1,2}:\d{2}:\d{2}$', time_text):
                            today = datetime.now().date()
                            time_parts = time_text.split(':')
                            news_time = datetime.combine(
                                today, 
                                datetime.min.time().replace(
                                    hour=int(time_parts[0]), 
                                    minute=int(time_parts[1]), 
                                    second=int(time_parts[2])
                                )
                            )
                            
                            logger.info(f"解析时间: {news_time}, 15分钟前: {fifteen_minutes_ago}")
                            # 只要最近15分钟的
                            if news_time < fifteen_minutes_ago:
                                logger.info(f"跳过旧新闻: {time_text}")
                                continue
                        else:
                            logger.warning(f"时间格式不匹配: {time_text}")
                            continue
                    else:
                        logger.warning(f"电报块 {i}: 未找到时间元素")
                        continue
                    
                    # 提取标题和内容
                    content_element = block.find('div')
                    if content_element:
                        title = content_element.get_text(strip=True)
                        # 安全清理换行符和控制字符，保护数字内容
                        original_title = title  # 保存原始标题用于调试
                        title = title.replace('\n', ' ').replace('\r', ' ').replace('\u2028', ' ').replace('\u2029', ' ')
                        # 使用更安全的空格处理，确保数字不被误删
                        import re
                        title = re.sub(r'\s+', ' ', title).strip()  # 将多个空白字符替换为单个空格
                        
                        # 调试：记录文本处理过程
                        if original_title != title:
                            logger.debug(f"文本处理: 原始='{original_title[:50]}...' -> 处理后='{title[:50]}...'")
                        else:
                            logger.debug(f"文本无需处理: '{title[:50]}...'")
                        if title and len(title) > 10:
                            # 提取链接
                            link_element = block.find('a')
                            url = link_element.get('href', '') if link_element else ''
                            
                            if url and not url.startswith('http'):
                                url = f"https://www.cls.cn{url}"
                            
                            # 提取股票信息
                            stock_container = block.find_next('div', class_='industry-stock')
                            stock_info = None
                            if stock_container:
                                stock_items = []
                                stock_links = stock_container.find_all('a')
                                for link in stock_links[:3]:  # 最多3只股票
                                    name_span = link.find('span', class_='c-222')
                                    change_span = link.find('span', class_='c-de0422')
                                    if name_span and change_span:
                                        name = name_span.get_text(strip=True)
                                        change = change_span.get_text(strip=True)
                                        stock_items.append(f"{name} {change}")
                                
                                if stock_items:
                                    stock_info = ' '.join(stock_items)
                            
                            news_item = NewsItem(
                                title=title,
                                url=url,
                                source="财联社电报",
                                news_time=time_text if time_element else None,
                                stock_info=stock_info
                            )
                            telegraph_items.append(news_item)
                            logger.info(f"添加电报项: {time_text} - {title[:50]}...")
                            
                except Exception as e:
                    logger.debug(f"解析电报项错误: {e}")
                    continue
            
            # 按新闻时间排序，最新的在前
            def parse_news_time(item):
                if item.news_time:
                    try:
                        time_parts = item.news_time.split(':')
                        today = datetime.now().date()
                        return datetime.combine(today, datetime.min.time().replace(
                            hour=int(time_parts[0]), 
                            minute=int(time_parts[1]), 
                            second=int(time_parts[2])
                        ))
                    except:
                        return datetime.min
                return datetime.min
            
            telegraph_items.sort(key=parse_news_time, reverse=True)
            logger.info(f"最终获得 {len(telegraph_items)} 个有效电报项")
            
            # 记录排序后的前5个电报时间
            for i, item in enumerate(telegraph_items[:5]):
                logger.info(f"排序后第{i+1}个电报: {item.news_time}")
            
        except Exception as e:
            logger.error(f"获取财联社电报失败: {e}")
        
        return telegraph_items[:5]  # 只保留最新5条
    
    def get_display_content(self) -> Dict:
        """获取当前应该显示的内容 - 基于10秒轮播"""
        with self.lock:
            current_time = datetime.now()
            # 使用更精确的轮播机制，减少同步问题
            cycle_second = int(current_time.timestamp()) % 10
            
            # 记录轮播状态到调试日志
            logger.debug(f"轮播状态: 当前时间={current_time.strftime('%H:%M:%S')}, 周期秒={cycle_second}")
            
            if cycle_second < 5:
                # 0-5秒：显示电报（轮播最新的5条中的前3条）
                if self.telegraph_items:
                    # 优先轮播最新的3条电报
                    display_telegraph = self.telegraph_items[:3]
                    if display_telegraph:
                        telegraph_index = (cycle_second * len(display_telegraph)) // 5
                        if telegraph_index < len(display_telegraph):
                            return {
                                'type': 'telegraph',
                                'content': display_telegraph[telegraph_index].to_dict()
                            }
                
                return {
                    'type': 'telegraph', 
                    'content': {'title': '📈 等待财联社电报数据...', 'source': '财联社电报'}
                }
            else:
                # 5-10秒：显示股指和板块
                display_data = {
                    'type': 'market',
                    'indices': [idx.to_dict() for idx in self.indices],
                    'sectors': [sector.to_dict() for sector in self.sectors]
                }
                return display_data
    
    def get_indices(self) -> List[Dict]:
        """获取股指数据"""
        with self.lock:
            return [idx.to_dict() for idx in self.indices]
    
    def get_sectors(self) -> List[Dict]:
        """获取板块数据"""
        with self.lock:
            return [sector.to_dict() for sector in self.sectors]
    
    def get_telegraph(self) -> List[Dict]:
        """获取电报数据"""
        with self.lock:
            return [item.to_dict() for item in self.telegraph_items]
    
    def get_status(self) -> Dict:
        """获取BigA模式状态"""
        with self.lock:
            return {
                'indices_count': len(self.indices),
                'sectors_count': len(self.sectors),
                'telegraph_count': len(self.telegraph_items),
                'last_indices_update': self.last_indices_update.isoformat(),
                'last_sectors_update': self.last_sectors_update.isoformat(),
                'last_telegraph_update': self.last_telegraph_update.isoformat()
            }
    
    def stop(self):
        """停止BigA数据更新"""
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=5)

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
            # BigA模式API端点
            elif path == '/biga/status':
                self._handle_biga_status()
            elif path == '/biga/next':
                self._handle_biga_next()
            elif path == '/biga/indices':
                self._handle_biga_indices()
            elif path == '/biga/sectors':
                self._handle_biga_sectors()
            elif path == '/biga/telegraph':
                self._handle_biga_telegraph()
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
    
    # BigA模式处理函数
    def _handle_biga_status(self):
        """处理BigA模式状态请求"""
        status = biga_pool.get_status()
        self._send_json_response(status)
    
    def _handle_biga_next(self):
        """处理BigA模式下一个内容请求"""
        content = biga_pool.get_display_content()
        self._send_json_response(content)
    
    def _handle_biga_indices(self):
        """处理BigA模式股指数据请求"""
        indices = biga_pool.get_indices()
        self._send_json_response(indices)
    
    def _handle_biga_sectors(self):
        """处理BigA模式板块数据请求"""
        sectors = biga_pool.get_sectors()
        self._send_json_response(sectors)
    
    def _handle_biga_telegraph(self):
        """处理BigA模式电报数据请求"""
        telegraph = biga_pool.get_telegraph()
        self._send_json_response(telegraph)
    
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
    global news_pool, biga_pool, httpd
    if news_pool:
        news_pool.stop()
    if biga_pool:
        biga_pool.stop()
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
        
        # 初始化BigA模式数据池
        logger.info("初始化BigA模式数据池...")
        global biga_pool
        biga_pool = BigAPool()
        
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
        logger.info("BigA Mode endpoints:")
        logger.info("  GET /biga/status    - BigA模式状态")
        logger.info("  GET /biga/next      - BigA模式轮播内容")
        logger.info("  GET /biga/indices   - 股指数据")
        logger.info("  GET /biga/sectors   - 板块数据")
        logger.info("  GET /biga/telegraph - 电报数据")
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    news_pool = None
    biga_pool = None
    httpd = None
    main()