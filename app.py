import streamlit as st
import pandas as pd
import numpy as np

# إعداد الصفحة لتكون واسعة وتدعم الكتابة من اليمين لليسار
st.set_page_config(layout="wide", page_title="منصة إدارة المشاريع")

# إضافة نمط CSS مخصص لتحسين مظهر الجدول والواجهة
st.markdown("""
    <style>
    /* تنسيق النص ليكون من اليمين لليسار */
    .rtl-text {
        direction: rtl;
        text-align: right;
    }
    
    /* تنسيق الجدول */
    .stDataFrame {
        direction: ltr !important; /* جداول بايثون تبقى لليسار لسهولة قراءة الأرقام */
    }
    .stDataFrame table {
        border-collapse: separate !important;
        border-spacing: 0;
        border: 1px solid #444;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* لون خلفية العناوين */
    .stDataFrame thead tr th {
        background-color: #1e1e1e !important;
        color: #fff !important;
        font-weight: bold !important;
        border-bottom: 2px solid #555 !important;
    }
    
    /* لون خلفية الصفوف الزوجية */
    .stDataFrame tbody tr:nth-child(even) {
        background-color: #2a2a2a !important;
    }
    
    /* لون خلفية الصفوف الفردية */
    .stDataFrame tbody tr:nth-child(odd) {
        background-color: #333 !important;
    }
    
    /* منطقة حفظ البيانات */
    .save-section {
        background-color: #1f1f1f;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #333;
        margin-top: 30px;
    }
    
    /* زر الحفظ الأخضر */
    .stButton>button {
        background-color: #2ecc71;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        border: none;
        padding: 10px 20px;
    }
    .stButton>button:hover {
        background-color: #27ae60;
        color: white;
    }
    
    </style>
""", unsafe_allow_html=True)

# ترويسة التطبيق
st.title("🏗️ منصة إدارة المشاريع والكميات")
st.markdown("---")

# --- محاكاة البيانات المستخرجة (بتنسيق صحيح) ---
st.subheader("📋 معاينة بيانات جدول الكميات المستخرجة")

# بيانات الجدول مع تصحيح النصوص والترتيب
data = {
    "م": [98, 99, 100, 101, 102, 103, 104, 105, 106, 107],
    "الوصف": [
        "توريد وتركيب أنابيب خرسانية قطر 1000 ملم، شاملة الحفر والردم وصب الخرسانة",
        "توريد وتركيب أنابيب خرسانية قطر 1200 ملم، شاملة الحفر والردم وصب الخرسانة",
        "توريد وتركيب أنابيب خرسانية قطر 1400 ملم، شاملة الحفر والردم وصب الخرسانة",
        "", # صف فارغ
        "توريد وتركيب صمامات بوابة قطر 400 ملم، شاملة غرف الصمامات والغطاء",
        "توريد وتركيب صمامات بوابة قطر 600 ملم، شاملة غرف الصمامات والغطاء",
        "", # صف فارغ
        "أعمال رصف أسفلت سمك 5 سم، شاملة الطبقة الرابطة",
        "", # بيانات ناقصة
        ""  # بيانات ناقصة
    ],
    "الوحدة": ["م.ط.", "م.ط.", "م.ط.", "", "عدد", "عدد", "", "م2", "", ""],
    "الكمية": ["11,000.00", "14,200.00", "16,700.00", "", "156,600.00", "177,000.00", "", "710,000.00", "", ""],
    "سعر الوحدة": ["110.00", "142.00", "167.00", "", "1,566.00", "1,770.00", "", "142.00", "", ""],
    "السعر الإجمالي": ["1,210,000.00", "2,016,400.00", "2,788,900.00", "", "245,235,600.00", "313,290,000.00", "", "100,820,000.00", "", ""]
}

df = pd.DataFrame(data)

# تعويض القيم الفارغة لتبدو أفضل
df = df.replace("", np.nan)

# استخدام الأعمدة المخصصة لتوسيع الجدول وتسهيل القراءة
cols_to_show = ["م", "الوصف", "الوحدة", "الكمية", "سعر الوحدة", "السعر الإجمالي"]

st.dataframe(df[cols_to_show], use_container_width=True)

# --- منطقة حفظ البيانات المنظمة ---
st.markdown("<div class='save-sectionrtl-text'>", unsafe_allow_html=True)
st.markdown("<h3>💾 حفظ البيانات المستخرجة في قاعدة البيانات</h3>", unsafe_allow_html=True)
st.info("💡 الخطوة التالية: حدد الأعمدة المناسبة من الجدول لتسكينها مباشرة في قاعدة البيانات:")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.selectbox("📌 كود البند / الرقم", df.columns, index=0)
with col2:
    st.selectbox("📝 وصف البند", df.columns, index=1)
with col3:
    st.selectbox("📏 الوحدة", df.columns, index=2)
with col4:
    st.selectbox("🔢 الكمية", df.columns, index=3)

# أزرار الإجراءات
st.markdown("---")
btn_col1, btn_col2 = st.columns([1, 5])
with btn_col1:
    st.button("✅ حفظ البيانات")
with btn_col2:
    st.button("❌ إلغاء", type="secondary")
    
st.markdown("</div>", unsafe_allow_html=True)