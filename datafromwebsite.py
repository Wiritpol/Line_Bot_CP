from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import requests

# ฟังก์ชันเช็คว่า URL มีอยู่จริงหรือไม่
def url_exists(url):
    try:
        response = requests.head(url, timeout=5)
        return response.status_code < 400
    except:
        return False

# ตั้งค่า Chrome
chrome_options = Options()
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

driver = webdriver.Chrome(options=chrome_options)

def get_product_details(product_url):
    """เปิดหน้ารายละเอียดสินค้าในแท็บใหม่และดึงข้อมูลเพิ่มเติม"""
    try:
        # เปิดแท็บใหม่
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(product_url)
        time.sleep(2)

        details = {}

        # คำอธิบาย
        try:
            desc_elem = driver.find_element(By.CSS_SELECTOR, ".product-description, .description, [class*=desc]")
            details['description'] = desc_elem.text.strip()
        except:
            details['description'] = 'ไม่พบคำอธิบาย'

        # ราคา
        try:
            price_elem = driver.find_element(By.CSS_SELECTOR, ".price, .product-price, [class*=price]")
            details['price'] = price_elem.text.strip()
        except:
            details['price'] = 'ไม่พบราคา'

        # ปิดแท็บ แล้วกลับไปยังหน้าหลัก
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        return details

    except Exception as e:
        print(f"เกิดข้อผิดพลาดในหน้าสินค้า: {e}")
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return {'description': 'เกิดข้อผิดพลาด', 'price': ''}


def scrape_page(url, page_num):
    """ดึงข้อมูลจากหน้าหนึ่ง - ทั้งชื่อ, รูปภาพ, ลิงก์ และรายละเอียดภายใน"""
    print(f"\n📄 กำลังดึงข้อมูลจากหน้า {page_num}: {url}")
    
    try:
        driver.get(url)
        time.sleep(3)  # รอโหลด

        products_data = []

        # ดึงสินค้าทั้งหมด
        containers = driver.find_elements(By.CSS_SELECTOR, ".product, .item, .card, .product-item, div[class*='product']")
        print(f"🔍 พบสินค้าทั้งหมด: {len(containers)} รายการ")

        for idx, container in enumerate(containers, 1):
            try:
                product_name = ""
                image_url = ""
                product_link = ""

                # ชื่อสินค้า
                name_selectors = ["h1", "h2", "h3", "h4", "h5", ".product-name", ".item-name", ".title", ".name"]
                for sel in name_selectors:
                    try:
                        name_elem = container.find_element(By.CSS_SELECTOR, sel)
                        if name_elem.text.strip():
                            product_name = name_elem.text.strip()
                            break
                    except:
                        continue

                # รูปภาพ
                try:
                    img_elem = container.find_element(By.TAG_NAME, "img")
                    image_url = img_elem.get_attribute("src") or img_elem.get_attribute("data-src")
                except:
                    image_url = ""

                # ลิงก์สินค้า
                try:
                    link_elem = container.find_element(By.CSS_SELECTOR, "a")
                    product_link = link_elem.get_attribute("href")
                except:
                    product_link = ""

                if not product_name or len(product_name) < 4:
                    continue

                # 🧠 ดึงรายละเอียดจากแท็บใหม่
                details = get_product_details(product_link) if product_link else {'description': 'ไม่มีลิงก์', 'price': ''}

                product_data = {
                    'name': product_name,
                    'image': image_url if image_url else 'ไม่พบรูปภาพ',
                    'price': details['price'],
                    'description': details['description'],
                    'url': product_link,
                    'source': f'หน้า {page_num}'
                }

                products_data.append(product_data)
                print(f"✅ [{idx}] {product_name[:50]}...")

            except Exception as e:
                print(f"⚠️ เกิดข้อผิดพลาดกับสินค้าชิ้นที่ {idx}: {e}")
                continue

        return products_data

    except Exception as e:
        print(f"❌ Error scraping page {page_num}: {e}")
        return []



try:
    base_url = "https://shop.cpbrandsite.com/th/category/133840/all-product"
    all_products_data = []
    
    # วิธีที่ 1: ลอง URL patterns ต่างๆ
    url_patterns = [
        f"{base_url}?page={{}}",
        f"{base_url}?p={{}}",
        f"{base_url}/page/{{}}",
        f"{base_url}#page={{}}",
    ]
    
    successful_pattern = None
    
    for pattern in url_patterns:
        test_url = pattern.format(2)  # ทดสอบกับหน้า 2
        print(f"ทดสอบ URL pattern: {test_url}")
        
        if url_exists(test_url):
            successful_pattern = pattern
            print(f"พบ pattern ที่ใช้ได้: {pattern}")
            break
    
    if successful_pattern:
        # ใช้ URL pattern ที่เจอ
        for page in range(1, 3):  # ลองสูงสุด 10 หน้า
            url = successful_pattern.format(page)
            page_products = scrape_page(url, page)
            
            if page_products:
                all_products_data.extend(page_products)
                print(f"หน้า {page}: พบ {len(page_products)} รายการ")
                # แสดงตัวอย่าง 2 รายการแรก
                for i, product in enumerate(page_products[:2], 1):
                    print(f"  {i}. {product['name'][:50]}...")
            else:
                print(f"หน้า {page}: ไม่พบข้อมูลหรือหน้าไม่มีอยู่")
                if page > 2:  # ถ้าหน้า 3+ ไม่มีข้อมูล ให้หยุด
                    break
    
    else:
        # วิธีที่ 2: เริ่มจากหน้าแรกแล้วหาปุ่ม next
        print("ไม่พบ URL pattern ที่รู้จัก ลองใช้วิธีคลิกปุ่ม next")
        
        driver.get(base_url)
        time.sleep(5)
        
        page_num = 1
        while page_num <= 3:
            print(f"\n=== หน้า {page_num} ===")
            
            # ดึงข้อมูลจากหน้าปัจจุบัน
            current_products = []
            
            # หา product containers
            containers = driver.find_elements(By.CSS_SELECTOR, ".product, .item, .card, div[class*='product']")
            
            for container in containers:
                product_data = {}
                
                # หาชื่อสินค้า
                try:
                    name_elem = container.find_element(By.CSS_SELECTOR, "h1, h2, h3, h4, .title, .name, .product-name")
                    product_name = name_elem.text.strip()
                except:
                    product_name = ""
                
                # หารูปภาพ
                try:
                    img_elem = container.find_element(By.TAG_NAME, "img")
                    img_src = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                except:
                    img_src = ""
                
                if product_name:
                    product_data = {
                        'name': product_name,
                        'image': img_src if img_src else 'ไม่พบรูปภาพ',
                    }
                    current_products.append(product_data)
            
            if current_products:
                all_products_data.extend(current_products)
                print(f"พบ {len(current_products)} รายการ")
            
            # หาปุ่ม next
            next_found = False
            next_selectors = [
                "//button[contains(text(), 'ถัดไป')]",
                "//a[contains(text(), 'ถัดไป')]", 
                "//button[contains(text(), 'Next')]",
                "//a[contains(text(), 'Next')]",
                "//button[contains(text(), '>>')]",
                "//a[contains(text(), '>>')]",
                "//*[contains(@class, 'next')]",
                "//*[contains(@class, 'pagination-next')]"
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = driver.find_element(By.XPATH, selector)
                    if next_btn.is_enabled():
                        driver.execute_script("arguments[0].click();", next_btn)
                        time.sleep(3)
                        next_found = True
                        break
                except:
                    continue
            
            if not next_found:
                print("ไม่พบปุ่ม next")
                break
                
            page_num += 1
    
    # แสดงผลลัพธ์และบันทึกไฟล์
    print(f"\n{'='*50}")
    print(f"สรุปผลการดึงข้อมูล")
    print(f"{'='*50}")
    print(f"จำนวนสินค้าทั้งหมด: {len(all_products_data)} รายการ")
    
    if all_products_data:
        print(f"\nตัวอย่างสินค้าที่พบ:")
        for i, product in enumerate(all_products_data[:3], 1):
            print(f"{i:2d}. {product['name'][:60]}...")
            print(f"     รูปภาพ: {product['image'][:80]}...")
            print()
        
        # บันทึกลงไฟล์ format ที่อ่านง่าย
        with open('cp_products_with_images.txt', 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("ข้อมูลสินค้าจากเว็บไซต์ CP Brand\n")
            f.write(f"จำนวนสินค้าทั้งหมด: {len(all_products_data)} รายการ\n")
            f.write("=" * 60 + "\n\n")
            
            for i, product in enumerate(all_products_data, 1):
                f.write(f"รายการที่ {i}\n")
                f.write(f"ชื่อสินค้า: {product['name']}\n")
                f.write(f"รูปภาพ: {product['image']}\n")
                f.write("-" * 40 + "\n\n")
        
        # บันทึกในรูปแบบ CSV สำหรับ Excel
        with open('cp_products.csv', 'w', encoding='utf-8') as f:
            f.write("ลำดับ,ชื่อสินค้า,รูปภาพ\n")
            for i, product in enumerate(all_products_data, 1):
                # ทำความสะอาดข้อมูลสำหรับ CSV
                name = product['name'].replace(',', ';').replace('\n', ' ')
                image = product['image'].replace(',', ';')
                f.write(f"{i},{name},{image}\n")
        
        # CSV
        with open('cp_products_detailed.csv', 'w', encoding='utf-8') as f:
            f.write("ลำดับ,ชื่อสินค้า,ราคา,คำอธิบาย,รูปภาพ,ลิงก์\n")
            for i, product in enumerate(all_products_data, 1):
                name = product['name'].replace(',', ';')
                price = product.get('price', '').replace(',', ';')
                desc = product.get('description', '').replace(',', ';').replace('\n', ' ')
                image = product['image'].replace(',', ';')
                url = product.get('url', '')
                f.write(f"{i},{name},{price},{desc},{image},{url}\n")

        # บันทึกเฉพาะ URL รูปภาพ
        image_urls = [p['image'] for p in all_products_data if p['image'] != 'ไม่พบรูปภาพ']
        with open('image_urls.txt', 'w', encoding='utf-8') as f:
            for url in image_urls:
                f.write(f"{url}\n")
        
        print(f"\n✅ บันทึกข้อมูลเรียบร้อยแล้ว:")
        print(f"   📄 cp_products_with_images.txt - ข้อมูลครบถ้วน")
        print(f"   📊 cp_products.csv - รูปแบบ CSV สำหรับ Excel")
        print(f"   🖼️  image_urls.txt - เฉพาะ URL รูปภาพ ({len(image_urls)} รูป)")
        
    else:
        print("\n❌ ไม่พบข้อมูลสินค้า")
        print("ลองตรวจสอบ:")
        print("1. เว็บไซต์ต้องการ login หรือไม่")
        print("2. มี CAPTCHA หรือ bot protection หรือไม่") 
        print("3. โครงสร้าง HTML ของเว็บไซต์")
        
        # Debug info
        print(f"\nPage Title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # ดูรูปภาพทั้งหมดในหน้า
        all_images = driver.find_elements(By.TAG_NAME, "img")
        print(f"พบรูปภาพทั้งหมด: {len(all_images)} รูป")
        for i, img in enumerate(all_images[:5], 1):
            src = img.get_attribute('src')
            print(f"  {i}. {src}")

except Exception as e:
    print(f"เกิดข้อผิดพลาด: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()
    print("\n🏁 เสร็จสิ้นการทำงาน")