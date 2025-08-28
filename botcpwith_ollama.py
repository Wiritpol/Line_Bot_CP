from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,URIAction,
    TemplateSendMessage, CarouselTemplate, CarouselColumn, MessageAction
)
from sentence_transformers import SentenceTransformer, util
import csv
import requests
import json
import re

app = Flask(__name__)

# LINE Credentials
CHANNEL_SECRET = 'xxx'
CHANNEL_ACCESS_TOKEN = 'xxx'

# Ollama Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"  # หรือ model อื่นที่คุณมี

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')


@app.route("/", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


def summarize_product_description(description):
    """ใช้ Ollama สรุปคำอธิบายสินค้าให้กระชับ"""
    if not description or len(description.strip()) < 50:
        return description
    
    try:
        prompt = f"""กรุณาสรุปคำอธิบายสินค้านี้ให้กระชับและเข้าใจง่าย โดย:
        - ลบ emoji และสัญลักษณ์พิเศษออก
        - เน้นข้อมูลสำคัญเช่น ส่วนผสม คุณประโยชน์ ขนาด
        - ใช้ภาษาไทยง่ายๆ ไม่เกิน 3-4 บรรทัด
        - ไม่ต้องมีข้อมูลการจัดส่งหรือเงื่อนไขการสั่งซื้อ
        
        คำอธิบายเดิม: {description}
        
        สรุป:"""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "max_tokens": 200
            }
        }
        
        response = requests.post(OLLAMA_URL, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            summary = result.get("response", "").strip()
            
            # ตรวจสอบว่า summary ไม่ว่างและมีเนื้อหาที่เหมาะสม
            if summary and len(summary) > 20:
                return summary
            else:
                return clean_description_manually(description)
        else:
            return clean_description_manually(description)
            
    except Exception as e:
        print(f"Summary error: {e}")
        return clean_description_manually(description)


def clean_description_manually(description):
    """ทำความสะอาดคำอธิบายแบบง่ายๆ หาก Ollama ไม่สามารถใช้ได้"""
    if not description:
        return "ไม่มีรายละเอียด"
    
    # ลบ emoji และสัญลักษณ์พิเศษ
    clean_text = re.sub(r'[❤️✅‼️?️?]', '', description)
    clean_text = re.sub(r'#\w+', '', clean_text)  # ลบ hashtag
    clean_text = re.sub(r'-{3,}', '', clean_text)  # ลบเส้นประ
    
    # แยกเป็นประโยค
    sentences = [s.strip() for s in clean_text.split('.') if s.strip()]
    
    # เอาเฉพาะประโยคสำคัญ (ไม่เกิน 4 ประโยคแรก)
    important_sentences = []
    for sentence in sentences[:4]:
        if any(keyword in sentence for keyword in ['ส่วนผสม', 'โปรตีน', 'วิตามิน', 'พลังงาน', 'ซุป', 'อาหาร']):
            important_sentences.append(sentence)
    
    # ถ้าไม่มีประโยคสำคัญ เอา 2 ประโยคแรก
    if not important_sentences:
        important_sentences = sentences[:2]
    
    result = '. '.join(important_sentences).strip()
    
    # จำกัดความยาว
    if len(result) > 300:
        result = result[:300] + "..."
    
    return result if result else "ไม่มีรายละเอียดเพิ่มเติม"

def call_ollama(prompt, context=""):
    """เรียก Ollama API เพื่อสร้างคำตอบ"""
    try:
        full_prompt = f"""คุณเป็นผู้ช่วยในร้านอาหาร CP ที่ให้คำแนะนำเกี่ยวกับสินค้าและตอบคำถามของลูกค้า
        
        ข้อมูลบริบท: {context}
        
        คำถามของลูกค้า: {prompt}
        
        กรุณาตอบด้วยภาษาไทยในลักษณะที่เป็นมิตรและให้ข้อมูลที่เป็นประโยชน์ หากไม่มีข้อมูลที่เกี่ยวข้อง ให้แนะนำให้ลูกค้าดูเมนูหรือสินค้าที่มี
        ตอบแค่ข้อความสั้นๆ ไม่เกิน 200 คำ"""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "max_tokens": 300
            }
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "ขออภัย ไม่สามารถตอบได้ในขณะนี้")
        else:
            return "ขออภัย ระบบขัดข้อง กรุณาลองใหม่อีกครั้ง"

    except requests.exceptions.RequestException:
        return "ขออภัย ไม่สามารถเชื่อมต่อกับระบบได้ กรุณาลองใหม่อีกครั้ง"
    except Exception as e:
        print(f"Ollama error: {e}")
        return "ขออภัย เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง"



def fetch_cp_products_from_csv(csv_path="cp_products_detailed_new.csv"):
    products = []
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row.get("ชื่อสินค้า")
                image = row.get("รูปภาพ")
                price = row.get("ราคาปกติ")
                link = row.get("ลิงก์")
                desc = row.get("คำอธิบาย")

                if name and image:
                    products.append({
                        "name": name,
                        "image_url": image,
                        "price": price,
                        "description": desc,
                        "link": link
                    })
    except FileNotFoundError:
        print(f"⚠️ CSV file '{csv_path}' not found.")

    return products


def word_similarity(word1, word2):
    embeddings = model.encode([word1, word2], convert_to_tensor=True)
    score = util.cos_sim(embeddings[0], embeddings[1]).item()
    return score


def extract_price_number(price_string):
    """แยกตัวเลขราคาออกมาจาก string โดยเฉพาะเจาะจงกับราคา"""
    if not price_string:
        return 0
    
    # ลบช่องว่างและแปลงเป็นตัวพิมพ์เล็ก
    price_clean = price_string.strip()
    
    # หา pattern ที่มีสัญลักษณ์ ฿ หรือคำว่า "บาท"
    # Pattern 1: ฿XX หรือ ฿XX.XX
    baht_pattern = r'฿\s*(\d{1,}(?:,\d{3})*(?:\.\d{2})?)'
    match = re.search(baht_pattern, price_clean)
    if match:
        price_str = match.group(1).replace(',', '')
        return float(price_str)
    
    # Pattern 2: XX บาท หรือ XX.XX บาท
    baht_word_pattern = r'(\d{1,}(?:,\d{3})*(?:\.\d{2})?)\s*บาท'
    match = re.search(baht_word_pattern, price_clean)
    if match:
        price_str = match.group(1).replace(',', '')
        return float(price_str)
    
    # Pattern 3: ราคาเดิม ฿XX ราคาใหม่ ฿YY (เอาราคาใหม่)
    multiple_prices = re.findall(baht_pattern, price_clean)
    if len(multiple_prices) >= 2:
        # เอาราคาตัวสุดท้าย (มักเป็นราคาที่ลดแล้ว)
        return float(multiple_prices[-1].replace(',', ''))
    
    # Pattern 4: XX/YY (เช่น เดิม 150/ใหม่ 120) - เอาตัวสุดท้าย
    slash_pattern = r'(\d+)/(\d+)'
    match = re.search(slash_pattern, price_clean)
    if match:
        return float(match.group(2))  # เอาตัวหลัง slash
    
    # ถ้าไม่เจอ pattern ไหนเลย ลองหาเลขที่อยู่ในช่วงราคาที่เป็นไปได้
    all_numbers = re.findall(r'\d+(?:\.\d{2})?', price_clean.replace(',', ''))
    if all_numbers:
        # กรองเอาเฉพาะตัวเลขที่อาจเป็นราคา (15-9999 บาท)
        potential_prices = []
        for num_str in all_numbers:
            num = float(num_str)
            if 15 <= num <= 9999:  # ช่วงราคาที่เป็นไปได้
                potential_prices.append(num)
        
        if potential_prices:
            return max(potential_prices)  # เอาราคาสูงสุด (มักเป็นราคาจริง)
    
    return 0


def parse_user_query(user_message):
    """วิเคราะห์คำค้นหาของผู้ใช้เพื่อหาเงื่อนไขต่างๆ"""
    query_info = {
        'keywords': [],
        'max_price': None,
        'min_price': None,
        'price_range': None,
        'original_query': user_message.lower()
    }
    
    message_lower = user_message.lower()
    
    # หาเงื่อนไขราคาด้วย pattern ที่เฉพาะเจาะจงมากขึ้น
    price_patterns = [
        # ราคาต่ำกว่า, น้อยกว่า, ไม่เกิน + บาท
        (r'(?:ราคา)?(?:ต่ำกว่า|น้อยกว่า|ไม่เกิน)\s*(\d+)\s*(?:บาท)?', 'max'),
        # ราคาสูงกว่า, มากกว่า, เกิน + บาท  
        (r'(?:ราคา)?(?:สูงกว่า|มากกว่า|เกิน)\s*(\d+)\s*(?:บาท)?', 'min'),
        # ราคาประมาณ, รอบๆ + บาท
        (r'(?:ราคา)?(?:ประมาณ|รอบ|รอบๆ)\s*(\d+)\s*(?:บาท)?', 'around'),
        # ราคา XX บาท
        (r'ราคา\s*(\d+)\s*บาท', 'around'),
        # เฉพาะคำว่า ราคา ตามด้วยตัวเลข (ไม่มี กรัม, มล., กก., ชิ้น ด้านหลัง)
        (r'ราคา\s*(\d+)(?!\s*(?:กรัม|มล|กก|ชิ้น|ก\.?|มล\.?))', 'around'),
    ]
    
    for pattern, price_type in price_patterns:
        match = re.search(pattern, message_lower)
        if match:
            price = int(match.group(1))
            # ตรวจสอบว่าเป็นตัวเลขที่เป็นไปได้สำหรับราคา
            if 10 <= price <= 9999:  # ช่วงราคาที่เหมาะสม
                if price_type == 'max':
                    query_info['max_price'] = price
                elif price_type == 'min':
                    query_info['min_price'] = price
                elif price_type == 'around':
                    # ประมาณ ±25%
                    margin = int(price * 0.25)
                    query_info['min_price'] = max(0, price - margin)
                    query_info['max_price'] = price + margin
                break
    
    # หาคำค้นหาหลักโดยลบเงื่อนไขราคาออก
    keywords_text = message_lower
    # ลบคำที่เกี่ยวกับราคาและหน่วยต่างๆ
    remove_patterns = [
        r'ราคา(?:ต่ำกว่า|น้อยกว่า|สูงกว่า|มากกว่า|ไม่เกิน|เกิน|ประมาณ|รอบ|รอบๆ)?\s*\d+\s*(?:บาท)?',
        r'(?:ต่ำกว่า|น้อยกว่า|สูงกว่า|มากกว่า|ไม่เกิน|เกิน|ประมาณ|รอบ|รอบๆ)\s*\d+\s*(?:บาท)?',
        r'\d+\s*(?:กรัม|มล|กก|ชิ้น|ก\.?|มล\.?)',  # ลบข้อมูลขนาด
        r'(?:อยาก|ต้องการ|ขอ|หา|ให้)'  # ลบคำขอร้อง
    ]
    
    for pattern in remove_patterns:
        keywords_text = re.sub(pattern, ' ', keywords_text)
    
    keywords_text = re.sub(r'\s+', ' ', keywords_text).strip()
    
    if keywords_text:
        query_info['keywords'] = [kw.strip() for kw in keywords_text.split() if len(kw.strip()) > 1]
    
    return query_info


def filter_products_by_criteria(products, query_info):
    """กรองสินค้าตามเงื่อนไขที่วิเคราะห์ได้"""
    filtered_products = []
    
    for product in products:
        price = extract_price_number(product.get('price', '0'))
        
        # ตรวจสอบเงื่อนไขราคา
        if query_info['max_price'] is not None and price > query_info['max_price']:
            continue
        if query_info['min_price'] is not None and price < query_info['min_price']:
            continue
        
        filtered_products.append(product)
    
    return filtered_products


def smart_product_search(user_query, menu_items, top_k=5, threshold=0.3):
    """ค้นหาสินค้าแบบฉลาดโดยพิจารณาเงื่อนไขต่างๆ"""
    if not menu_items:
        return []
    
    # วิเคราะห์คำค้นหา
    query_info = parse_user_query(user_query)
    
    # กรองสินค้าตามเงื่อนไขราคาก่อน
    filtered_products = filter_products_by_criteria(menu_items, query_info)
    
    if not filtered_products:
        return []
    
    # ถ้ามีคำค้นหา ให้หาสินค้าที่ตรงกับคำค้นหา
    if query_info['keywords']:
        search_text = ' '.join(query_info['keywords'])
        similarities = []
        
        for item in filtered_products:
            score = word_similarity(search_text, item["name"].lower())
            if score >= threshold:
                similarities.append({
                    "item": item,
                    "score": score
                })
        
        similarities.sort(key=lambda x: x["score"], reverse=True)
        
        unique_items = []
        seen_names = set()
        for sim in similarities:
            item = sim["item"]
            if item["name"] not in seen_names:
                unique_items.append(item)
                seen_names.add(item["name"])
        
        return unique_items[:top_k]
    
    # ถ้าไม่มีคำค้นหา แสดงสินค้าที่ตรงเงื่อนไขราคา เรียงตามราคา
    else:
        # เรียงตามราคา (ถ้าต้องการราคาต่ำ ให้เรียงจากต่ำไปสูง)
        if query_info['max_price'] is not None:
            filtered_products.sort(key=lambda x: extract_price_number(x.get('price', '0')))
        else:
            filtered_products.sort(key=lambda x: -extract_price_number(x.get('price', '0')))
        
        return filtered_products[:top_k]


def create_product_carousel(products, search_query):
    if not products:
        return None

    carousel_columns = []
    for product in products:
        title = product["name"][:40]
        price = product["price"]
        text = f"ราคา: {price}"[:60]

        carousel_columns.append(
            CarouselColumn(
                thumbnail_image_url=product["image_url"],
                title=title,
                text=text,
                actions=[
                    MessageAction(label="รายละเอียด", text=f"รายละเอียด {product['name']}"),
                    URIAction(label="สั่งซื้อ", uri=product["link"] or "https://example.com")
                ]
            )
        )

    return TemplateSendMessage(
        alt_text=f"ผลการค้นหา: {search_query}",
        template=CarouselTemplate(columns=carousel_columns)
    )


def is_product_related_query(user_message, menu_data):
    """ตรวจสอบว่าข้อความเกี่ยวข้องกับการค้นหาสินค้าหรือไม่"""
    # คำที่แสดงว่าต้องการดูเมนู
    menu_keywords = ["เมนู", "menu", "สินค้า", "ของ", "อาหาร"]
    
    # คำที่แสดงว่าต้องการดูรายละเอียด
    if user_message.startswith("รายละเอียด "):
        return True
    
    # ตรวจสอบคำว่า "เมนู"
    for keyword in menu_keywords:
        if word_similarity(keyword, user_message) > 0.65:
            return True
    
    # ตรวจสอบว่ามีคำเกี่ยวกับราคาหรือไม่
    price_keywords = ["ราคา", "บาท", "ต่ำกว่า", "น้อยกว่า", "สูงกว่า", "มากกว่า", "ไม่เกิน", "เกิน", "ประมาณ"]
    message_lower = user_message.lower()
    has_price_keyword = any(keyword in message_lower for keyword in price_keywords)
    
    if has_price_keyword:
        return True
    
    # ตรวจสอบว่ามีสินค้าที่คล้ายกับที่ผู้ใช้พิมพ์มาหรือไม่
    similar_products = smart_product_search(user_message, menu_data, top_k=1, threshold=0.3)
    if similar_products:
        return True
    
    return False


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text.strip()
    menu_data = fetch_cp_products_from_csv()

    if not menu_data:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ ไม่พบข้อมูลเมนู")
        )
        return

    # ตรวจสอบว่าเป็นคำขอดูเมนูหรือไม่
    if word_similarity("menu", user_message) > 0.65 or word_similarity("เมนู", user_message) > 0.65:
        top_items = menu_data[:10]
        template_message = create_product_carousel(top_items, "เมนูแนะนำ")

        if template_message:
            line_bot_api.reply_message(event.reply_token, template_message)
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ ไม่สามารถแสดงเมนูได้ในขณะนี้")
            )
    
    # ตรวจสอบว่าเป็นคำขอดูรายละเอียดหรือไม่
    elif user_message.startswith("รายละเอียด "):
        product_name = user_message.replace("รายละเอียด ", "").strip()
        matched = next((item for item in menu_data if item["name"].strip().lower() == product_name.lower()), None)

        if matched:
            # ใช้ Ollama สรุปคำอธิบายก่อนแสดงผล
            detail = matched["description"]
            if detail:
                summary = summarize_product_description(detail)
                reply_text = f"📦 {matched['name']}:\n\n{summary}"
            else:
                reply_text = f"📦 {matched['name']}:\nไม่มีรายละเอียดเพิ่มเติม"

            # จำกัดความยาวข้อความไม่เกิน 1000 ตัวอักษร
            if len(reply_text) > 1000:
                reply_text = reply_text[:997] + "..."

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ ไม่พบรายละเอียดของ '{product_name}'")
            )
    
    # ตรวจสอบว่าเป็นการค้นหาสินค้าหรือไม่
    elif is_product_related_query(user_message, menu_data):
        similar_products = smart_product_search(user_message, menu_data, top_k=5, threshold=0.3)

        if similar_products:
            # วิเคราะห์คำค้นหาเพื่อสร้างข้อความตอบกลับ
            query_info = parse_user_query(user_message)
            search_title = user_message
            
            # ปรับข้อความแสดงผลตามเงื่อนไข
            if query_info['max_price']:
                search_title = f"สินค้าราคาไม่เกิน {query_info['max_price']} บาท"
            elif query_info['min_price'] and query_info['max_price']:
                search_title = f"สินค้าราคา {query_info['min_price']}-{query_info['max_price']} บาท"
            elif query_info['min_price']:
                search_title = f"สินค้าราคาตั้งแต่ {query_info['min_price']} บาท"
            
            template_message = create_product_carousel(similar_products, search_title)

            if template_message:
                line_bot_api.reply_message(event.reply_token, template_message)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"❌ ไม่สามารถแสดงผลการค้นหา '{user_message}' ได้")
                )
        else:
            # ใช้ Ollama ตอบกลับพร้อมแนะนำ
            query_info = parse_user_query(user_message)
            context = "ไม่พบสินค้าที่ตรงกับเงื่อนไขที่ต้องการ "
            
            if query_info['max_price']:
                context += f"ราคาไม่เกิน {query_info['max_price']} บาท "
            elif query_info['min_price']:
                context += f"ราคาตั้งแต่ {query_info['min_price']} บาท ขึ้นไป "
            
            context += "สินค้าที่มีในร้าน ได้แก่ ข้าว, น้ำจิ้ม, ซุป"
            
            ollama_response = call_ollama(user_message, context)
            
            suggestion_text = f"{ollama_response}\n\n" \
                              f"💡 ลองใช้คำค้นหาเช่น:\n" \
                              f"• ข้าว\n" \
                              f"• น้ำจิ้ม\n" \
                              f"• ซุป\n" \
                              f"• หรือพิมพ์ 'เมนู' เพื่อดูเมนูทั้งหมด"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=suggestion_text)   
            )
    
    # สำหรับคำถามทั่วไปหรือการสนทนา ใช้ Ollama
    else:
        # สร้าง context จากข้อมูลเมนู (แค่ชื่อสินค้าเพื่อไม่ให้ยาวเกินไป)
        menu_names = [item["name"] for item in menu_data[:20]]  # เอาแค่ 20 รายการ
        context = f"สินค้าในร้าน CP: {', '.join(menu_names)}"
        
        ollama_response = call_ollama(user_message, context)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ollama_response)
        )


if __name__ == "__main__":

    app.run(port=5000)
