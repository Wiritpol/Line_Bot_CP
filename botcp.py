from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,URIAction,
    TemplateSendMessage, CarouselTemplate, CarouselColumn, MessageAction
)
from sentence_transformers import SentenceTransformer, util
import csv

app = Flask(__name__)

# LINE Credentials
CHANNEL_SECRET = 'xxx'
CHANNEL_ACCESS_TOKEN = 'xxx'

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

def extract_current_price(price_string):
    prices = price_string.split("฿")  
    if len(prices) >= 2:
        current_price = "฿" + prices[1].strip()  
        return current_price
    return price_string  


def fetch_cp_products_from_csv(csv_path="cp_products_detailed.csv"):
    products = []
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row.get("ชื่อสินค้า")
                image = row.get("รูปภาพ")
                price = row.get("ราคา")
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


def find_similar_products(user_query, menu_items, top_k=5, threshold=0.3):
    if not menu_items:
        return []

    similarities = []
    for item in menu_items:
        score = word_similarity(user_query.lower(), item["name"].lower())
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


def create_product_carousel(products, search_query):
    if not products:
        return None

    carousel_columns = []
    for product in products:
        title = product["name"][:40]
        current_price = extract_current_price(product["price"])
        text = f"ราคา: {current_price}"[:60]

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

    # คำว่า "เมนู"
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
    elif user_message.startswith("รายละเอียด "):
        product_name = user_message.replace("รายละเอียด ", "").strip()
        matched = next((item for item in menu_data if item["name"].strip().lower() == product_name.lower()), None)


        if matched:
            detail = matched["description"] or "ไม่มีรายละเอียดเพิ่มเติม"
            reply_text = f"📦 {matched['name']}:\n{detail.strip()[:1000]}"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_text)
            )
        else:
            line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"❌ ไม่พบรายละเอียดของ '{product_name}'")
        )

    else:
        similar_products = find_similar_products(user_message, menu_data, top_k=5, threshold=0.4)

        if similar_products:
            template_message = create_product_carousel(similar_products, user_message)

            if template_message:
                line_bot_api.reply_message(event.reply_token, template_message)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"❌ ไม่สามารถแสดงผลการค้นหา '{user_message}' ได้")
                )
        else:
            suggestion_text = f"❌ ไม่พบสินค้าที่เกี่ยวข้องกับ '{user_message}'\n\n" \
                              f"💡 ลองใช้คำค้นหาเช่น:\n" \
                              f"• ข้าว\n" \
                              f"• น้ำจิ้ม\n" \
                              f"• ซุป\n" \
                              f"• ของหวาน\n" \
                              f"• หรือพิมพ์ 'เมนู' เพื่อดูเมนูทั้งหมด"

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=suggestion_text)   
            )
    

if __name__ == "__main__":
    app.run(port=5000)

