from google.cloud import language_v1
import google.generativeai as genai
import os
import html
import re
import json

class NewsSummarizer:
    def __init__(self):
        # 初始化原有的 Google Natural Language API 客戶端作為後備
        self.language_client = language_v1.LanguageServiceClient()
        
        # 初始化 Gemini API
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
            # 設置使用的模型 - 使用 Gemini 2.0 Flash
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
            print("Gemini API 初始化成功")
        else:
            self.gemini_model = None
            print("Warning: GEMINI_API_KEY not found. Falling back to Google NL API for summarization.")
    
    def clean_html(self, text):
        """清理HTML標籤和字符實體"""
        # 先解碼HTML實體
        text = html.unescape(text)
        # 移除HTML標籤
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多餘空白
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def summarize_with_gemini(self, text, language_code, max_length=350):
        """使用 Gemini API 生成新聞摘要"""
        try:
            # 根據語言選擇適當的提示詞
            if language_code.startswith('zh') or any('\u4e00' <= char <= '\u9fff' for char in text[:100]):
                prompt = f"""
                請幫我將以下新聞內容生成一個簡潔、流暢的中文摘要，長度約300字以內。
                摘要必須是繁體中文，不要使用英文。
                保留最重要的事實和細節，但不要添加原文中沒有的信息。
                
                新聞內容：
                {text}
                
                請直接給出摘要，不要加入額外的說明或引言。
                """
            else:
                prompt = f"""
                Please create a concise and coherent summary of the following news article, 
                in about 400 characters. Retain the most important facts and details,
                but don't add information not present in the original text.
                
                News content:
                {text}
                
                Provide the summary directly without additional explanations or introductions.
                """
            
            # 呼叫 Gemini API
            print(f"發送請求到 Gemini API，提示詞長度: {len(prompt)}")
            response = self.gemini_model.generate_content(prompt)
            summary = response.text
            print(f"Gemini API 成功回應，摘要長度: {len(summary)}")
            
            # 如果摘要過長，進行截斷
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."
            
            return summary
        
        except Exception as e:
            print(f"使用 Gemini API 生成摘要時出錯: {str(e)}")
            return None
    
    def extract_entities_with_gemini(self, text, language_code):
        """使用 Gemini API 提取實體"""
        try:
            # 根據語言選擇適當的提示詞
            if language_code.startswith('zh'):
                prompt = f"""
                請從以下新聞內容中提取重要的實體，並按以下類別分類：
                人物 (PERSON)、組織 (ORGANIZATION)、地點 (LOCATION)、事件 (EVENT)、藝術作品/產品 (WORK_OF_ART)、
                消費品 (CONSUMER_GOOD) 和其他重要關鍵詞 (OTHER)。
                
                每個類別最多列出3個最重要的實體。如果某類別沒有實體，請省略該類別。
                
                新聞內容：
                {text}
                
                請以JSON格式輸出，格式如下：
                {{
                  "PERSON": ["人名1", "人名2"],
                  "ORGANIZATION": ["組織1", "組織2"],
                  ...
                }}
                
                僅返回JSON格式的結果，不要有其他文字。
                """
            else:
                prompt = f"""
                Extract important entities from the following news content and categorize them by:
                PERSON, ORGANIZATION, LOCATION, EVENT, WORK_OF_ART, CONSUMER_GOOD, and OTHER important keywords.
                
                For each category, list up to 3 most important entities. Omit categories with no entities.
                
                News content:
                {text}
                
                Output in JSON format like:
                {{
                  "PERSON": ["name1", "name2"],
                  "ORGANIZATION": ["org1", "org2"],
                  ...
                }}
                
                Return only the JSON result without any other text.
                """
            
            # 呼叫 Gemini API
            print("發送實體提取請求到 Gemini API")
            response = self.gemini_model.generate_content(prompt)
            
            # 處理回應
            result_text = response.text.strip()
            
            # 嘗試解析 JSON
            try:
                # 移除可能的代碼塊標記
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                
                result_text = result_text.strip()
                entities = json.loads(result_text)
                print(f"成功解析實體 JSON，類別數: {len(entities)}")
                return entities
            except json.JSONDecodeError as e:
                print(f"解析 Gemini 回應的 JSON 時出錯: {str(e)}")
                print(f"原始回應: {result_text}")
                return {}
        
        except Exception as e:
            print(f"使用 Gemini API 提取實體時出錯: {str(e)}")
            return {}
    
    def is_valid_entity(self, name, category, language_code):
        """檢查實體名稱是否合理 (保留原有功能作為後備)"""
        # 檢查PERSON類別，確保不是長句
        if category == 'PERSON':
            # 中文人名通常不會超過5個字
            if language_code.startswith('zh') and len(name) > 8:
                return False
            # 英文人名通常不會有標點
            elif (',' in name or '.' in name or ';' in name):
                return False
            # 英文人名通常不會超過20個字符
            elif len(name) > 20:
                return False
        
        # 過濾掉包含完整句子的實體
        if '。' in name or '！' in name or '？' in name or '；' in name:
            return False
        if '.' in name and len(name) > 15:  # 允許縮寫中的點
            return False
        
        return True
    
    def fallback_extract_entities(self, text, language='zh'):
        """原有的實體提取方法，作為後備"""
        document = language_v1.Document(
            content=text,
            type_=language_v1.Document.Type.PLAIN_TEXT,
            language=language
        )
        
        try:
            response = self.language_client.analyze_entities(document=document)
            
            # 按類型分類實體
            categorized_entities = {
                'PERSON': [],       # 人物
                'ORGANIZATION': [], # 組織
                'LOCATION': [],     # 地點
                'EVENT': [],        # 事件
                'WORK_OF_ART': [],  # 藝術作品/產品
                'CONSUMER_GOOD': [], # 消費品
                'OTHER': []         # 其他
            }
            
            for entity in response.entities:
                if entity.salience > 0.05:  # 顯著性閾值
                    category = language_v1.Entity.Type(entity.type_).name
                    # 驗證實體有效性
                    if self.is_valid_entity(entity.name, category, language):
                        if category in categorized_entities:
                            # 檢查是否已經存在
                            names = [e['name'] for e in categorized_entities[category]]
                            if entity.name not in names:
                                categorized_entities[category].append({
                                    'name': entity.name,
                                    'salience': entity.salience
                                })
                        else:
                            categorized_entities['OTHER'].append({
                                'name': entity.name,
                                'salience': entity.salience
                            })
            
            # 整理結果
            result = {}
            for category, entities in categorized_entities.items():
                if entities:
                    # 每類排序並最多取3個
                    sorted_entities = sorted(entities, key=lambda x: x['salience'], reverse=True)[:3]
                    result[category] = [e['name'] for e in sorted_entities]
            
            return result
            
        except Exception as e:
            print(f"提取實體時出錯: {str(e)}")
            return {}
    
    def fallback_generate_summary(self, text, max_length=350):
        """原有的摘要生成方法，作為後備"""
        # 分割成句子
        sentences = re.split(r'(?<=[。.!?！？])\s*', text)
        
        if len(sentences) <= 3 or len(text) <= max_length:
            # 如果文本很短或句子很少，直接返回原文
            return text
        
        # 計算詞頻（用於句子重要性評分）
        word_frequencies = {}
        for sentence in sentences:
            # 對於中文，我們按字符分割；對於英文/混合文本，按空格分割
            has_spaces = ' ' in sentence
            words = sentence.split() if has_spaces else list(sentence)
            
            for word in words:
                if word.lower() not in word_frequencies:
                    word_frequencies[word.lower()] = 1
                else:
                    word_frequencies[word.lower()] += 1
        
        # 計算最大詞頻，用於正規化
        max_frequency = max(word_frequencies.values()) if word_frequencies else 1
        
        # 計算每個句子的分數
        sentence_scores = {}
        for i, sentence in enumerate(sentences):
            has_spaces = ' ' in sentence
            words = sentence.split() if has_spaces else list(sentence)
            
            # 避免太短的句子
            if len(words) < 3:
                continue
                
            # 計算句子分數
            score = 0
            for word in words:
                score += word_frequencies.get(word.lower(), 0) / max_frequency
            
            # 考慮句子位置（前面的句子更重要）
            position_weight = 1.0 if i < 3 else 0.8
            sentence_scores[i] = score * position_weight
        
        # 選擇分數最高的2-4個句子
        top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:4]
        
        # 按原始順序重組句子
        selected_sentences = sorted(top_sentences, key=lambda x: x[0])
        summary = ' '.join([sentences[i] for i, _ in selected_sentences])
        
        # 如果摘要還是太長，截斷
        if len(summary) > max_length:
            summary = summary[:max_length-3] + '...'
            
        return summary
    
    def summarize(self, news_item):
        """摘要新聞內容，首先嘗試 Gemini API，失敗則回退到原有方法"""
        try:
            # 檢查輸入
            if not news_item:
                print("Error: news_item is None")
                return None

            if 'title' not in news_item:
                print("Error: news_item missing 'title'")
                return None

            # 清理HTML和格式化文本
            if 'summary' in news_item and news_item['summary']:
                clean_text = self.clean_html(news_item['summary'])
                print(f"使用新聞摘要進行處理，長度: {len(clean_text)}")
            else:
                clean_text = news_item['title']  # 如果沒有摘要，使用標題
                print(f"使用新聞標題進行處理: {clean_text}")
            
            # 更準確的語言檢測邏輯
            # 首先檢查文本中是否有中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in news_item.get('title', '') + (news_item.get('summary', '') or ''))
            
            if has_chinese:
                language_code = 'zh'
                print("檢測到中文內容")
            else:
                # 如果沒有明顯的中文字符，才使用 Google API 進行語言檢測
                try:
                    document = language_v1.Document(
                        content=clean_text,
                        type_=language_v1.Document.Type.PLAIN_TEXT
                    )
                    language_response = self.language_client.detect_language(document=document)
                    language_code = language_response.languages[0].language_code
                    print(f"Google API 檢測到語言: {language_code}")
                except Exception as e:
                    print(f"語言檢測錯誤: {str(e)}")
                    # 如果檢測失敗，根據 ASCII 字符比例猜測語言
                    non_ascii_ratio = sum(1 for char in clean_text if ord(char) > 127) / (len(clean_text) or 1)
                    language_code = 'zh' if non_ascii_ratio > 0.1 else 'en'
                    print(f"語言檢測失敗，根據字符推測語言為: {language_code}")
            
            # 調整摘要長度
            max_length = 300 if language_code.startswith('zh') else 400
            
            # 嘗試使用 Gemini API 生成摘要
            if self.gemini_model:
                print("使用 Gemini API 生成摘要")
                summary = self.summarize_with_gemini(clean_text, language_code, max_length)
                
                # 如果 Gemini API 失敗，使用後備方法
                if not summary:
                    print("Gemini API 摘要失敗，使用後備方法")
                    summary = self.fallback_generate_summary(clean_text, max_length)
            else:
                # 沒有配置 Gemini API，直接使用後備方法
                print("未配置 Gemini API，使用後備方法生成摘要")
                summary = self.fallback_generate_summary(clean_text, max_length)
            
            # 檢查摘要是否符合語言要求
            if language_code.startswith('zh'):
                # 檢查摘要是否包含足夠的中文字符
                chinese_char_count = sum(1 for char in summary if '\u4e00' <= char <= '\u9fff')
                if chinese_char_count < len(summary) * 0.3:  # 如果中文字符不足30%
                    print("摘要語言不符合要求，重新使用後備方法")
                    summary = self.fallback_generate_summary(clean_text, max_length)
            
            # 提取分類後的實體
            if self.gemini_model:
                print("使用 Gemini API 提取實體")
                categorized_entities = self.extract_entities_with_gemini(clean_text, language_code)
                
                # 如果 Gemini API 提取實體失敗，使用後備方法
                if not categorized_entities:
                    print("Gemini API 實體提取失敗，使用後備方法")
                    categorized_entities = self.fallback_extract_entities(clean_text, language_code)
            else:
                # 沒有配置 Gemini API，直接使用後備方法
                print("未配置 Gemini API，使用後備方法提取實體")
                categorized_entities = self.fallback_extract_entities(clean_text, language_code)
            
            # 返回結果
            result = {
                'title': news_item.get('title', '無標題'),
                'summary': summary,
                'entities': categorized_entities,
                'language': language_code,
                'link': news_item.get('link', '#')
            }
            print(f"成功生成摘要，長度: {len(summary)}")
            return result
            
        except Exception as e:
            print(f"摘要生成過程中出錯: {str(e)}")
            # 即使出錯也返回基本信息
            try:
                return {
                    'title': news_item.get('title', '無標題'),
                    'summary': clean_text[:200] + '...' if len(clean_text) > 200 else clean_text,
                    'entities': {},
                    'language': language_code if 'language_code' in locals() else 'zh',
                    'link': news_item.get('link', '#')
                }
            except:
                # 極端情況下的後備
                return {
                    'title': '處理失敗',
                    'summary': '無法處理此新聞',
                    'entities': {},
                    'language': 'zh',
                    'link': '#'
                }