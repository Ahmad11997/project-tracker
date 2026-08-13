import io
import sqlite3
from datetime import date
import arabic_reshaper
from bidi.algorithm import get_display
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract
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


# --- 2. محرك القراءة البصرية الجذرية (PyTesseract OCR) ---
def process_pdf_ocr(pdf_bytes):
    """تحويل صفحات الـ PDF إلى صور ثم قراءة النصوص هندسياً بناءً على إحداثيات الصفحة"""
    try:
        images = convert_from_bytes(pdf_bytes)
    except Exception as e:
        st.error(
            "حدث خطأ أثناء تحويل الـ PDF لصور. تأكد من إدراج poppler-utils في"
            " packages.txt"
        )
        return None

    all_rows = []

    for img in images:
        # استخراج البيانات الهيكلية للكلمات مع الإحداثيات البصرية
        try:
            data = pytesseract.image_to_data(
                img, lang="ara+eng", output_type=pytesseract.Output.DATAFRAME
            )
        except Exception as e:
            st.error(
                "تعذر تشغيل محرك Tesseract. تأكد من إضافة tesseract-ocr إلى"
                " packages.txt"
            )
            return None

        # فلترة القيم الفارغة والنصوص الوهمية
        data = data[data.text.notnull() & (data.text.str.strip() != "")]

        if data.empty:
            continue

        # تجميع الكلمات القريبة رأسياً في نفس الصف (Line Grouping)
        data["line_group"] = (data["top"] / 16).astype(int)

        lines = []
        for _, group in data.groupby("line_group"):
            # فرز الكلمات داخل السطر نفسه من اليمين إلى اليسار (Left تنازلي)
            sorted_words = group.sort_values(by="left", ascending=False)

            row_text = []
            for text in sorted_words["text"]:
                try:
                    reshaped = arabic_reshaper.reshape(str(text))
                    clean_txt = get_display(reshaped)
                except:
                    clean_txt = str(text)
                row_text.append(clean_txt)

            if row_text:
                lines.append(row_text)

        all_rows.extend(lines)

    if all_rows:
        # توحيد عدد الأعمدة لضمان العرض السليم داخل الجدول
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
    "اختر ملف الـ BOQ بصيغة PDF", type=["pdf"], key="pdf_ocr_uploader"
)

if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.read()

    with st.spinner(
        "جاري المسح البصري للـ PDF وإعادة ترتيب الجداول والكلمات..."
    ):
        df_result = process_pdf_ocr(pdf_bytes)

    if df_result is not None and not df_result.empty:
        st.success(
            f"تم استخراج الجدول بنجاح! إجمالي الصفوف: {len(df_result)}"
        )
        st.dataframe(df_result, use_container_width=True)
    else:
        st.error(
            "لم يتم العثور على جداول قابلة للقراءة في هذا الملف أو الجودة غير"
            " كافية."
        )