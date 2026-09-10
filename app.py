import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import pyproj

# 1. ตั้งค่าหน้าจอ Web App
st.set_page_config(page_title="ระบบค้นหารายงานและแผนที่โครงการ", layout="wide")
st.title("🗺️ ระบบฐานข้อมูลรายงานฝ่ายปฐพีและธรณีวิทยา")

# 2. ฟังก์ชันดึงข้อมูลจาก Google Sheets (ปรับปรุงระบบแปลงพิกัด)
@st.cache_data(ttl=600)
def load_data(sheet_url):
    csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
    df = pd.read_csv(csv_url)
    
    # ใช้ Transformer ซึ่งเป็นวิธีมาตรฐานและเสถียรที่สุดใน pyproj เวอร์ชันใหม่
    # epsg:32647 = พิกัด UTM Zone 47N (ครอบคลุมไทยส่วนใหญ่)
    # epsg:4326 = พิกัด ละติจูด/ลองจิจูด ปกติ
    from pyproj import Transformer
    transformer = Transformer.from_crs("epsg:32647", "epsg:4326", always_xy=True)
    
    def convert_utm(row):
        # 1. ถ้ามี lat/long อยู่แล้ว ให้ใช้ค่าเดิม
        if pd.notna(row.get('lat')) and pd.notna(row.get('long')):
            return pd.Series([row['lat'], row['long']])
            
        # 2. ถ้าไม่มี lat/long แต่มี x/y ให้แปลงพิกัด
        if pd.notna(row.get('x')) and pd.notna(row.get('y')):
            try:
                # แปลงค่าเผื่อกรณีดึงมาจากชีตแล้วติดลูกน้ำ (Comma) หรือเป็นข้อความ
                x_val = float(str(row['x']).replace(',', '').strip())
                y_val = float(str(row['y']).replace(',', '').strip())
                
                # แปลงพิกัด (จะได้ผลลัพธ์เป็น ลองจิจูด, ละติจูด)
                lon, lat = transformer.transform(x_val, y_val)
                return pd.Series([lat, lon])
            except Exception as e:
                # ถ้าแปลงไม่ได้ (เช่น พิมพ์ตัวอักษรปนมา) ให้ข้ามไป
                pass
                
        # 3. ถ้าไม่มีพิกัดเลย ให้เป็นค่าว่าง
        return pd.Series([None, None])
    
    # สร้างคอลัมน์ lat, long ใหม่โดยเรียกใช้ฟังก์ชันด้านบน
    df[['lat', 'long']] = df.apply(convert_utm, axis=1)
    return df
    
    def convert_utm(row):
        # ถ้าไม่มี lat/long แต่มี x/y ให้แปลงค่า
        if pd.isna(row.get('lat')) or pd.isna(row.get('long')):
            if pd.notna(row.get('x')) and pd.notna(row.get('y')):
                try:
                    lon, lat = proj(row['x'], row['y'], inverse=True)
                    return pd.Series([lat, lon])
                except:
                    pass
        return pd.Series([row.get('lat'), row.get('long')])
    
    df[['lat', 'long']] = df.apply(convert_utm, axis=1)
    return df

# !!! นำลิงก์ Google Sheets ของคุณมาใส่ที่นี่ !!!
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1jGX3XJq3kiSGy-8NrlaNr-q8fdJ9IQJYqTiTHHDlyoI/edit?usp=sharing"

try:
    df = load_data(GOOGLE_SHEET_URL)
    
    # 3. สร้างระบบค้นหา (Sidebar ด้านข้าง)
    st.sidebar.header("🔍 ระบบค้นหาข้อมูล")
    search_proj = st.sidebar.text_input("ชื่อโครงการ/รายงาน:")
    search_prov = st.sidebar.text_input("จังหวัด:")
    search_year = st.sidebar.selectbox("ปี:", ["ทั้งหมด"] + sorted(df['ปี'].dropna().unique().tolist(), reverse=True))
    
    # ประมวลผลการกรองข้อมูลตามที่ผู้ใช้ค้นหา
    filtered_df = df.copy()
    if search_proj:
        filtered_df = filtered_df[filtered_df['โครงการ'].astype(str).str.contains(search_proj, na=False) | 
                                  filtered_df['รายงาน'].astype(str).str.contains(search_proj, na=False)]
    if search_prov:
        filtered_df = filtered_df[filtered_df['จังหวัด'].astype(str).str.contains(search_prov, na=False)]
    if search_year != "ทั้งหมด":
        filtered_df = filtered_df[filtered_df['ปี'] == search_year]
        
    filtered_map = filtered_df.dropna(subset=['lat', 'long'])
    
    # 4. ส่วนแสดงแผนที่ (ใช้ API ของ OpenStreetMap ซึ่งฟรี)
    st.subheader(f"📍 แผนที่แสดงตำแหน่งโครงการ ({len(filtered_map)} โครงการที่มีพิกัด)")
    if not filtered_map.empty:
        # หาจุดกึ่งกลางของแผนที่
        center_lat = filtered_map['lat'].mean()
        center_lon = filtered_map['long'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
        
       # ปักหมุดลงบนแผนที่
        for idx, row in filtered_map.iterrows():
            # จัดการข้อมูลที่เป็น NaN (ค่าว่าง) ให้แสดงเป็นขีด (-) แทน
            proj_name = row.get('โครงการ', '-') if pd.notna(row.get('โครงการ')) else '-'
            prov_name = row.get('จังหวัด', '-') if pd.notna(row.get('จังหวัด')) else '-'
            
            # จัดการปีให้แสดงเป็นตัวเลขจำนวนเต็ม (ลบจุดทศนิยม .0 ออก)
            year_val = str(int(row.get('ปี'))) if pd.notna(row.get('ปี')) else '-'
            
            soil_type = row.get('ดินที่พบ', '-') if pd.notna(row.get('ดินที่พบ')) else '-'
            rock_type = row.get('หินที่พบ', '-') if pd.notna(row.get('หินที่พบ')) else '-'
            
            # เพิ่มข้อมูล ดิน และ หิน ลงใน Popup
            popup_text = f"""
            <div style="font-family: Tahoma, sans-serif; min-width: 200px;">
                <b>โครงการ:</b> {proj_name}<br>
                <b>จังหวัด:</b> {prov_name}<br>
                <b>ปี:</b> {year_val}<br>
                <b>ดินที่พบ:</b> {soil_type}<br>
                <b>หินที่พบ:</b> {rock_type}
            </div>
            """
            
            folium.Marker(
                [row['lat'], row['long']], 
                popup=folium.Popup(popup_text, max_width=400), # ขยาย max_width เผื่อข้อความยาว
                tooltip=str(proj_name),
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
    else:
        st.info("ระบุพิกัด (x,y หรือ lat,long) ในตารางเพื่อแสดงผลบนแผนที่")
        
    # 5. แสดงตารางรายงาน
    st.subheader("📑 ข้อมูลรายละเอียดโครงการ")
    st.dataframe(filtered_df)

except Exception as e:
    st.error("ไม่สามารถโหลดข้อมูลได้ กรุณาตรวจสอบ Link Google Sheets ว่าเปิดสิทธิ์แชร์แล้วหรือไม่")
    st.write(e)
