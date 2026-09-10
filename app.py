import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import pyproj

# 1. ตั้งค่าหน้าจอ Web App
st.set_page_config(page_title="ระบบค้นหารายงานและแผนที่โครงการ", layout="wide")
st.title("🗺️ ระบบฐานข้อมูลรายงานฝ่ายปฐพีและธรณีวิทยา")

# 2. ฟังก์ชันดึงข้อมูลจาก Google Sheets (อัปเดตอัตโนมัติเมื่อข้อมูลเปลี่ยน)
@st.cache_data(ttl=600) # Cache ข้อมูล 10 นาที เพื่อไม่ให้โหลดซ้ำบ่อยเกินไป
def load_data(sheet_url):
    # แปลง Link ปกติ เป็น Link สำหรับดาวน์โหลด CSV
    csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
    df = pd.read_csv(csv_url)
    
    # ระบบแปลงพิกัด UTM (x, y) เป็น Lat/Long 
    # (ใช้ Zone 47N ซึ่งครอบคลุมพื้นที่ส่วนใหญ่ของไทย)
    proj = pyproj.Proj(proj='utm', zone=47, ellps='WGS84', datum='WGS84')
    
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
            popup_text = f"""
            <b>โครงการ:</b> {row.get('โครงการ', '-')}<br>
            <b>จังหวัด:</b> {row.get('จังหวัด', '-')}<br>
            <b>ปี:</b> {row.get('ปี', '-')}
            """
            folium.Marker(
                [row['lat'], row['long']], 
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=str(row.get('โครงการ', 'คลิกดูข้อมูล')),
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
            
        st_folium(m, width=1000, height=500)
    else:
        st.info("ระบุพิกัด (x,y หรือ lat,long) ในตารางเพื่อแสดงผลบนแผนที่")
        
    # 5. แสดงตารางรายงาน
    st.subheader("📑 ข้อมูลรายละเอียดโครงการ")
    st.dataframe(filtered_df)

except Exception as e:
    st.error("ไม่สามารถโหลดข้อมูลได้ กรุณาตรวจสอบ Link Google Sheets ว่าเปิดสิทธิ์แชร์แล้วหรือไม่")
    st.write(e)