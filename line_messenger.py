import json
import requests
from google.cloud import firestore
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class LineMessenger:
    def __init__(self, channel_access_token):
        self.channel_access_token = channel_access_token
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {channel_access_token}'
        }
        self.push_url = 'https://api.line.me/v2/bot/message/push'
        self.multicast_url = 'https://api.line.me/v2/bot/message/multicast'
        self.db = firestore.Client()
    
    def get_subscribers(self):
        """獲取所有訂閱用戶，最多5人"""
        users_ref = self.db.collection('users')
        docs = users_ref.stream()
        
        user_ids = []
        for doc in docs:
            user_data = doc.to_dict()
            if user_data.get('active', True):  # 只獲取活躍用戶
                user_ids.append(doc.id)
                # 限制最多5人，符合免費額度控制
                if len(user_ids) >= 5:
                    break
        
        logger.info(f"Found {len(user_ids)} active subscribers")
        return user_ids
    
    def format_news_message(self, news_data):
        """格式化新聞訊息"""
        # 檢測語言
        is_chinese = news_data.get('language', '').startswith('zh')
        if not is_chinese and any('\u4e00' <= char <= '\u9fff' for char in news_data['title']):
            is_chinese = True
        
        # 標題和摘要
        if is_chinese:
            message_text = f"{news_data['title']}\n\n"
        else:
            # 英文標題加引號更清晰
            message_text = f"「{news_data['title']}」\n\n"

        message_text += f"{news_data['summary']}\n\n"

        # 處理關鍵資訊
        if 'entities' in news_data and news_data['entities']:
            message_text += "【關鍵資訊】\n"

            # 翻譯類型名稱
            type_translations = {
                'PERSON': '人物',
                'ORGANIZATION': '組織',
                'LOCATION': '地點',
                'EVENT': '事件',
                'WORK_OF_ART': '作品',
                'CONSUMER_GOOD': '產品',
                'OTHER': '關鍵詞'
            }

            # 優先顯示的類別順序
            priority_order = ['PERSON', 'ORGANIZATION', 'LOCATION', 'EVENT', 'WORK_OF_ART', 'CONSUMER_GOOD', 'OTHER']
        
            # 按優先順序顯示關鍵資訊
            displayed = False
            for entity_type in priority_order:
                if entity_type in news_data['entities'] and news_data['entities'][entity_type]:
                    type_name = type_translations.get(entity_type, entity_type)
                    message_text += f"• {type_name}：{', '.join(news_data['entities'][entity_type])}\n"
                    displayed = True
            if not displayed:
                message_text += "• 無顯著關鍵詞\n"
        else:
            message_text += "【關鍵資訊】\n• 無顯著關鍵詞\n"
    
        # 添加原文連結
        message_text += f"\n閱讀全文：{news_data['link']}"
        
        return message_text
        
    
    def send_news(self, news_data, category):
        """發送新聞到所有訂閱者"""
        subscribers = self.get_subscribers()
        
        if not subscribers:
            logger.warning("No subscribers found")
            return False
        
        # 檢查訂閱者數量是否超過限制
        if len(subscribers) > 5:
            logger.warning(f"Subscriber count ({len(subscribers)}) exceeds limit of 5. Only sending to first 5 subscribers.")
            subscribers = subscribers[:5]
        
        # 準備消息內容
        message_text = self.format_news_message(news_data)
        
        # 準備消息物件
        category_label = "科技新聞" if category == "tech" else "商業新聞"
        message = {
            "type": "text",
            "text": f"【{category_label}】\n{message_text}"
        }
        
        # 使用 multicast API 一次發送給所有訂閱者（最多5人）
        try:
            data = {
                "to": subscribers,
                "messages": [message]
            }
            
            logger.info(f"Sending news to {len(subscribers)} subscribers")
            response = requests.post(self.multicast_url, headers=self.headers, data=json.dumps(data))
            
            if response.status_code == 200:
                logger.info("News sent successfully via multicast API")
                # 儲存發送記錄
                self.save_news_record(news_data, category)
                return True
            else:
                logger.error(f"Failed to send news via multicast API: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending news via multicast API: {str(e)}")
            return False
    
    def save_news_record(self, news_data, category):
        """保存新聞記錄到Firestore"""
        try:
            news_ref = self.db.collection('news').document()
            news_ref.set({
                'title': news_data['title'],
                'link': news_data['link'],
                'category': category,
                'sent_at': datetime.now(),
                'expire_at': datetime.now() + timedelta(days=1)  # 設置1天後過期
            })
            logger.info(f"News record saved: {news_data['title'][:50]}...")
        except Exception as e:
            logger.error(f"Error saving news record: {str(e)}")