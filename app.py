import io
import arabic_reshaper
from bidi.algorithm import get_display
import pdfplumber
import pandas as pd
import streamlit as st

# --- 1. إعداد الصفحة والاتجاه RTL ---
st.set_page_config(
    page_title="شركة العامرية المتحدة للمقاولات - إدارة المشاريع",
    layout="wide",
    page_icon="🏗️",
)

st.markdown(
    """
    <style>
    html, body, [class*="css"], div, h1, h2, h3, h4, h5, h6, p {
        direction: rtl !important;
        text-align: right !important;
    }
    .stSelectbox, .stTextInput, .stNumberInput, .stDateInput, .stFileUploader {
        direction: rtl !important;
        text-align: right !important;
    }
    .stDataFrame {
        direction: rtl !important;
    }
    .stButton>button {
        background-color: #2ecc71 !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 6px !important;
        width: 100%;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- 2. دالة معالجة واستخراج الجداول وإصلاح النصوص المعكوسة ---
def fix_arabic_text(text):
    if not text:
        return ""
    text_str = str(text).strip()
    try:
        # إعادة تشكيل وترتيب النص العربي المعكوس
        reshaped = arabic_reshaper.reshape(text_str)
        return get_display(reshaped)
    except:
        return text_str


def extract_tables_from_pdf(pdf_file):
    all_rows = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # استخراج الجداول مباشرة من الصفحة
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # تنظيف وتعديل كل خلية في الصف
                    clean_row = [fix_arabic_text(cell) for cell in row]
                    # تجاهل الصفوف الفارغة تماماً
                    if any(clean_row):
                        all_rows.append(clean_row)

    if all_rows:
        # توحيد أطوال الصفوف
        max_cols = max(len(r) for r in all_rows)
        padded_rows = [
            r + [""] * (max_cols - len(r)) for r in all_rows
        ]

        df = pd.DataFrame(padded_rows)
        df.columns = [f"العمود {i+1}" for i in range(df.shape[1])]
        return df

    return None


# --- 3. واجهة المستخدم والتطبيق ---
st.title("🏗️ شركة العامرية المتحدة للمقاولات")
st.caption("نظام إدارة المشاريع واستخراج كميات BOQ")

st.subheader("📄 الاستخراج الذكي لجدول الـ BOQ من ملف PDF مباشرة")

uploaded_pdf = st.file_uploader(
    "اختر ملف الـ BOQ بصيغة PDF", type=["pdf"], key="pdf_boq_uploader"
)

if uploaded_pdf is not None:
    with st.spinner("جاري قراءة واستخراج الجداول من ملف الـ PDF..."):
        df_result = extract_tables_from_pdf(uploaded_pdf)

    if df_result is not None and not df_result.empty:
        st.success(
            f"تم استخراج الجدول بنجاح! إجمالي الصفوف: {len(df_result)}"
        )
        st.dataframe(df_result, use_container_width=True)
    else:
        st.error(
            "تعذر استخراج جداول من هذا الملف. تأكد من أن الملف يحتوي على"
            " جداول محددة."
        )