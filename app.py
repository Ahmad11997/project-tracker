import sqlite3
from datetime import date
import pandas as pd
import pdfplumber
import streamlit as st


# --- 1. محرك قاعدة البيانات المطور ---
class ProgressTrackerDB:

    def __init__(self, db_name="project_progress.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()

        # جدول المشاريع
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE,
                client_name TEXT,
                created_at TEXT
            )
        """)

        # جدول المستخدمين
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                full_name TEXT,
                role TEXT
            )
        """)

        # جدول الـ BOQ (مرتبط بالمشروع)
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

        # جدول الـ WIRs (مرتبط بالمشروع والمستخدم)
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
        summary = self.get_boq_summary(project_id, boq_code)
        if summary:
            remaining_qty = summary["remaining_qty"]
            if approved_qty > remaining_qty:
                return (
                    False,
                    f"خطأ: الكمية المدخلة ({approved_qty}) تتجاوز المتبقي"
                    f" ({remaining_qty})!",
                )

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


# --- دالة استخراج الجداول من PDF المحدثة مع معالجة خطأ الدمج ---
def extract_boq_from_pdf(pdf_file):
    all_rows = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if table:
                    for row in table:
                        cleaned_row = [
                            str(cell).strip() if cell is not None else ""
                            for cell in row
                        ]
                        if any(cleaned_row):
                            all_rows.append(cleaned_row)

    if all_rows:
        raw_df = pd.DataFrame(all_rows)
        header = raw_df.iloc[0]
        final_df = raw_df[1:].copy()
        final_df.columns = [
            f"Col_{i+1}: {col}" for i, col in enumerate(header)
        ]
        return final_df.reset_index(drop=True)
    return None


# --- 2. واجهة التطبيق ---
db = ProgressTrackerDB()

st.set_page_config(
    page_title="شركة العامرية المتحدة للمقاولات - إدارة المشاريع",
    layout="wide",
    page_icon="🏗️",
)

st.title(
    "🏗️ منصة إدارة المشاريع والكميات - شركة العامرية المتحدة للمقاولات"
)

# --- الشريط الجانبي ---
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

    st.sidebar.divider()
    st.sidebar.header(f"📝 إدخال WIR مشروع: {selected_project_name}")

    boq_df = db.get_boq_summary(selected_project_id)

    if not boq_df.empty:
        boq_list = boq_df["boq_code"].tolist()
        selected_boq = st.sidebar.selectbox("اختر بند الـ BOQ:", boq_list)
        wir_no = st.sidebar.text_input("رقم الـ WIR:")
        wir_date = st.sidebar.date_input("تاريخ الاعتماد:", date.today())
        location = st.sidebar.text_input("الموقع / المحطة:")
        approved_qty = st.sidebar.number_input(
            "الكمية المعتمدة:", min_value=0.0, step=1.0
        )
        status = st.sidebar.selectbox("حالة الاعتماد:", ["Code A", "Code B"])

        if st.sidebar.button("حفظ الـ WIR"):
            success, msg = db.record_wir(
                selected_project_id,
                wir_no,
                str(wir_date),
                selected_boq,
                location,
                approved_qty,
                status,
                user_name,
            )
            if success:
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)
    else:
        st.sidebar.info("قم بإضافة جدول الكميات BOQ لهذا المشروع أولاً.")
else:
    st.sidebar.warning(
        "لا توجد مشاريع مضافة حالياً. يرجى إضافة مشروع جديد."
    )
    selected_project_id = None

# --- تبويبات المنصة ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 تقرير المشروع الحسابي",
    "📄 قراءة BOQ من PDF",
    "⚙️ إعدادات BOQ اليدوية",
    "➕ إدارة المشاريع",
])

# Tab 1: تقارير المشروع المختار
with tab1:
    if selected_project_id:
        st.subheader(
            f"📊 تقرير البروجريس الخاص بمشروع: ({selected_project_name})"
        )
        summary_df = db.get_boq_summary(selected_project_id)

        if not summary_df.empty:
            total_contract = summary_df["total_budget"].sum()
            total_earned = summary_df["earned_value"].sum()
            overall_progress = (
                (total_earned / total_contract * 100)
                if total_contract > 0
                else 0
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("إجمالي قيمة العقد", f"{total_contract:,.2f} SAR")
            col2.metric("القيمة المكتسبة (EV)", f"{total_earned:,.2f} SAR")
            col3.metric("نسبة الإنجاز المالي", f"{overall_progress:.2f} %")

            st.dataframe(summary_df, use_container_width=True)

            excel_data = summary_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                f"📥 تصدير تقرير ({selected_project_name})",
                excel_data,
                f"{selected_project_name}_Progress.csv",
                "text/csv",
            )
        else:
            st.info("لا توجد بنود تعاقدية مضافة لهذا المشروع بعد.")
    else:
        st.warning(
            "يرجى اختيار أو إضافة مشروع من القائمة الجانبية أو تبويب إدارة"
            " المشاريع."
        )

# Tab 2: استخراج BOQ تلقائياً من ملفات PDF
with tab2:
    if selected_project_id:
        st.subheader(
            "📄 رفع واستخراج جدول الكميات (BOQ) من ملف PDF لـ"
            f" ({selected_project_name})"
        )
        pdf_file = st.file_uploader(
            "اختر ملف BOQ بصيغة PDF", type=["pdf"], key="boq_pdf_uploader"
        )

        if pdf_file is not None:
            with st.spinner("جاري قراءة وتحليل ملف الـ PDF..."):
                extracted_df = extract_boq_from_pdf(pdf_file)

            if extracted_df is not None and not extracted_df.empty:
                st.success("تم قراءة مستند الـ PDF بنجاح!")
                st.markdown("### معاينة الجدول المستخرج:")
                st.dataframe(extracted_df, use_container_width=True)

                st.divider()
                st.markdown("#### 📥 حفظ البيانات المستخرجة في قاعدة البيانات")
                st.info(
                    "حدد الأعمدة المناسبة لتسكينها مباشرة في قاعدة البيانات:"
                )

                cols = list(extracted_df.columns)
                col_code = st.selectbox(
                    "عمود كود البند (BOQ Code):", cols, index=0
                )
                col_desc = st.selectbox(
                    "عمود الوصف (Description):",
                    cols,
                    index=min(1, len(cols) - 1),
                )
                col_unit = st.selectbox(
                    "عمود الوحدة (Unit):", cols, index=min(2, len(cols) - 1)
                )
                col_qty = st.selectbox(
                    "عمود الكمية (Qty):", cols, index=min(3, len(cols) - 1)
                )
                col_rate = st.selectbox(
                    "عمود الفئة/السعر (Rate):", cols, index=min(4, len(cols) - 1)
                )

                if st.button("حفظ الجدول المستخرج في هذا المشروع"):
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
                        f"تم حفظ {saved_count} بند بنجاح في قاعدة البيانات!"
                    )
                    st.rerun()
            else:
                st.error(
                    "لم يتم العثور على جداول واضحة في الملف. تأكد أن ملف الـ PDF"
                    " ليس عبارة عن صور ممسوحة ضوئياً (Scanned)."
                )
    else:
        st.warning("يرجى اختيار مشروع أولاً من القائمة الجانبية.")

# Tab 3: إعدادات BOQ اليدوية
with tab3:
    if selected_project_id:
        st.subheader(f"إضافة بند يدوياً لمشروع: ({selected_project_name})")
        with st.form("boq_form"):
            b_code = st.text_input("كود البند (BOQ Code):")
            b_desc = st.text_input("وصف البند:")
            b_unit = st.text_input("الوحدة:")
            b_qty = st.number_input("الكمية التعاقدية:", min_value=0.0)
            b_rate = st.number_input("فئة السعر (Unit Rate):", min_value=0.0)

            if st.form_submit_button("حفظ البند في هذا المشروع"):
                db.add_boq_item(
                    selected_project_id,
                    b_code,
                    b_desc,
                    b_unit,
                    b_qty,
                    b_rate,
                )
                st.success("تم حفظ البند بنجاح داخل هذا المشروع!")
                st.rerun()
    else:
        st.warning(
            "قم باختيار أو إنشاء مشروع أولاً لكي تتمكن من إدخال البنود."
        )

# Tab 4: إنشاء وإدارة المشاريع الجديدة
with tab4:
    st.subheader("➕ إضافة مشروع جديد إلى النظام")
    with st.form("new_project_form"):
        p_name = st.text_input("اسم المشروع (مثال: شبكات مياه حائل):")
        p_client = st.text_input("الجهة المالكية / الاستشاري:")

        if st.form_submit_button("إنشاء المشروع"):
            if p_name:
                ok, msg = db.add_project(p_name, p_client)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("يرجى إدخال اسم المشروع.")

st.divider()
st.markdown(
    "<center>© جميع الحقوق محفوظة - تطوير م. أحمد السيد | شركة العامرية"
    " المتحدة للمقاولات</center>",
    unsafe_allow_html=True,
)