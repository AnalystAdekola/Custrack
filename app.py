import re
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime
import io

# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- BACKEND MULTI-USER DATABASE ENGINE (SQLITE) ---
DB_FILE = "fabskollexionn.db"

def init_db():
    """Initializes the multi-user user registry and transactional databases with safety migrations."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. User Accounts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Email TEXT UNIQUE,
            Password TEXT,
            Business_Name TEXT,
            Business_Logo BLOB
        )
    """)
    
    # 2. Base Orders Table Setup
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Time_Log TEXT,
            Customer_Name TEXT,
            Customer_Phone TEXT,
            Receiver_Name TEXT,
            Delivery_Address TEXT,
            Receiver_State TEXT,
            Receiver_Phone TEXT,
            Status TEXT,
            Payment_Status TEXT,
            Marketplace_Channel TEXT
        )
    """)
    
    # 🛠️ DYNAMIC MIGRATION LAYER: Inspect the table and add user_id if it's missing from old versions
    cursor.execute("PRAGMA table_info(orders)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "user_id" not in columns:
        # Default legacy orders to user_id = 1 so your old records remain visible
        cursor.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER DEFAULT 1")
        
    conn.commit()
    conn.close()

# --- SECURITY & REGISTRY UTILITY OPERATIONS ---
def register_user(email, password, biz_name, logo_bytes):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (Email, Password, Business_Name, Business_Logo) VALUES (?, ?, ?, ?)",
            (email, password, biz_name, logo_bytes)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(email, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, Business_Name, Business_Logo FROM users WHERE Email = ? AND Password = ?", (email, password))
    user = cursor.fetchone()
    conn.close()
    return user

# --- DYNAMIC DATA FILTERS BASED ON ACTIVE LOGGED-IN USER ID ---
def save_order_to_db(order_dict, user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, Time_Log, Customer_Name, Customer_Phone, Receiver_Name, Delivery_Address, Receiver_State, Receiver_Phone, Status, Payment_Status, Marketplace_Channel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, order_dict["Time_Log"], order_dict["Customer_Name"], order_dict["Customer_Phone"],
        order_dict["Receiver_Name"], order_dict["Delivery_Address"], order_dict["Receiver_State"], 
        order_dict["Receiver_Phone"], order_dict["Status"], order_dict["Payment_Status"], order_dict["Marketplace_Channel"]
    ))
    conn.commit()
    conn.close()

def load_orders_from_db(user_id):
    """Loads records belonging exclusively to the authenticated user ID profile connection."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM orders WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_orders_from_db(id_list, user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if len(id_list) == 1:
        cursor.execute(f"DELETE FROM orders WHERE id = {id_list[0]} AND user_id = {user_id}")
    else:
        cursor.execute(f"DELETE FROM orders WHERE id IN {tuple(id_list)} AND user_id = {user_id}")
    conn.commit()
    conn.close()

# Initialize Database Architecture
init_db()


# --- FIXED HIGH-CONTRAST PDF GENERATOR WITH AUTO-WRAPPING ---
def generate_pdf(dataframe):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=15, leftMargin=15, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor("#1E3A8A"), alignment=1 
    )
    header_cell_style = ParagraphStyle(
        'HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.whitesmoke, alignment=1
    )
    body_cell_style = ParagraphStyle(
        'BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=7, leading=10, textColor=colors.HexColor("#1E293B"), alignment=1
    )
    
    story.append(Paragraph("Custrack Customer & Delivery Log Report", title_style))
    story.append(Spacer(1, 15))
    
    columns = list(dataframe.columns)
    header_row = [Paragraph(str(col).replace("_", " "), header_cell_style) for col in columns]
    data = [header_row] 
    
    for _, row in dataframe.iterrows():
        body_row = [Paragraph(str(val), body_cell_style) for val in row.values]
        data.append(body_row)
        
    column_widths = [55, 60, 65, 65, 65, 102, 60, 65, 45]
    t = Table(data, colWidths=column_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer


# --- REGEX EXTRACTOR ENGINE ---
def extract_order_details(text_block):
    patterns = {
        "Customer_Name": r"Customer\s*Name:\s*(.*)",
        "Customer_Phone": r"Customer\s*Phone\s*(?:No|Number)?:\s*(.*)",
        "Receiver_Name": r"Receiver\s*Name:\s*(.*)",
        "Delivery_Address": r"(?:Receiver\s*)?Address:\s*(.*)",
        "Receiver_State": r"Receiver\s*State\s*/\s*Province:\s*(.*)",
        "Receiver_Phone": r"Receiver\s*Phone\s*(?:No|Number)?:\s*(.*)"
    }
    
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text_block, re.IGNORECASE)
        extracted[key] = match.group(1).strip() if match else "Not Provided"
        
    if extracted["Receiver_Name"] == "Not Provided" or not extracted["Receiver_Name"]:
        extracted["Receiver_Name"] = extracted["Customer_Name"]
    if extracted["Receiver_Phone"] == "Not Provided" or not extracted["Receiver_Phone"]:
        extracted["Receiver_Phone"] = extracted["Customer_Phone"]
        
    return extracted


# --- RE-CONFIGURED PAGE INTERFACE SETUP ---
st.set_page_config(page_title="Custrack — Multi-User Workspace", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded")

# Initialize Authorization Memory Containers
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "biz_name" not in st.session_state:
    st.session_state.biz_name = ""
if "biz_logo" not in st.session_state:
    st.session_state.biz_logo = None
if "theme_dark" not in st.session_state:
    st.session_state.theme_dark = False


# --- THEME CUSTOM STYLE LAYOUT INJECTORS ---
if st.session_state.theme_dark:
    text_color = "#F8FAFC"
    accent_color = "#38BDF8"
    card_bg = "#1E293B"
    border_color = "#334155"
    chart_color_1 = "#38BDF8"
    chart_color_2 = "#F43F5E"
    st.markdown(f"""
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background-color: #0F172A !important; color: {text_color} !important; font-family: 'Inter', sans-serif !important; }}
        h1, h2, h3, h4, h5, h6, p, label, span, small, strong, [data-testid="stMarkdownContainer"] p {{ color: {text_color} !important; }}
        [data-testid="stSidebar"] {{ background-color: #1E293B !important; border-right: 1px solid {border_color} !important; }}
        [data-testid="stSidebar"] * {{ color: {text_color} !important; }}
        .stSelectbox div[data-baseweb="select"], .stSelectbox div[data-baseweb="select"] *, .stTextInput input, .stTextArea textarea, input, textarea, select, option {{ color: #0F172A !important; font-weight: 500 !important; }}
        div.stButton button, div.stDownloadButton button, div.stButton button p, div.stDownloadButton button p, [data-testid="stBaseButton-primary"] *, [data-testid="stBaseButton-secondary"] * {{ background-color: #38BDF8 !important; color: #0F172A !important; border: 1px solid #38BDF8 !important; font-weight: bold !important; }}
        div.stButton button:hover, div.stDownloadButton button:hover, div.stButton button:hover p, div.stDownloadButton button:hover p {{ background-color: #0EA5E9 !important; color: #FFFFFF !important; }}
        div[data-baseweb="multiselect"] span, div[data-baseweb="multiselect"] div {{ color: #0F172A !important; }}
        div[data-testid="stDataFrame"] *, div[data-testid="data-grid"] * {{ color: #FFFFFF !important; }}
        </style>
    """, unsafe_allow_html=True)
else:
    text_color = "#0F172A"
    accent_color = "#1E3A8A"
    card_bg = "#FFFFFF"
    border_color = "#CBD5E1"
    chart_color_1 = "#1E3A8A"
    chart_color_2 = "#D97706"
    st.markdown(f"""
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background-color: #F8FAFC !important; color: {text_color} !important; font-family: 'Inter', sans-serif !important; }}
        h1, h2, h3, h4, h5, h6, p, label, span, strong, [data-testid="stMarkdownContainer"] p {{ color: {text_color} !important; }}
        [data-testid="stSidebar"] {{ background-color: #E2E8F0 !important; border-right: 1px solid {border_color} !important; }}
        [data-testid="stSidebar"] * {{ color: {text_color} !important; }}
        .stSelectbox div[data-baseweb="select"], .stTextInput input, .stTextArea textarea {{ background-color: {card_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important; }}
        div.stButton button, div.stDownloadButton button, div.stButton button p, div.stDownloadButton button p {{ background-color: #1E3A8A !important; color: #FFFFFF !important; border: 1px solid #1E3A8A !important; font-weight: bold !important; }}
        div.stButton button:hover, div.stDownloadButton button:hover, div.stButton button:hover p, div.stDownloadButton button:hover p {{ background-color: #1D4ED8 !important; color: #FFFFFF !important; }}
        </style>
    """, unsafe_allow_html=True)


# =========================================================================
# 🔒 GATEWAY WALL: USER REGISTRATION AND LOGIN PORTAL
# =========================================================================
if not st.session_state.user_authenticated:
    st.title("🛍️ Welcome to Custrack Portal")
    st.markdown("Please log in or create a secure account to access your isolated business dashboard.")
    
    auth_mode = st.radio("Choose Action Portal:", ["Sign In to Account", "Create New Custrack Account"], horizontal=True)
    st.markdown("---")
    
    if auth_mode == "Create New Custrack Account":
        st.subheader("📝 Sign Up Form")
        reg_email = st.text_input("Valid Email Address")
        reg_pass = st.text_input("Create Password", type="password")
        reg_confirm = st.text_input("Reconfirm Password", type="password")
        
        # Live Password Requirement Matrix Rules Evaluation
        has_upper = any(c.isupper() for c in reg_pass)
        has_digit = any(c.isdigit() for c in reg_pass)
        has_min_len = len(reg_pass) >= 7
        
        if reg_pass:
            if has_upper and has_digit and has_min_len:
                st.success("👑 Password Strength: Strong (Meets all parameters)")
                pass_is_valid = True
            else:
                st.error("❌ Password Strength: Weak (Must contain at least 7 characters, a Capital letter, and a Number)")
                pass_is_valid = False
                
            if reg_pass != reg_confirm:
                st.warning("⚠️ Status Notice: Reconfirmed validation entry does not match original password input.")
                pass_matches = False
            else:
                pass_matches = True
        else:
            pass_is_valid = False
            pass_matches = False

        st.markdown("#### Corporate Profile Attachments")
        reg_biz_name = st.text_input("Business Name * (Compulsory)")
        reg_biz_logo = st.file_uploader("Upload Business Logo Image * (Compulsory)", type=["png", "jpg", "jpeg"])
        
        if st.button("🚀 Register Corporate Account", use_container_width=True):
            if not reg_email or not reg_biz_name or not reg_biz_logo:
                st.error("Validation Error: All profile form elements marked with an asterisk (*) are strictly compulsory.")
            elif not pass_is_valid:
                st.error("Validation Error: Please increase your password complexity to fulfill strength metrics.")
            elif not pass_matches:
                st.error("Validation Error: Passwords must match exactly before database synchronization.")
            else:
                logo_binary_blob = reg_biz_logo.read()
                success = register_user(reg_email, reg_pass, reg_biz_name, logo_binary_blob)
                if success:
                    st.success("Account constructed successfully! Switching workspace portals...")
                    st.info("You can now toggle to 'Sign In to Account' to open your tracker.")
                else:
                    st.error("Database Collision Error: That email address has already been registered.")
                    
    elif auth_mode == "Sign In to Account":
        st.subheader("🔑 Access Workspace Identity validation")
        login_email = st.text_input("Account Registered Email")
        login_pass = st.text_input("Security Key Account Password", type="password")
        
        if st.button("⚡ Authenticate & Open Dashboard", use_container_width=True):
            user_match = verify_user(login_email, login_pass)
            if user_match:
                st.session_state.user_authenticated = True
                st.session_state.user_id = user_match[0]
                st.session_state.biz_name = user_match[1]
                st.session_state.biz_logo = user_match[2]
                st.toast(f"Welcome back to Custrack, {st.session_state.biz_name}!")
                st.rerun()
            else:
                st.error("Access Denied: Invalid combination credentials checked. Verify your login parameters.")
    st.stop()


# =========================================================================
# 🔓 APPLICATION LAYER: EXECUTED ONLY IF ACCOUNT CREDENTIALS VALIDATED
# =========================================================================

# --- SIDEBAR MENU ARCHISTRATION ---
with st.sidebar:
    # 3. Dynamic Custom Welcome Branding Display Grid Layout Component
    if st.session_state.biz_logo:
        st.image(st.session_state.biz_logo, width=110)
    
    st.markdown(f"### ✨ **{st.session_state.biz_name}**")
    st.markdown("`WELCOME TO CUSTRACK`")
    st.markdown("---")
    
    st.markdown("## 🧭 Main Menu")
    navigation_selection = st.radio(
        "Choose Workspace Selectors:",
        ["📥 Quick Paste Workspace", "📊 View Data & Cloud Exports", "🏆 Patronage Dashboard"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 🌗 System Theme Config")
    bulb_label = "💡 Theme Mode: Dark" if st.session_state.theme_dark else "💡 Theme Mode: Light"
    if st.button(bulb_label, use_container_width=True):
        st.session_state.theme_dark = not st.session_state.theme_dark
        st.rerun()
        
    if st.button("🚪 Log Out of Profile", type="secondary", use_container_width=True):
        st.session_state.user_authenticated = False
        st.session_state.user_id = None
        st.session_state.biz_name = ""
        st.session_state.biz_logo = None
        st.rerun()

# --- DYNAMICALLY SEGREGATED CONTENT LOADING FRAMEWORK ROUTER ---
USER_CONTEXT_ID = st.session_state.user_id

if navigation_selection == "📥 Quick Paste Workspace":
    st.markdown(f"### <span style='color:{accent_color}'>Paste Raw Customer Dispatch Block</span>", unsafe_allow_html=True)
    
    placeholder_text = (
        "Customer Name: Adefarasin John\n"
        "Customer Phone No: 09071234567\n"
        "Receiver Name: Pelumi Odulaja\n"
        "Receiver Address: 10 Surulere\n"
        "Receiver State/Province: Lagos State\n"
        "Receiver Phone No: 08081234567"
    )
    
    raw_pasted_text = st.text_area("Drop plain text string block here:", height=220, placeholder=placeholder_text)
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        payment_condition = st.selectbox("Direct Ledger Payment Status", ["Paid", "Pending Verify", "COD - Cash on Delivery"])
    with col_opt2:
        source_channel = st.selectbox("Marketplace Origin Channel", ["Instagram DMs", "WhatsApp Business", "TikTok Direct", "Facebook DM"])
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("⚡ Save Customer Details", type="primary", use_container_width=True):
        if raw_pasted_text.strip():
            parsed_data = extract_order_details(raw_pasted_text)
            
            if parsed_data["Customer_Name"] != "Not Provided" or parsed_data["Delivery_Address"] != "Not Provided":
                now = datetime.now()
                timestamp_log = now.strftime("%Y-%m-%d %H:%M:%S")
                
                final_row = {
                    "Time_Log": timestamp_log,
                    "Customer_Name": parsed_data["Customer_Name"],
                    "Customer_Phone": parsed_data["Customer_Phone"],
                    "Receiver_Name": parsed_data["Receiver_Name"],
                    "Delivery_Address": parsed_data["Delivery_Address"],
                    "Receiver_State": parsed_data["Receiver_State"],
                    "Receiver_Phone": parsed_data["Receiver_Phone"],
                    "Status": f"{payment_condition} ({source_channel})",
                    "Payment_Status": payment_condition,
                    "Marketplace_Channel": source_channel
                }
                
                # Locked seamlessly to the active user context profile identity
                save_order_to_db(final_row, USER_CONTEXT_ID)
                
                st.markdown(f"""
                <div style="background-color: #10B981; padding: 15px; border-radius: 8px; color: white; font-weight: bold; margin-bottom: 15px;">
                    🎯 Saved! Record written permanently to database disk for {final_row['Customer_Name']}.
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("#### Outbound Confirmation Copy Block")
                outbound_receipt = (
                    f"Hello {final_row['Customer_Name']},\n\n"
                    f"We've successfully logged your order delivery details! ✨\n\n"
                    f"📦 Dispatch To: {final_row['Receiver_Name']}\n"
                    f"📍 Target Address: {final_row['Delivery_Address']}, {final_row['Receiver_State']}\n"
                    f"📞 Delivery Hotline: {final_row['Receiver_Phone']}\n\n"
                    f"Thank you for shopping with {st.session_state.biz_name}! 🛍️"
                )
                st.text_area("Copy and send directly to customer:", value=outbound_receipt, height=140)
            else:
                st.error("Parse Error: Could not extract details. Check text tags.")
        else:
            st.error("Text field is empty.")

elif navigation_selection == "📊 View Data & Cloud Exports":
    st.markdown(f"### <span style='color:{accent_color}'>View Data & File Exporters</span>", unsafe_allow_html=True)
    
    # Loads isolated user records ONLY
    raw_ledger_df = load_orders_from_db(USER_CONTEXT_ID)
    
    if not raw_ledger_df.empty:
        date_objects = pd.to_datetime(raw_ledger_df['Time_Log'], errors='coerce')
        raw_ledger_df['Log_Month'] = date_objects.dt.strftime('%B').fillna('Unknown')
        raw_ledger_df['Day_of_Week'] = date_objects.dt.strftime('%A').fillna('Unknown')
        
        arranged_df = raw_ledger_df[[
            'id', 'Log_Month', 'Day_of_Week', 'Customer_Name', 'Customer_Phone', 
            'Receiver_Name', 'Delivery_Address', 'Receiver_State', 'Receiver_Phone', 
            'Payment_Status', 'Marketplace_Channel'
        ]]

        st.markdown("#### 📑 Excel Column-Level Filter Dropdowns")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        f_col5, f_col6, f_col7, f_col8 = st.columns(4)
        
        with f_col1:
            month_list = ["All"] + sorted(arranged_df['Log_Month'].unique().tolist())
            sel_month = st.selectbox("Log Month", month_list)
        with f_col2:
            day_list = ["All"] + sorted(arranged_df['Day_of_Week'].unique().tolist())
            sel_day = st.selectbox("Weekday", day_list)
        with f_col3:
            state_list = ["All"] + sorted(arranged_df['Receiver_State'].unique().tolist())
            sel_state = st.selectbox("Receiver State", state_list)
        with f_col4:
            pay_list = ["All"] + sorted(arranged_df['Payment_Status'].unique().tolist())
            sel_pay = st.selectbox("Payment Status", pay_list)
        with f_col5:
            chan_list = ["All"] + sorted(arranged_df['Marketplace_Channel'].unique().tolist())
            sel_chan = st.selectbox("Marketplace Channel", chan_list)
        with f_col6:
            cust_list = ["All"] + sorted(arranged_df['Customer_Name'].unique().tolist())
            sel_cust = st.selectbox("Customer Name", cust_list)
        with f_col7:
            phone_list = ["All"] + sorted(arranged_df['Customer_Phone'].unique().tolist())
            sel_phone = st.selectbox("Customer Phone", phone_list)
        with f_col8:
            text_address_query = st.text_input("Street Address Search", placeholder="Type keywords...").strip().lower()

        filtered_df = arranged_df.copy()
        if sel_month != "All": filtered_df = filtered_df[filtered_df['Log_Month'] == sel_month]
        if sel_day != "All": filtered_df = filtered_df[filtered_df['Day_of_Week'] == sel_day]
        if sel_state != "All": filtered_df = filtered_df[filtered_df['Receiver_State'] == sel_state]
        if sel_pay != "All": filtered_df = filtered_df[filtered_df['Payment_Status'] == sel_pay]
        if sel_chan != "All": filtered_df = filtered_df[filtered_df['Marketplace_Channel'] == sel_chan]
        if sel_cust != "All": filtered_df = filtered_df[filtered_df['Customer_Name'] == sel_cust]
        if sel_phone != "All": filtered_df = filtered_df[filtered_df['Customer_Phone'] == sel_phone]
        if text_address_query: filtered_df = filtered_df[filtered_df['Delivery_Address'].str.lower().str.contains(text_address_query, na=False)]

        st.caption(f"Showing {len(filtered_df)} of {len(arranged_df)} records matching active criteria filters.")

        col_dl1, col_dl2, col_dl3 = st.columns(3)
        export_df = filtered_df.drop(columns=["id"], errors="ignore")
        
        col_dl1.download_button("📄 Download Filtered CSV", export_df.to_csv(index=False).encode('utf-8'), "custrack_ledger.csv", "text/csv", use_container_width=True)
        
        xlsx_io = io.BytesIO()
        with pd.ExcelWriter(xlsx_io, engine='openpyxl') as wr: export_df.to_excel(wr, index=False, sheet_name="Deliveries")
        xlsx_io.seek(0)
        col_dl2.download_button("📈 Download Filtered Excel (.xlsx)", xlsx_io, "custrack_ledger.xlsx", use_container_width=True)
        
        col_dl3.download_button("📕 Export Filtered PDF", generate_pdf(export_df), "custrack_ledger.pdf", "application/pdf", use_container_width=True)
        
        st.markdown("---")
        st.markdown("#### 🚨 Delete Specified Data Rows")
        deletion_options = { f"Row ID {row['id']} | {row['Customer_Name']}": row['id'] for _, row in filtered_df.iterrows() }
        
        if deletion_options:
            target_selections = st.multiselect("Select specific records to remove:", options=list(deletion_options.keys()))
            if st.button("🗑️ Drop Selected Rows Permanently", type="secondary"):
                if target_selections:
                    delete_orders_from_db([deletion_options[item] for item in target_selections], USER_CONTEXT_ID)
                    st.toast("Selected rows successfully removed from database storage.")
                    st.rerun()
        
        st.markdown("---")
        st.dataframe(export_df, use_container_width=True)
    else:
        st.info("The database storage space is empty for this profile. Log verified entries inside the Quick Paste Workspace.")

elif navigation_selection == "🏆 Patronage Dashboard":
    st.markdown(f"### <span style='color:{accent_color}'>🏆 Customer Loyalty Insights</span>", unsafe_allow_html=True)
    
    dash_df = load_orders_from_db(USER_CONTEXT_ID)
    
    if not dash_df.empty:
        total_orders = len(dash_df)
        unique_customers = dash_df['Customer_Phone'].nunique()
        repeat_customers = sum(dash_df['Customer_Phone'].value_counts() > 1)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1: st.metric("📦 Total Orders Handled", total_orders)
        with col_m2: st.metric("👥 Total Unique Customers", unique_customers)
        with col_m3: st.metric("🔄 Loyal Repeat Customers", repeat_customers)
            
        st.markdown("---")
        st.markdown(f"### <span style='color:{accent_color}'>📊 Sales & Operations Analytics</span>", unsafe_allow_html=True)
        
        date_series = pd.to_datetime(dash_df['Time_Log'], errors='coerce')
        dash_df['Extracted_Day'] = date_series.dt.strftime('%A').fillna('Unknown')
        
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("#### 📅 Day of the Week Sales Count")
            day_counts = dash_df['Extracted_Day'].value_counts().reset_index()
            day_counts.columns = ['Day of Week', 'Sales Volume']
            week_chronological_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_counts['Day of Week'] = pd.Categorical(day_counts['Day of Week'], categories=week_chronological_order, ordered=True)
            st.bar_chart(data=day_counts.sort_values('Day of Week'), x='Day of Week', y='Sales Volume', color=chart_color_1, use_container_width=True)
            
        with chart_col2:
            st.markdown("#### 📍 Regional Distribution Count")
            state_counts = dash_df['Receiver_State'].value_counts().reset_index()
            state_counts.columns = ['Receiver State', 'Orders Volume']
            st.bar_chart(data=state_counts.sort_values(by='Orders Volume', ascending=False), x='Receiver State', y='Orders Volume', color=chart_color_2, use_container_width=True)
            
        st.markdown("---")
        st.markdown("#### 📈 Customer Patronage Leaderboard")
        
        leaderboard = dash_df.groupby('Customer_Phone').agg(Customer_Name=('Customer_Name', 'first'), Total_Patronage_Count=('id', 'count')).reset_index()
        leaderboard = leaderboard.sort_values(by='Total_Patronage_Count', ascending=False).reset_index(drop=True)
        leaderboard = leaderboard[["Customer_Name", "Customer_Phone", "Total_Patronage_Count"]]
        leaderboard.columns = ["👑 Customer Name Reference", "📞 Unique Phone Number", "🛍️ Times Patronized"]
        
        vip_customer = leaderboard.iloc[0]["👑 Customer Name Reference"]
        vip_phone = leaderboard.iloc[0]["📞 Unique Phone Number"]
        vip_count = leaderboard.iloc[0]["🛍️ Times Patronized"]
        
        alert_box_bg = "#1E293B" if st.session_state.theme_dark else "#E2E8F0"
        alert_text_base = "#FFFFFF" if st.session_state.theme_dark else "#1E3A8A"
        
        st.markdown(f"""
        <div style="background-color: {alert_box_bg}; border-left: 5px solid #38BDF8; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
            <span style="color: #38BDF8; font-weight: bold;">✨ VIP Customer Alert:</span><br>
            <span style="color: {alert_text_base};">The customer with phone number <strong>{vip_phone}</strong> ({vip_customer}) is your top patron, ordering <strong>{vip_count} times</strong>!</span>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(leaderboard, use_container_width=True)
    else:
        st.info("No data available yet. Save entries in Tab 1 to populate metrics.")
