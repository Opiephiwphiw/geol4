import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from pyproj import Transformer

# 1. ตั้งค่าหน้าจอ Web App
st.set_page_config(page_title="ระบบค้นหารายงานและแผนที่โครงการ", layout="wide")
st.title("🗺️ ระบบฐานข้อมูลรายงานฝ่ายปฐพีและธรณีวิทยา")

# 2. ฟังก์ชันดึงข้อมูลจาก Google Sheets
@st.cache_data(ttl=600)
def load_data(sheet_url):
    csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
    df = pd.read_csv(csv_url)
    
    # ระบบแปลงพิกัด UTM Zone 47N เป็น Lat/Long
    transformer = Transformer.from_crs("epsg:32647", "epsg:4326", always_xy=True)
    
    def convert_utm(row):
        if pd.notna(row.get('lat')) and pd.notna(row.get('long')):
            return pd.Series([row['lat'], row['long']])
            
        if pd.notna(row.get('x')) and pd.notna(row.get('y')):
            try:
                x_val = float(str(row['x']).replace(',', '').strip())
                y_val = float(str(row['y']).replace(',', '').strip())
                lon, lat = transformer.transform(x_val, y_val)
                return pd.Series([lat, lon])
            except Exception:
                pass
                
        return pd.Series([None, None])
    
    df[['lat', 'long']] = df.apply(convert_utm, axis=1)
    return df

# !!! ใส่ Link Google Sheets ของคุณที่นี่ !!!
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1jGX3XJq3kiSGy-8NrlaNr-q8fdJ9IQJYqTiTHHDlyoI/edit?usp=sharing"

try:
    df = load_data(GOOGLE_SHEET_URL)
    
    # 3. ระบบค้นหา (Sidebar)
    st.sidebar.header("🔍 ระบบค้นหาข้อมูล")
    
    # เพิ่ม key="btn_refresh"
    if st.sidebar.button("🔄 อัปเดตข้อมูลสดจาก Google Sheets", key="btn_refresh"):
        st.cache_data.clear()
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()
            
    # เพิ่ม key แยกเฉพาะให้ช่องค้นหาทุกช่อง
    search_proj = st.sidebar.text_input("ชื่อโครงการ/รายงาน:", key="input_search_proj")
    search_prov = st.sidebar.text_input("จังหวัด:", key="input_search_prov")
    
    # รายการปีสำหรับเลือก
    year_list = ["ทั้งหมด"]
    if 'ปี' in df.columns:
        valid_years = df['ปี'].dropna().unique().tolist()
        formatted_years = []
        for y in valid_years:
            try:
                formatted_years.append(str(int(float(str(y).replace(',', '').strip()))))
            except:
                formatted_years.append(str(y).strip())
        year_list += sorted(list(set(formatted_years)), reverse=True)
        
    search_year = st.sidebar.selectbox("ปี:", year_list, key="select_search_year")
    
    # กรองข้อมูล
    filtered_df = df.copy()
    if search_proj:
        filtered_df = filtered_df[filtered_df['โครงการ'].astype(str).str.contains(search_proj, na=False) | 
                                  filtered_df['รายงาน'].astype(str).str.contains(search_proj, na=False)]
    if search_prov:
        filtered_df = filtered_df[filtered_df['จังหวัด'].astype(str).str.contains(search_prov, na=False)]
    if search_year != "ทั้งหมด":
        filtered_df = filtered_df[filtered_df['ปี'].astype(str).str.contains(search_year, na=False)]
        
    filtered_map = filtered_df.dropna(subset=['lat', 'long'])
    
    # 4. ส่วนแสดงแผนที่
    st.subheader(f"📍 แผนที่แสดงตำแหน่งโครงการ ({len(filtered_map)} โครงการที่มีพิกัด)")
    if not filtered_map.empty:
        center_lat = filtered_map['lat'].mean()
        center_lon = filtered_map['long'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
        
        for idx, row in filtered_map.iterrows():
            proj_name = str(row['โครงการ']).strip() if pd.notna(row.get('โครงการ')) else '-'
            report_name = str(row['รายงาน']).strip() if pd.notna(row.get('รายงาน')) else '-'
            prov_name = str(row['จังหวัด']).strip() if pd.notna(row.get('จังหวัด')) else '-'
            soil_type = str(row['ดินที่พบ']).strip() if pd.notna(row.get('ดินที่พบ')) else '-'
            rock_type = str(row['หินที่พบ']).strip() if pd.notna(row.get('หินที่พบ')) else '-'
            
            raw_year = row.get('ปี')
            if pd.notna(raw_year) and str(raw_year).strip() != '':
                try:
                    year_val = str(int(float(str(raw_year).replace(',', '').strip())))
                except:
                    year_val = str(raw_year).strip()
            else:
                year_val = '-'
            
            popup_html = f"""
            <div style="font-family: 'Tahoma', sans-serif; font-size: 13px; min-width: 220px; line-height: 1.5;">
                <b>โครงการ:</b> {proj_name}<br>
                <b>รายงาน:</b> {report_name}<br>
                <b>จังหวัด:</b> {prov_name}<br>
                <b>ปี:</b> {year_val}<br>
                <b>ดินที่พบ:</b> {soil_type}<br>
                <b>หินที่พบ:</b> {rock_type}
            </div>
            """
            
            folium.Marker(
                location=[row['lat'], row['long']], 
                popup=folium.Popup(popup_html, max_width=350),
                tooltip=proj_name,
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
            
        st_folium(m, width=1000, height=500)
    else:
        st.info("ไม่พบข้อมูลพิกัดโครงการที่ค้นหา")
        
    # 5. แสดงตารางข้อมูล
    st.subheader("📑 ข้อมูลรายละเอียดโครงการ")
    st.dataframe(filtered_df)

except Exception as e:
    st.error("ไม่สามารถดึงข้อมูลได้ กรุณาตรวจสอบการเปิดสิทธิ์แชร์ใน Google Sheets")
    st.write("รายละเอียด Error:", e)
