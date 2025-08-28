import pandas as pd
import re

# อ่านไฟล์ CSV
df = pd.read_csv('cp_products_detailed.csv')

# ลบแถวที่ซ้ำกัน (ไม่รวมแถวแรกที่เหมือนกัน)
df_no_duplicates = df.drop_duplicates()

# แสดงข้อมูลที่ลบซ้ำแล้ว
print("ข้อมูลหลังจากลบแถวซ้ำ:")
print(df_no_duplicates)

# บันทึกไฟล์ CSV ใหม่หลังจากลบแถวซ้ำ
df_no_duplicates.to_csv('cp_products_detailed.csv', index=False)

print("\nบันทึกข้อมูลที่ลบแถวซ้ำลงใน 'cp_products_detailed.csv'")




def split_prices(price_str):
    if pd.isna(price_str):
        return pd.Series([None, None])
    
    # แก้ ; ให้เป็น ,
    price_str = price_str.replace(";", ",")
    
    # ดึงเฉพาะตัวเลขจากสตริง
    prices = re.findall(r"[\d,]+\.\d{2}", price_str)
    
    # แปลง string -> float (เอา , ออกก่อน)
    prices = [float(p.replace(",", "")) for p in prices]
    
    if len(prices) == 2:
        return pd.Series(prices)  # [ราคาลดแล้ว, ราคาปกติ]
    elif len(prices) == 1:
        return pd.Series([None, prices[0]])  # ไม่มีราคาลด
    else:
        return pd.Series([None, None])

# แยกราคาออกมาเป็นตัวเลข
df[["ราคาลดแล้ว_num", "ราคาปกติ_num"]] = df["ราคา"].apply(split_prices)

# ฟอร์แมตให้มี ฿ นำหน้า (คอลัมน์สำหรับแสดงผล)
df["ราคาลดแล้ว"] = df["ราคาลดแล้ว_num"].apply(lambda x: f"฿ {x:,.2f}" if pd.notna(x) else None)
df["ราคาปกติ"] = df["ราคาปกติ_num"].apply(lambda x: f"฿ {x:,.2f}" if pd.notna(x) else None)

# คำนวณเปอร์เซ็นต์ลด
df["ส่วนลด (%)"] = ((df["ราคาปกติ_num"] - df["ราคาลดแล้ว_num"]) / df["ราคาปกติ_num"] * 100).round(2)

# ถ้าไม่มีราคาลดแล้ว ให้ส่วนลดเป็น 0
df.loc[df["ราคาลดแล้ว_num"].isna(), "ส่วนลด (%)"] = 0

# ลบคอลัมน์เลขดิบออกถ้าไม่อยากเก็บ
df = df.drop(columns=["ราคาลดแล้ว_num", "ราคาปกติ_num"])

# บันทึกออก
df.to_csv("cp_products_detailed_new.csv", index=False, encoding="utf-8-sig")
