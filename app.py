import io
import sqlite3
from datetime import date
import arabic_reshaper
from bidi.algorithm import get_display
import easyocr
import numpy as np
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
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


# --- 2. محرك قراءة الـ PDF البصري الجذرى (OCR Engine) ---
@st.cache_resource
def init_ocr_reader():
    # تحميل قارئ النصوص للغتين العربية والإنجليزية
    return easyocr.Reader(["ar", "en"], gpu=False)


reader = init_ocr_reader()


def process_pdf_with_ocr(pdf_bytes):
    """تحويل الـ PDF لصور وقراءة النصوص حسب إحداثيات الصفوف والأعمدة"""
    try:
        images = convert_from_bytes(pdf_bytes)
    except Exception as e:
        st.error(
            "تأكد من تثبيت مكتبة Poppler على النظام لدعم تحويل PDF إلى صور."
        )
        return None

    all_extracted_rows = []

    for page_idx, img in enumerate(images):
        img_np = np.array(img)

        # استخراج الكلمات مع إحداثياتها: [(bbox, text, prob), ...]
        results = reader.readtext(img_np)

        if not results:
            continue

        # تجميع النصوص بناءً على الإحداثي الرأسي Y (الصفوف) ثم الأفقي X (الأعمدة من اليمين للياسار)
        items = []
        for bbox, text, prob in results:
            if prob < 0.2:  # استبعاد القراءات الضعيفة جداً
                continue

            # حساب مركز الكلمة (Y_center, X_center)
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            x_center = (bbox[0][0] + bbox[1][0]) / 2

            # إصلاح النص العربي المقلوب
            try:
                reshaped = arabic_reshaper.reshape(text)
                clean_text = get_display(reshaped)
            except:
                clean_text = text

            items.append({
                "y": y_center,
                "x": x_center,
                "text": clean_text.strip(),
            })

        # فرز البنود حسب الصفوف (Y)
        items.sort(key=lambda item: item["y"])

        # تقسيم البنود إلى صفوف (الكلمات ذات الإحداثي Y المتقارب تنتمي لنفس الصف)
        rows = []
        current_row = []
        last_y = None
        y_threshold = 18  # المسافة الرأسية لتمييز السطر الجديد

        for item in items:
            if last_y is None or abs(item["y"] - last_y) < y_threshold:
                current_row.append(item)
            else:
                # ترتيب كلمات الصف الحالي من اليمين إلى اليسار (X تنازلي)
                current_row.sort(key=lambda item: item["x"], reverse=True)
                rows.append([it["text"] for it in current_row])
                current_row = [item]
            last_y = item["y"]

        if current_row:
            current_row.sort(key=lambda item: item["x"], reverse=True)
            rows.append([it["text"] for it in current_row])

        all_extracted_rows.extend(rows)

    if all_extracted_rows:
        # توحيد أطوال الأعمدة
        max_cols = max(len(r) for r in all_extracted_rows)
        padded_rows = [r + [""] * (max_cols - len(r)) for r in all_extracted_rows]

        df = pd.DataFrame(padded_rows)
        cols = [f"العمود {i+1}" for i in range(df.shape[1])]
        df.columns = cols
        return df

    return None


# --- 3. واجهة الاستخدام ---
st.title(
    "🏗️ منصة إدارة المشاريع والكميات - شركة العامرية المتحدة للمقاولات"
)

st.subheader("📄 الاستخراج الذكي لجدول الـ BOQ من ملف PDF مباشرة")

uploaded_pdf = st.file_uploader(
    "اختر ملف الـ BOQ بصيغة PDF", type=["pdf"], key="pdf_ocr_uploader"
)

if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.read()

    with st.spinner("جاري المسح البصري الذكي للـ PDF وإعادة ترتيب الجداول..."):
        df_result = process_pdf_with_ocr(pdf_bytes)

    if df_result is not None and not df_result.empty:
        st.success(
            f"تم التعرف البصري على الجدول بنجاح! إجمالي الصفوف المستخرجة:"
            f" {len(df_result)}"
        )
        st.dataframe(df_result, use_container_width=True)
    else:
        st.error(
            "تعذر قراءة الجدول من الملف. تأكد من جودة ملف الـ PDF المرفق."
        )