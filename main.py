import os
import json
from flask import Flask
from google.cloud import firestore
from datetime import datetime, timedelta
import logging
from functions_framework import http

# 引入自定義模組
from news_crawler import NewsCrawler
from news_summarizer import NewsSummarizer
from line_messenger import LineMessenger

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化Flask應用 (用於共享一些功能)
app = Flask(__name__)

# 環境配置
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')

# 初始化Firestore
db = firestore.Client()

# Line相關處理
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError, LineBotApiError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent, UnfollowEvent
)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Line事件處理器
@handler.add(FollowEvent)
def handle_follow(event):
    """處理用戶關注事件"""
    user_id = event.source.user_id
    logger.info(f"User {user_id} followed the bot")
    
    # 檢查當前訂閱人數
    users_ref = db.collection('users')
    current_subscribers = len(list(users_ref.stream()))
    
    if current_subscribers >= 5:
        # 超過5人限制，拒絕新用戶
        welcome_message = "很抱歉，目前訂閱人數已達上限，暫時無法提供服務。"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_message)
        )
        return
    
    # 將用戶添加到訂閱資料庫
    user_ref = db.collection('users').document(user_id)
    user_ref.set({
        'active': True,
        'joined_at': datetime.now()
    })
    
    # 發送歡迎訊息
    welcome_message = "感謝您的訂閱！\n每天早上8:30和下午13:00，您將收到精選的科技和商業新聞摘要。\n\n您可以發送任何訊息來測試機器人回應。"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_message)
    )

@handler.add(UnfollowEvent)
def handle_unfollow(event):
    """處理用戶取消關注事件"""
    user_id = event.source.user_id
    logger.info(f"User {user_id} unfollowed the bot")
    
    # 從資料庫中移除用戶
    user_ref = db.collection('users').document(user_id)
    user_ref.delete()

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """處理用戶發送的文字訊息"""
    user_id = event.source.user_id
    user_message = event.message.text
    logger.info(f"Received message from {user_id}: {user_message}")
    
    # 檢查用戶是否在訂閱列表中
    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        # 用戶不在訂閱列表中
        reply_message = "您尚未訂閱新聞服務。請先關注此帳號以開始接收新聞。"
    else:
        # 根據用戶訊息提供相應回應
        message_lower = user_message.lower().strip()
        
        if any(keyword in message_lower for keyword in ['幫助', 'help', '說明', '指令']):
            reply_message = """可用指令：
• 發送「狀態」查看訂閱狀態
• 發送「取消」取消訂閱
• 每天8:30和13:00會自動推送新聞"""
        
        elif any(keyword in message_lower for keyword in ['狀態', 'status', '訂閱']):
            user_data = user_doc.to_dict()
            joined_date = user_data.get('joined_at', datetime.now()).strftime('%Y-%m-%d')
            reply_message = f"您的訂閱狀態：\n• 狀態：已訂閱\n• 訂閱日期：{joined_date}\n• 推送時間：每天8:30、13:00"
        
        elif any(keyword in message_lower for keyword in ['取消', 'unsubscribe', '退訂']):
            user_ref.delete()
            reply_message = "已成功取消訂閱。如需重新訂閱，請重新關注此帳號。"
        
        else:
            reply_message = f"收到您的訊息：「{user_message}」\n\n如需幫助，請發送「幫助」查看可用指令。"
    
    # 回覆訊息
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )

# 各功能處理函數
def send_tech_news_handler():
    """處理發送科技新聞的邏輯"""
    try:
        logger.info("Starting to fetch tech news")
        # 爬取最新科技新聞
        crawler = NewsCrawler()
        news_item = crawler.fetch_news('tech')
        
        if not news_item:
            logger.warning("No tech news found")
            return "No tech news found", 404
        
        # 生成摘要
        logger.info("Generating summary for tech news")
        summarizer = NewsSummarizer()
        summary = summarizer.summarize(news_item)
        
        # 發送到Line
        logger.info("Sending tech news to subscribers")
        messenger = LineMessenger(LINE_CHANNEL_ACCESS_TOKEN)
        result = messenger.send_news(summary, 'tech')
        
        if result:
            logger.info("Tech news sent successfully")
            return "Tech news sent successfully", 200
        else:
            logger.error("Failed to send tech news")
            return "Failed to send tech news", 500
    
    except Exception as e:
        logger.error(f"Error sending tech news: {str(e)}")
        return f"Error: {str(e)}", 500

def send_business_news_handler():
    """處理發送商業新聞的邏輯"""
    try:
        logger.info("Starting to fetch business news")
        # 爬取最新商業新聞
        crawler = NewsCrawler()
        news_item = crawler.fetch_news('business')
        
        if not news_item:
            logger.warning("No business news found")
            return "No business news found", 404
        
        # 生成摘要
        logger.info("Generating summary for business news")
        summarizer = NewsSummarizer()
        summary = summarizer.summarize(news_item)
        
        # 發送到Line
        logger.info("Sending business news to subscribers")
        messenger = LineMessenger(LINE_CHANNEL_ACCESS_TOKEN)
        result = messenger.send_news(summary, 'business')
        
        if result:
            logger.info("Business news sent successfully")
            return "Business news sent successfully", 200
        else:
            logger.error("Failed to send business news")
            return "Failed to send business news", 500
    
    except Exception as e:
        logger.error(f"Error sending business news: {str(e)}")
        return f"Error: {str(e)}", 500

def cleanup_handler():
    """處理清理過期新聞的邏輯"""
    try:
        logger.info("Starting cleanup of expired news")
        # 查詢過期的新聞記錄
        now = datetime.now()
        news_ref = db.collection('news')
        expired_news = news_ref.where('expire_at', '<=', now).stream()
        
        # 刪除過期記錄
        deleted_count = 0
        for doc in expired_news:
            doc.reference.delete()
            deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} expired news records")
        return f"Cleaned up {deleted_count} expired news records", 200
    
    except Exception as e:
        logger.error(f"Error cleaning up news: {str(e)}")
        return f"Error: {str(e)}", 500

# Cloud Functions/Cloud Run 主入口點
@http
def webhook(request):
    """主要HTTP入口點，處理所有請求"""
    path = request.path
    method = request.method
    
    logger.info(f"Received {method} request to {path}")
    
    # 根據路徑和方法分發請求
    if path == '/callback' and method == 'POST':
        # 處理Line的Webhook請求
        signature = request.headers.get('X-Line-Signature', '')
        body = request.get_data(as_text=True)
        
        logger.info(f"Processing Line webhook: {body[:100]}...")
        
        try:
            handler.handle(body, signature)
            return ('OK', 200)
        except InvalidSignatureError:
            logger.error("Invalid signature from LINE")
            return ('Invalid signature', 400)
        except LineBotApiError as e:
            logger.error(f"LINE Bot API error: {e.status_code} - {e.error.message}")
            return ('LINE API error', 200)  # 仍返回200避免LINE重試
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}", exc_info=True)
            return ('Internal error', 200)  # 仍返回200避免LINE重試
    
    elif path == '/' and method == 'GET':
        # 處理根路徑請求（健康檢查）
        return ('Line Bot Server is running!', 200)
    
    elif path == '/send_tech_news':
        # 處理發送科技新聞請求
        return send_tech_news_handler()
    
    elif path == '/send_business_news':
        # 處理發送商業新聞請求
        return send_business_news_handler()
    
    elif path == '/cleanup':
        # 處理清理過期新聞請求
        return cleanup_handler()
    
    else:
        logger.warning(f"Unknown path: {path}")
        return ('Not Found', 404)