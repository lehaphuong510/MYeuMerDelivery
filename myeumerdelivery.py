import streamlit as st
import pandas as pd
import gspread
import requests
import base64
import io
from PIL import Image
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- CẤU HÌNH BẢO MẬT & SESSION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "picker_id" not in st.session_state:
    st.session_state.picker_id = ""

VALID_PASSWORDS = {"0519": "Lê Phương", "PICKER-AN": "An"}

if not st.session_state.authenticated:
    st.markdown("### 🔒 Cổng kiểm soát nội bộ (Trạm Giao Hàng)")
    password = st.text_input("Nhập mã truy cập cá nhân:", type="password")
    
    if st.button("Đăng nhập"):
        if password in VALID_PASSWORDS: 
            st.session_state.authenticated = True
            st.session_state.picker_id = VALID_PASSWORDS[password] 
            st.rerun()
        else:
            st.error("Mã không hợp lệ hoặc đã bị vô hiệu hóa!")
    st.stop()

# --- CẤU HÌNH GIAO DIỆN CHUẨN TONE ---
st.set_page_config(page_title="MYÊU PICKER", layout="centered")

st.markdown("""
<style>
    .main-title {
        color: #C71585;
        text-shadow: 2px 2px 0px #e6d3d3, 4px 4px 5px rgba(0,0,0,0.4);
        text-align: left;
        font-weight: 900;
        font-size: 2.5rem;
        line-height: 1.2;
        margin-bottom: 25px;
    }
    .main-title span { display: block; white-space: nowrap; }
    
    /* CLASS CHỮ TRẮNG THÔNG THƯỜNG */
    .base-text {
        font-size: 1.15rem;
        font-weight: bold;
        color: inherit;
        line-height: 1.8;
    }
    
    /* CLASS HIGHLIGHT MÀU HỒNG - TÍM CHO CHỮ (TO HƠN VÀ ĐẬM HƠN) */
    .highlight-text { 
        background: linear-gradient(90deg, #C71585, #8B008B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900 !important; 
        font-size: 1.25rem !important;
    }
    
    .section-title {
        background: linear-gradient(90deg, #C71585, #8B008B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 1.5rem;
        margin-top: 20px;
        margin-bottom: 15px;
        text-align: left;
    }
    
    div.stButton > button {
        background: linear-gradient(90deg, #C71585, #8B008B) !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        transition: 0.3s;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #8B008B, #C71585) !important;
        box-shadow: 0px 4px 10px rgba(139, 0, 139, 0.4) !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title"><span>MYÊU MERCHANDISE</span><span>DELIVERY</span></div>', unsafe_allow_html=True)
st.caption(f"🏃 Đang trực trạm giao hàng: **{st.session_state.picker_id}**")
st.markdown("---")

# --- KẾT NỐI API & UPLOAD ---
OUTPUT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1zSeYfiaSFJNdXMOZnwG7WsW0b33v-rbt0EruvMS_aA0/edit"
# [QUAN TRỌNG]: DÁN LINK APPS SCRIPT UP HÌNH MỚI TẠO VÀO ĐÂY NHA:
LINK_WEB_APP = "https://script.google.com/macros/s/xxxx/exec" 

@st.cache_resource
def get_gspread_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

client = get_gspread_client()

def upload_image_to_gdrive_script(photo_file, filename):
    try:
        img = Image.open(photo_file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((1024, 1024))
        compressed_io = io.BytesIO()
        img.save(compressed_io, format='JPEG', quality=70)
        compressed_bytes = compressed_io.getvalue()
        
        encoded_image = base64.b64encode(compressed_bytes).decode('utf-8')
        payload = {"fileData": encoded_image, "contentType": "image/jpeg", "filename": filename}
        response = requests.post(LINK_WEB_APP, data=payload)
        return response.text if response.text.startswith("http") else None
    except Exception as e:
        st.error(f"Lỗi nén/up ảnh: {e}")
        return None

# --- LẤY DỮ LIỆU TỪ SHEET ---
try:
    sheet = client.open_by_url(OUTPUT_SHEET_URL).sheet1
    all_records = sheet.get_all_records()
    df_all = pd.DataFrame(all_records)
    if not df_all.empty:
        df_all.columns = df_all.columns.str.strip()
except Exception as e:
    df_all = pd.DataFrame()
    st.error(f"Lỗi kết nối Sheet: {e}")

# --- LOGIC GET ĐƠN & GIAO HÀNG ---
if st.button("Thông tin MYêu nhận Mer", use_container_width=True):
    if df_all.empty:
        st.warning("Sheet Đầu Ra hiện đang trống chưa có data!")
    elif 'Tên' not in df_all.columns or 'Status' not in df_all.columns:
        st.error("⚠️ File Sheet Đầu Ra đang bị thiếu tên cột hoặc sai tên. M check lại Row 1 nha!")
    else:
        df_pending = df_all[df_all['Status'].astype(str).str.strip() != 'Completed']
        
        if df_pending.empty:
            st.success("Tạm thời không có đơn hàng nào chờ giao!")
        else:
            df_pending['Thời Gian'] = pd.to_datetime(df_pending['Thời Gian'])
            df_pending = df_pending.sort_values(by='Thời Gian')
            
            first_row = df_pending.iloc[0]
            target_phone = first_row['ĐT']
            target_order = first_row['Mã đơn hàng']
            target_name = first_row['Tên']
            
            user_items = df_pending[(df_pending['ĐT'] == target_phone) & (df_pending['Mã đơn hàng'] == target_order)]
            row_indices = user_items.index.tolist()
            
            st.session_state.current_user = {
                "name": target_name,
                "order_code": str(target_order),
                "items": user_items.to_dict('records'),
                "row_indices": row_indices
            }

if "current_user" in st.session_state:
    user_data = st.session_state.current_user
    
    with st.container(border=True):
        st.markdown(f"<div class='base-text'>Khách hàng: <span class='highlight-text'>{user_data['name']}</span></div><br>", unsafe_allow_html=True)
        
        for i, item in enumerate(user_data['items']):
            merch = item['Loại Merchandise']
            size = item['Size áo']
            qty = item['SL']
            
            if pd.notna(size) and str(size).strip() != '' and str(size).lower() != 'nan':
                clean_size = str(size).strip()
                if clean_size.lower().startswith('size'):
                    clean_size = clean_size[4:].strip()
                size_html = f" - Size <span class='highlight-text'>{clean_size}</span>"
            else:
                size_html = ""
                
            st.markdown(f"<div class='base-text'>{i+1}. <span class='highlight-text'>{merch}</span>{size_html} - <span class='highlight-text'>{qty}</span> cái</div>", unsafe_allow_html=True)
            st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True) # Khoảng cách các món
    
    st.markdown("---")
    photo = st.file_uploader("Chụp hóa đơn/bằng chứng", type=['png', 'jpg', 'jpeg'])
    
    if st.button("Hoàn Thành Giao Hàng", type="primary"):
        if photo is None:
            st.warning("Bạn quên chụp hình bằng chứng rồi!")
        else:
            with st.spinner("Đang lưu hình và chốt đơn..."):
                suffix = user_data['order_code'][-3:] if len(user_data['order_code']) >= 3 else user_data['order_code']
                file_name = f"Merch_{suffix}.jpg"
                
                img_url = upload_image_to_gdrive_script(photo, file_name)
                
                if img_url:
                    for idx in user_data['row_indices']:
                        sheet_row = idx + 2 
                        sheet.update_cell(sheet_row, 9, "Completed") 
                        sheet.update_cell(sheet_row, 10, img_url)    
                        
                    st.success("✅ Đã hoàn tất giao hàng và ghi nhận lên hệ thống!")
                    del st.session_state.current_user
                    st.rerun() 
                else:
                    st.error("Up hình thất bại, vui lòng thử lại!")

# --- THỐNG KÊ SỐ LƯỢNG ĐÃ GIAO (BẢNG HTML) ---
st.markdown("---")
st.markdown('<div class="section-title">📊 THỐNG KÊ SỐ LƯỢNG ĐÃ GIAO</div>', unsafe_allow_html=True)

if not df_all.empty and 'Loại Merchandise' in df_all.columns:
    df_completed = df_all[df_all['Status'].astype(str).str.strip() == 'Completed']
    
    html_table = "<table style='width: 100%; border-collapse: collapse; font-family: sans-serif; text-align: center; margin-bottom: 20px;'>"
    html_table += "<tr style='border-bottom: 2px solid #8B008B; color: #8B008B; background-color: #f9f9f9;'>"
    html_table += "<th style='text-align: left; padding: 12px;'>Loại Merchandise</th>"
    html_table += "<th style='padding: 12px;'>Đã giao</th></tr>"
    
    merch_list = df_all['Loại Merchandise'].dropna().unique().tolist()
    
    # Ép thứ tự: Áo thun -> Gối -> Package
    def merch_sort_key(m):
        m_lower = str(m).lower()
        if "áo thun" in m_lower: return 1
        elif "gối" in m_lower: return 2
        elif "package" in m_lower: return 3
        else: return 4
        
    merch_list.sort(key=merch_sort_key)
    
    for merch in merch_list:
        merch_df_completed = df_completed[df_completed['Loại Merchandise'] == merch]
        total_delivered = pd.to_numeric(merch_df_completed['SL'], errors='coerce').fillna(0).sum()
        
        merch_df_all = df_all[df_all['Loại Merchandise'] == merch]
        sizes = merch_df_all['Size áo'].dropna().unique() if 'Size áo' in merch_df_all.columns else []
        valid_sizes = [s for s in sizes if str(s).strip() != '' and str(s).lower() != 'nan']
        
        def clean_size_for_sort(sz):
            sz = str(sz).strip()
            if sz.lower().startswith('size'): sz = sz[4:].strip()
            return sz.upper()
            
        size_order = {"S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5}
        valid_sizes.sort(key=lambda x: size_order.get(clean_size_for_sort(x), 99))
        
        size_rows_html = ""
        for raw_size in valid_sizes:
            clean_size = clean_size_for_sort(raw_size)
            size_delivered = pd.to_numeric(merch_df_completed[merch_df_completed['Size áo'] == raw_size]['SL'], errors='coerce').fillna(0).sum()
            
            size_rows_html += f"<tr style='border-bottom: 1px solid #eee;'>"
            size_rows_html += f"<td style='text-align: left; padding: 8px 10px 8px 30px; color: #444; font-size: 0.95rem;'>↳ Size {clean_size}</td>"
            size_rows_html += f"<td style='padding: 8px;'>{int(size_delivered)}</td></tr>"
        
        gradient_style = "padding: 12px; font-weight: bold; background: linear-gradient(90deg, #C71585, #8B008B); -webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        
        html_table += f"<tr style='background-color: #fef5fa; border-top: 1px solid #ddd;'>"
        html_table += f"<td style='text-align: left; {gradient_style}'>{merch}</td>"
        html_table += f"<td style='{gradient_style}'>{int(total_delivered)}</td></tr>"
        
        html_table += size_rows_html

    html_table += "</table>"
    st.markdown(html_table, unsafe_allow_html=True)
else:
    st.info("Chưa có dữ liệu thống kê.")
