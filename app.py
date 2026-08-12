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


# --- 3. معالجة وتصحيح ترتيب ونصوص الجدول ---
def fix_cell_text(val):
    if not val or str(val).strip() in ["None", ""]:
        return ""
    text = str(val).strip()

    # تنظيف رموز cid المكسورة
    if "cid:" in text:
        return ""

    # تصحيح عكس الكلمات العربية والمجزءة
    try:
        # إذا كان النص مكسوراً ومشقلباً (مثل .1 أو m3)
        if (
            any("\u0600" <= c <= "\u06ff" for c in text)
            or text.startswith(".")
            or text.endswith("3")
        ):
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        return text
    except Exception:
        return text


def extract_boq_from_pdf(pdf_file, reverse_columns=True):
    all_rows = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if table:
                    for row in table:
                        cleaned_row = [fix_cell_text(cell) for cell in row]
                        if any(cleaned_row):
                            all_rows.append(cleaned_row)

    if all_rows:
        raw_df = pd.DataFrame(all_rows)

        # 🔄 عكس ترتيب الأعمدة من اليمين إلى اليسار ليصبح كود/رقم البند هو العمود الأول
        if reverse_columns:
            raw_df = raw_df.iloc[:, ::-1]

        # إعادة تسمية العناوين
        cols = [f"العمود {i+1}" for i in range(raw_df.shape[1])]
        raw_df.columns = cols

        return raw_df.reset_index(drop=True)
    return None


# --- 4. واجهة المستخدم ---
db = ProgressTrackerDB()

st.title(
    "🏗️ منصة إدارة المشاريع والكميات - شركة العامرية المتحدة للمقاولات"
)

st.sidebar.title("👨‍💼 تطوير وإعداد")
st.sidebar.markdown("**المهندس:** أحمد السيد")
st.sidebar.markdown("📱 **تليفون / واتساب:** `0546226304`")
st.sidebar.markdown("📧 **البريد:** `ahmadalsayed9797@gmail.com`")
st.sidebar.divider()

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

tab1, tab2, tab3 = st.tabs(
    ["📊 تقرير المشروع الحسابي", "📄 قراءة BOQ من PDF", "➕ إدارة المشاريع"]
)

with tab2:
    if selected_project_id:
        st.subheader(
            "📄 قراءة واستخراج جميع بنود الـ BOQ من ملف PDF لـ"
            f" ({selected_project_name})"
        )

        col_up1, col_up2 = st.columns([3, 1])
        with col_up1:
            pdf_file = st.file_uploader(
                "اختر ملف الـ BOQ بصيغة PDF",
                type=["pdf"],
                key="boq_pdf_uploader",
            )
        with col_up2:
            st.write("⚙️ خيارات الاتجاه:")
            flip_cols = st.checkbox(
                "عكس ترتيب الأعمدة (يمين ↔ شمال)", value=True
            )

        if pdf_file is not None:
            with st.spinner("جاري تعديل ترتيب الأعمدة وتعديل النصوص..."):
                extracted_df = extract_boq_from_pdf(
                    pdf_file, reverse_columns=flip_cols
                )

            if extracted_df is not None and not extracted_df.empty:
                st.success(f"تم استخراج الجدول! عدد الصفوف: {len(extracted_df)}")
                st.dataframe(extracted_df, use_container_width=True)

                st.divider()
                st.markdown(
                    "### 💾 ربط وتسكين الأعمدة في قاعدة بيانات المشروع"
                )

                cols = list(extracted_df.columns)
                col1, col2, col3 = st.columns(3)
                col4, col5, _ = st.columns(3)

                with col1:
                    col_code = st.selectbox(
                        "كود البند / الرقم:", cols, index=0
                    )
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
                st.error("لم يتم العثور على جداول قابلة للقراءة.")
    else:
        st.warning("يرجى اختيار مشروع أولاً من القائمة الجانبية.")

with tab1:
    if selected_project_id:
        st.subheader(f"📊 تقرير البروجريس: ({selected_project_name})")
        summary_df = db.get_boq_summary(selected_project_id)
        if not summary_df.empty:
            st.dataframe(summary_df, use_container_width=True)
        else:
            st.info("لا توجد بنود تعاقدية مضافة لهذا المشروع بعد.")

with tab3:
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