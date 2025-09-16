# 自動推送新聞 Line Bot
目的 : 資訊更新快速，為了確保每天至少吸收兩個新資訊(知識)，並且是以有效率的方式。
## 簡介
這是一個自動的 LINE Bot，會於早上 8:30 整理一篇科技新聞，以及在下午 1:00 整理一篇商業新聞，向訂閱用戶推送新聞網站中最新的新聞摘要。

## 功能
1. **自動爬取新聞**：從 TechCrunch、數位時代、經濟日報等來源爬取最新新聞
2. **生成摘要**：使用 Google Gemini API 生成簡潔的新聞摘要
3. **識別關鍵字**：提取新聞中的人物、組織、地點等關鍵信息
4. **LINE 推送**：群發消息給所有訂閱用戶
5. **數據管理**：使用 Firestore 管理用戶訂閱和新聞記錄
6. **多語言支持**：支持中文和英文新聞
7. **定時推送**：每天早上 8:30 和 下午 1:00

## 系統架構

```
LINE Webhook → Cloud Functions → News Processing → Firestore
                      ↓
            Gemini API (摘要生成) → LINE API (消息推送)
                      ↓
            Google NL API (實體識別)
```

## 技術棧
- **後端框架**：Flask + Functions Framework
- **部署**：Google Cloud Functions
- **數據庫**：Google Firestore
- **AI 服務**：Google Gemini API, Google Natural Language API
- **訊息平台**：LINE Bot API
- **新聞來源**：RSS feeds (TechCrunch, 數位時代, 經濟日報等)

## 建置步驟
### 1. 前置
#### LINE Bot 設置
1. 在 [LINE Developers Console](https://developers.line.biz/) 創建新的 Channel
2. 獲取 `Channel Secret` 和 `Channel Access Token`
3. 設置 Webhook URL (部署後獲得)
#### Google Cloud 設置
1. 創建 Google Cloud 項目
2. 啟用以下 API：
   - Cloud Functions API
   - Firestore API
   - Natural Language API
3. 創建服務帳戶並下載金鑰檔案
4. 獲取 [Gemini API Key](https://ai.google.dev/)

### 2. 環境配置

創建 `.env` 檔案：
```bash
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
```

### 3. 本地開發
```bash
pip install -r requirements.txt
functions-framework --target=webhook --debug
```
### 4. 部署到 Cloud Run Functions
```bash
gcloud functions deploy news_linebot \
  --runtime python39 \
  --trigger-http \
  --allow-unauthenticated \
  --region asia-east1 \
  --entry-point webhook \
  --set-env-vars LINE_CHANNEL_SECRET=your_secret,LINE_CHANNEL_ACCESS_TOKEN=your_token,GEMINI_API_KEY=your_key
```

### 5. 設置定時功能 (Cloud Scheduler)
使用 Cloud Scheduler 創建定時任務：
```bash
# 科技新聞 (每天 8:30)
gcloud scheduler jobs create http tech-news-job \
  --schedule="30 8 * * *" \
  --uri="https://asia-east1-your-project-id.cloudfunctions.net/news_linebot/send_tech_news" \
  --http-method=GET \
  --time-zone="Asia/Taipei"

# 商業新聞 (每天 13:00)
gcloud scheduler jobs create http business-news-job \
  --schedule="0 13 * * *" \
  --uri="https://asia-east1-your-project-id.cloudfunctions.net/news_linebot/send_business_news" \
  --http-method=GET \
  --time-zone="Asia/Taipei"

# 清理過期新聞 (每天 2:00)
gcloud scheduler jobs create http cleanup-job \
  --schedule="0 2 * * *" \
  --uri="https://asia-east1-your-project-id.cloudfunctions.net/news_linebot/cleanup" \
  --http-method=GET \
  --time-zone="Asia/Taipei"
```

## API 端點
| 端點 | 方法 | 描述 |
|------|------|------|
| `/callback` | POST | LINE Webhook 回調 |
| `/send_tech_news` | GET | 手動觸發科技新聞推送 |
| `/send_business_news` | GET | 手動觸發商業新聞推送 |
| `/cleanup` | GET | 清理過期新聞記錄 |
| `/` | GET | 健康檢查 |

## 數據結構
### Firestore 
#### `users` 集合
```json
{
  "user_id": {
    "active": true,
    "joined_at": "2024-01-15T10:30:00Z"
  }
}
```

#### `news` 集合
```json
{
  "news_id": {
    "title": "新聞標題",
    "link": "https://...",
    "category": "tech|business",
    "sent_at": "2024-01-15T08:30:00Z",
    "expire_at": "2024-01-16T08:30:00Z"
  }
}
```

## 新聞來源

### 科技新聞
- **主要來源**：TechCrunch (https://techcrunch.com/feed/)
- **備用來源**：數位時代 (https://www.bnext.com.tw/rss)

### 商業新聞
- **主要來源**：經濟日報 (https://money.udn.com/rssfeed/news/1001/5591/5612?ch=money)
- **備用來源**：Fortune (https://fortune.com/feed/)

## 訊息推送格式
推送的新聞消息包含：
- 新聞類別標籤
- 新聞標題和摘要
- 關鍵實體信息（人物、組織、地點等）
- 原文連結

舉例：
```
【科技新聞】
「OpenAI 發布新版 GPT 模型」

OpenAI 今天宣布推出最新的 GPT 模型，具備更強的推理能力和更廣泛的知識覆蓋。新模型在多個基準測試中表現優異...

【關鍵資訊】
• 人物：Sam Altman
• 組織：OpenAI, Microsoft
• 關鍵詞：GPT, 人工智能

閱讀全文：https://...
```

## 常見問題
1. **新聞爬取失敗**
   - 檢查 RSS 源是否可用
   - 確認網絡連接正常

2. **摘要生成失敗**
   - 檢查 Gemini API 配額
   - 確認 API 金鑰有效性

3. **LINE 推送失敗**
   - 驗證 LINE Channel 設置
   - 檢查用戶是否封鎖機器人

4. **Firestore 連接問題**
   - 確認服務帳戶權限
   - 檢查 API 是否啟用


