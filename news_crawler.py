import feedparser
import requests
from datetime import datetime, timedelta
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsCrawler:
    def __init__(self):
        # 定義RSS源
        self.tech_sources = {
            'primary': 'https://techcrunch.com/feed/',
            'backup': 'https://www.bnext.com.tw/rss'  # 數位時代
        }
        
        self.business_sources = {
            'primary': 'https://money.udn.com/rssfeed/news/1001/5591/5612?ch=money', #經濟日報產業別 
            'backup': 'https://fortune.com/feed/'  
        }
    
    def fetch_news(self, category):
        """抓取特定類別的新聞"""
        if category not in ['tech', 'business']:
            raise ValueError("Category must be 'tech' or 'business'")
        
        sources = self.tech_sources if category == 'tech' else self.business_sources
        
        # 首先嘗試主要源
        try:
            feed = feedparser.parse(sources['primary'])
            if feed.entries and len(feed.entries) > 0:
                logger.info(f"Successfully fetched news from primary {category} source")
                return self._process_feed(feed, 'primary')
        except Exception as e:
            logger.warning(f"Failed to fetch from primary {category} source: {str(e)}")
        
        # 如果主要源失敗，嘗試備用源
        try:
            feed = feedparser.parse(sources['backup'])
            if feed.entries and len(feed.entries) > 0:
                logger.info(f"Successfully fetched news from backup {category} source")
                return self._process_feed(feed, 'backup')
        except Exception as e:
            logger.error(f"Failed to fetch from backup {category} source: {str(e)}")
            return None
        
        return None
    
    def _process_feed(self, feed, source_type):
        """處理RSS Feed並返回最新的文章"""
        # 獲取當天的新聞
        today = datetime.now().date()
        recent_entries = []
        
        for entry in feed.entries:
            # 解析發布日期
            if 'published_parsed' in entry:
                publish_date = datetime(*entry.published_parsed[:6]).date()
            elif 'updated_parsed' in entry:
                publish_date = datetime(*entry.updated_parsed[:6]).date()
            else:
                # 如果沒有日期信息，假設是最近的
                publish_date = today
            
            # 檢查是否是今天或昨天的文章
            if (today - publish_date).days <= 1:
                recent_entries.append({
                    'title': entry.title,
                    'link': entry.link,
                    'summary': entry.summary if 'summary' in entry else '',
                    'published': publish_date.isoformat(),
                    'source': source_type
                })
        
        # 按日期排序並取最新的一篇
        if recent_entries:
            sorted_entries = sorted(recent_entries, 
                                   key=lambda x: x['published'], 
                                   reverse=True)
            return sorted_entries[0]
        
        return None