import sqlite3
from datetime import date
import arabic_reshaper
from bidi.algorithm import get_display
import pandas as pd
import pdfplumber
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
    /* تطبيق اتجاه اليمين لليسار على جميع النصوص والواجهة */
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


# --- 2. محرك قاعدة البيانات ---
class ProgressTrackerDB:

    def __init__(self, db_name="project_progress.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE,
                client_name TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS boq_master (
                boq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                boq_code TEXT,
                description TEXT,
                unit TEXT,
                contract_qty REAL,
                unit_rate REAL,
                FOREIGN KEY (project_id) REFERENCES projects (project_id),
                UNIQUE(project_id, boq_code)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wir_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                wir_id TEXT,
                wir_date TEXT,
                boq_code TEXT,
                location TEXT,
                approved_qty REAL,
                status TEXT,
                created_by TEXT,
                FOREIGN KEY (project_id) REFERENCES projects (project_id)
            )
        """)
        self.conn.commit()

    def add_project(self, name, client):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO projects (project_name, client_name, created_at)"
                " VALUES (?, ?, ?)",
                (name, client, str(date.today())),
            )
            self.conn.commit()
            return True, "تم إضافة المشروع بنجاح!"
        except sqlite3.IntegrityError:
            return False, "اسم المشروع موجود بالفعل."

    def get_projects(self):
        return pd.read_sql_query("SELECT * FROM projects", self.conn)

    def add_boq_item(self, project_id, code, desc, unit, qty, rate):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO boq_master (project_id, boq_code, description, unit, contract_qty, unit_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (project_id, code, desc, unit, qty, rate),
        )
        self.conn.commit()

    def record_wir(
        self,
        project_id,
        wir_id,
        date_str,
        boq_code,
        location,
        approved_qty,
        status,
        user_name,
    ):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO wir_log (project_id, wir_id, wir_date, boq_code, location, approved_qty, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                project_id,
                wir_id,
                date_str,
                boq_code,
                location,
                approved_qty,
                status,
                user_name,
            ),
        )
        self.conn.commit()
        return True, "تم تسجيل الـ WIR بنجاح."

    def get_boq_summary(self, project_id, boq_code=None):
        query = """
            SELECT 
                b.boq_code,
                b.description,
                b.unit,
                b.contract_qty,
                b.unit_rate,
                (b.contract_qty * b.unit_rate) as total_budget,
                COALESCE(SUM(w.approved_qty), 0) as cum_qty,
                (b.contract_qty - COALESCE(SUM(w.approved_qty), 0)) as remaining_qty,
                (COALESCE(SUM(w.approved_qty), 0) / b.contract_qty) * 100 as physical_progress_pct,
                (COALESCE(SUM(w.approved_qty), 0) * b.unit_rate) as earned_value
            FROM boq_master b
            LEFT JOIN wir_log w ON b.boq_code = w.boq_code AND b.project_id = w.project_id
            WHERE b.project_id = ?
        """
        if boq_code:
            query += " AND b.boq_code = ? GROUP BY b.boq_code"
            df = pd.read_sql_query(
                query, self.conn, params=(project_id, boq_code)
            )
            return df.to_dict("records")[0] if not df.empty else None
        else:
            query += " GROUP BY b.boq_code"
            return pd.read_sql_query(query, self.conn, params=(project_id,))


# --- 3. معالجة النصوص العربية المقلوبة واستخراج PDF ---
def fix_arabic_text(text):
    if not text or str(text).strip() in ["None", ""]:
        return ""
    text_str = str(text).strip()
    try:
        reshaped_text = arabic_reshaper.reshape(text_str)
        return get_display(reshaped_text)
    except Exception:
        return text_str


def extract_boq_from_pdf(pdf_file):
    all_rows = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if table:
                    for row in table:
                        cleaned_row = [fix_arabic_text(cell) for cell in row]
                        if any(cleaned_row):
                            all_rows.append(cleaned_row)

    if all_rows:
        raw_df = pd.DataFrame(all_rows)
        headers = [fix_arabic_text(col) for col in raw_df.iloc[0]]
        final_df = raw_df[1:].copy()
        final_df.columns = [
            f"العمود {i+1}: {h}" if h else f"العمود {i+1}"
            for i, h in enumerate(headers)
        ]
        return final_df.reset_index(drop=True)
    return None


# --- 4. واجهة المستخدم ---
db = ProgressTrackerDB()

st.title(
    "🏗️ منصة إدارة المشاريع والكميات - شركة العامرية المتحدة للمقاولات"
)

# الشريط الجانبي
st.sidebar.title("👨‍💼 تطوير وإعداد")
st.sidebar.markdown("**المهندس:** أحمد السيد")
st.sidebar.markdown("📱 **تليفون / واتساب:** `0546226304`")
st.sidebar.markdown("📧 **البريد:** `ahmadalsayed9797@gmail.com`")
st.sidebar.divider()

st.sidebar.title("👤 تسجيل الدخول والمشروع")
user_name = st.sidebar.text_input(
    "اسم المستخدم / المهندس:", value="م. أحمد السيد"
)

projects_df = db.get_projects()

if not projects_df.empty:
    project_options = dict(
        zip(projects_df["project_name"], projects_df["project_id"])
    )
    selected_project_name = st.sidebar.selectbox(
        "📂 اختر المشروع الحالي:", list(project_options.keys())
    )
    selected_project_id = project_options[selected_project_name]
else:
    st.sidebar.warning("يرجى إضافة مشروع جديد أولاً.")
    selected_project_id = None

# التبويبات الرئيسية
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 تقرير المشروع الحسابي",
    "📄 قراءة BOQ من PDF",
    "⚙️ إعدادات BOQ اليدوية",
    "➕ إدارة المشاريع",
])

# تبويب قراءة PDF
with tab2:
    if selected_project_id:
        st.subheader(
            "📄 قراءة واستخراج جميع بنود الـ BOQ من ملف PDF لـ"
            f" ({selected_project_name})"
        )
        pdf_file = st.file_uploader(
            "اختر ملف الـ BOQ بصيغة PDF", type=["pdf"], key="boq_pdf_uploader"
        )

        if pdf_file is not None:
            with st.spinner("جاري قراءة وتصحيح النصوص العربية من الملف..."):
                extracted_df = extract_boq_from_pdf(pdf_file)

            if extracted_df is not None and not extracted_df.empty:
                st.success(
                    f"تم استخراج وتعديل النصوص بنجاح! إجمالي البنود:"
                    f" {len(extracted_df)} بند."
                )
                st.markdown("### 📋 معاينة البيانات المستخرجة:")
                st.dataframe(extracted_df, use_container_width=True)

                st.divider()
                st.markdown(
                    "### 💾 ربط وتسكين الأعمدة في قاعدة بيانات المشروع"
                )

                cols = list(extracted_df.columns)
                col1, col2, col3 = st.columns(3)
                col4, col5, _ = st.columns(3)

                with col1:
                    col_code = st.selectbox("كود البند / الرقم:", cols, index=0)
                with col2:
                    col_desc = st.selectbox(
                        "وصف البند:", cols, index=min(1, len(cols) - 1)
                    )
                with col3:
                    col_unit = st.selectbox(
                        "الوحدة:", cols, index=min(2, len(cols) - 1)
                    )
                with col4:
                    col_qty = st.selectbox(
                        "الكمية:", cols, index=min(3, len(cols) - 1)
                    )
                with col5:
                    col_rate = st.selectbox(
                        "السعر / الفئة:", cols, index=min(4, len(cols) - 1)
                    )

                if st.button("✅ حفظ الجدول كاملاً في قاعدة البيانات"):
                    saved_count = 0
                    for _, row in extracted_df.iterrows():
                        try:
                            code_val = str(row[col_code]).strip()
                            desc_val = str(row[col_desc]).strip()
                            unit_val = str(row[col_unit]).strip()
                            qty_val = float(
                                str(row[col_qty])
                                .replace(",", "")
                                .replace(" ", "")
                            )
                            rate_val = float(
                                str(row[col_rate])
                                .replace(",", "")
                                .replace(" ", "")
                            )

                            if code_val and qty_val >= 0:
                                db.add_boq_item(
                                    selected_project_id,
                                    code_val,
                                    desc_val,
                                    unit_val,
                                    qty_val,
                                    rate_val,
                                )
                                saved_count += 1
                        except Exception:
                            continue

                    st.success(
                        f"تم حفظ {saved_count} بند في المشروع بنجاح!"
                    )
                    st.rerun()
            else:
                st.error("لم يتم العثور على بنود قابلة للقراءة في هذا الملف.")
    else:
        st.warning("يرجى اختيار مشروع أولاً من القائمة الجانبية.")

# تبويب تقارير البروجريس
with tab1:
    if selected_project_id:
        st.subheader(f"📊 تقرير البروجريس: ({selected_project_name})")
        summary_df = db.get_boq_summary(selected_project_id)
        if not summary_df.empty:
            st.dataframe(summary_df, use_container_width=True)
        else:
            st.info("لا توجد بنود تعاقدية مضافة لهذا المشروع بعد.")

# تبويب إضافة مشروع
with tab4:
    st.subheader("➕ إضافة مشروع جديد")
    with st.form("new_project_form"):
        p_name = st.text_input("اسم المشروع:")
        p_client = st.text_input("الجهة المالكية / الاستشاري:")
        if st.form_submit_button("إنشاء المشروع"):
            if p_name:
                ok, msg = db.add_project(p_name, p_client)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

st.divider()
st.markdown(
    "<center>© جميع الحقوق محفوظة - تطوير م. أحمد السيد | شركة العامرية"
    " المتحدة للمقاولات</center>",
    unsafe_allow_html=True,
)