import re
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime
import io
import time

# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- COUNTRY DIAL CODE REGISTRY ---
COUNTRIES = {
    "Nigeria": "+234",
    "Ghana": "+233",
    "United Kingdom": "+44",
    "United States": "+1",
    "Canada": "+1",
    "Kenya": "+254",
    "South Africa": "+27",
    "United Arab Emirates": "+971"
}

# --- BACKEND MULTI-USER DATABASE ENGINE (SQLITE) ---
DB_FILE = "fabskollexionn.db"

def init_db():
    """Initializes the multi-user registry with the expanded profile schema and safety migrations."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Updated User Accounts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Email TEXT UNIQUE,
            Password TEXT,
            Business_Name TEXT,
            Owner_Name TEXT,
            Country TEXT,
            Phone_Number TEXT,
            Business_Logo BLOB
        )
    """)
    
    # Base Orders Table Setup
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
    
    # Migration Check to ensure user_id exists in old database schemas
    cursor.execute("PRAGMA table_info(orders)")
    columns = [info[1] for info in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER DEFAULT 1")
        
    # Migration Check to append new profile metrics to the users table seamlessly if updating on disk
    cursor.execute("PRAGMA table_info(users)")
    u_columns = [info[1] for info in cursor.fetchall()]
    if "Owner_Name" not in u_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN Owner_Name TEXT")
    if "Country" not in u_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN Country TEXT")
    if "Phone_Number" not in u_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN Phone_Number TEXT")
        
    conn.commit()
    conn.close()

# --- SECURITY & REGISTRY UTILITY OPERATIONS ---
def register_base_user(email, password):
    """Phase 1 registration: Reserves the user profile with credentials."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (Email, Password) VALUES (?, ?)", (email, password))
        generated_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return generated_id
    except sqlite3.IntegrityError:
        return None

def complete_business_profile(user_id, biz_name, owner_name, country, phone, logo_bytes):
    """Phase 2 registration: Updates the reserved user slot with deep business meta metrics."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET Business_Name = ?, Owner_Name = ?, Country = ?, Phone_Number = ?, Business_Logo = ?
        WHERE id = ?
    """, (biz_name, owner_name, country, phone, logo_bytes, user_id))
    conn.commit()
    conn.close()

def verify_user(email, password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, Business_Name, Business_Logo FROM users WHERE Email = ? AND Password = ?", (email, password))
    user = cursor.fetchone()
    conn.close()
    return user

# --- TRANSACTIONAL LOG DATABASE READ/WRITE LAYER ---
def save_order_to_db(order_dict, user_id):
    """Inserts a parsed order row into the orders table while gracefully falling back if columns are mismatched."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Safely verify columns present in the live orders table on disk
    cursor.execute("PRAGMA table_info(orders)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "user_id" in columns:
        # Production Flow: Multi-user setup matches perfectly
        cursor.execute("""
            INSERT INTO orders (user_id, Time_Log, Customer_Name, Customer_Phone, Receiver_Name, Delivery_Address, Receiver_State, Receiver_Phone, Status, Payment_Status, Marketplace_Channel)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, order_dict["Time_Log"], order_dict["Customer_Name"], order_dict["Customer_Phone"],
            order_dict["Receiver_Name"], order_dict["Delivery_Address"], order_dict["Receiver_State"], 
            order_dict["Receiver_Phone"], order_dict["Status"], order_dict["Payment_Status"], order_dict["Marketplace_Channel"]
        ))
    else:
        # Fallback Legacy Flow: Prevents crashing if the database table hasn't updated its layout yet
        cursor.execute("""
            INSERT INTO orders (Time_Log, Customer_Name, Customer_Phone, Receiver_Name, Delivery_Address, Receiver_State, Receiver_Phone, Status, Payment_Status, Marketplace_Channel)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_dict["Time_Log"], order_dict["Customer_Name"], order_dict["Customer_Phone"],
            order_dict["Receiver_Name"], order_dict["Delivery_Address"], order_dict["Receiver_State"], 
            order_dict["Receiver_Phone"], order_dict["Status"], order_dict["Payment_Status"], order_dict["Marketplace_Channel"]
        ))
        
    conn.commit()
    conn.close()

init_db()

# --- FIXED HIGH-CONTRAST PDF GENERATOR ---
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

# --- NATIVE INTERFACE & SESSION RECOVERY ENGINE ---
st.set_page_config(page_title="Custrack — Multi-User Workspace", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded")

url_session_id = st.query_params.get("session")
url_theme_preference = st.query_params.get("theme")

if "user_authenticated" not in st.session_state: st.session_state.user_authenticated = False
if "user_id" not in st.session_state: st.session_state.user_id = None
if "biz_name" not in st.session_state: st.session_state.biz_name = ""
if "biz_logo" not in st.session_state: st.session_state.biz_logo = None
if "signup_step" not in st.session_state: st.session_state.signup_step = 1
if "temp_user_id" not in st.session_state: st.session_state.temp_user_id = None
if "show_splash" not in st.session_state: st.session_state.show_splash = False

if "theme_dark" not in st.session_state: 
    st.session_state.theme_dark = (url_theme_preference == "dark")

if not st.session_state.user_authenticated and url_session_id:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, Business_Name, Business_Logo FROM users WHERE id = ?", (int(url_session_id),))
    user_match = cursor.fetchone()
    conn.close()
    
    if user_match and user_match[1] is not None:
        st.session_state.user_authenticated = True
        st.session_state.user_id = user_match[0]
        st.session_state.biz_name = user_match[1]
        st.session_state.biz_logo = user_match[2]

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
# 🎬 SPLASH SCREEN ROUTER (ANIMATION EFFECT LAYER)
# =========================================================================
if st.session_state.show_splash:
    splash_bg = "#0F172A" if st.session_state.theme_dark else "#1E3A8A"
    splash_text = "#38BDF8" if st.session_state.theme_dark else "#FFFFFF"
    
    st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 75vh; background: linear-gradient(135deg, {splash_bg}, #1E1B4B); border-radius: 16px; margin: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); animation: fadeIn 1s ease-out;">
            <h1 style="color: {splash_text} !important; font-size: 4rem !important; font-weight: 900 !important; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; text-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                🚀 WELCOME
            </h1>
            <h2 style="color: #F43F5E !important; font-size: 2.5rem !important; font-weight: 700 !important; letter-spacing: 1px;">
                {st.session_state.biz_name}
            </h2>
            <p style="color: #94A3B8 !important; margin-top: 30px; font-size: 1.1rem; font-style: italic;">
                Preparing your workspace environments...
            </p>
        </div>
    """, unsafe_allow_html=True)
    time.sleep(3.0)
    st.session_state.show_splash = False
    st.rerun()

# =========================================================================
# 🔒 GATEWAY WALL: SIGNUP & INITIALIZATION PIPELINE
# =========================================================================
if not st.session_state.user_authenticated:
    st.title("🛍️ Welcome to Custrack Portal")
    
    auth_mode = st.radio("Choose Action Portal:", ["Sign In to Account", "Create New Custrack Account"], horizontal=True)
    st.markdown("---")
    
    if auth_mode == "Create New Custrack Account":
        # --- ONBOARDING PHASE 1: ACCOUNT CREDENTIALS ---
        if st.session_state.signup_step == 1:
            st.subheader("📝 Step 1: Base Account Access Setup")
            reg_email = st.text_input("Valid Email Address")
            reg_pass = st.text_input("Create Secure Password", type="password")
            reg_confirm = st.text_input("Reconfirm Password", type="password")
            
            has_upper = any(c.isupper() for c in reg_pass)
            has_digit = any(c.isdigit() for c in reg_pass)
            has_min_len = len(reg_pass) >= 7
            
            if reg_pass:
                if has_upper and has_digit and has_min_len:
                    st.success("👑 Password Strength: Strong")
                    pass_is_valid = True
                else:
                    st.error("❌ Weak: Minimum 7 tokens with an uppercase character and a numeric token required.")
                    pass_is_valid = False
                pass_matches = (reg_pass == reg_confirm)
                if not pass_matches: st.warning("⚠️ Passwords values do not match yet.")
            else:
                pass_is_valid = pass_matches = False

            if st.button("Proceed to Business Registration ➡️", use_container_width=True):
                if not reg_email or not pass_is_valid or not pass_matches:
                    st.error("Validation Error: Please resolve credential structural metrics before moving forward.")
                else:
                    new_uid = register_base_user(reg_email, reg_pass)
                    if new_uid:
                        st.session_state.temp_user_id = new_uid
                        st.session_state.signup_step = 2
                        st.rerun()
                    else:
                        st.error("Collision Error: Email configuration space already claimed.")

        # --- ONBOARDING PHASE 2: DETAILED CORPORATE REGISTRATION ---
        elif st.session_state.signup_step == 2:
            st.subheader("🏢 Step 2: Establish Corporate Identity Profile")
            
            reg_biz_name = st.text_input("Business Name *")
            reg_owner_name = st.text_input("Owner Full Name *")
            
            selected_country = st.selectbox("Operating Country Structure *", list(COUNTRIES.keys()))
            country_dial = COUNTRIES[selected_country]
            
            # Inline side-by-side presentation layer matching dynamic phone numbers
            p_col1, p_col2 = st.columns([1, 4])
            with p_col1:
                st.text_input("Code", value=country_dial, disabled=True, key="dial_disabled_v")
            with p_col2:
                raw_phone_body = st.text_input("Phone Box Number Entry *", placeholder="80XXXXXXXX")
                
            full_compiled_phone = f"{country_dial}{raw_phone_body.strip()}"
            reg_biz_logo = st.file_uploader("Upload Profile Corporate Logo Asset *", type=["png", "jpg", "jpeg"])
            
            if st.button("Proceed & Initialize Dashboard 🚀", use_container_width=True):
                if not reg_biz_name or not reg_owner_name or not raw_phone_body or not reg_biz_logo:
                    st.error("Validation Error: All properties are mandatory to create your isolated ledger.")
                else:
                    logo_binary_blob = reg_biz_logo.read()
                    complete_business_profile(
                        st.session_state.temp_user_id, reg_biz_name, reg_owner_name, 
                        selected_country, full_compiled_phone, logo_binary_blob
                    )
                    
                    # Log user session state parameters completely
                    st.session_state.user_authenticated = True
                    st.session_state.user_id = st.session_state.temp_user_id
                    st.session_state.biz_name = reg_biz_name
                    st.session_state.biz_logo = logo_binary_blob
                    
                    st.query_params["session"] = str(st.session_state.user_id)
                    st.query_params["theme"] = "dark" if st.session_state.theme_dark else "light"
                    
                    # Reset signup temporary tracks and prompt beautiful welcome animation layer
                    st.session_state.signup_step = 1
                    st.session_state.temp_user_id = None
                    st.session_state.show_splash = True
                    st.rerun()
                    
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
                
                st.query_params["session"] = str(user_match[0])
                st.query_params["theme"] = "dark" if st.session_state.theme_dark else "light"
                
                st.toast(f"Welcome back to Custrack, {st.session_state.biz_name}!")
                st.rerun()
            else:
                st.error("Access Denied: Invalid parameters. Verify your configuration data details.")
    st.stop()

# =========================================================================
# 🔓 APPLICATION LAYER: MAIN LEDGER SYSTEM INTERFACE
# =========================================================================

with st.sidebar:
    if st.session_state.biz_logo:
        st.image(st.session_state.biz_logo, width=110)
    st.markdown(f"### ✨ **{st.session_state.biz_name}**")
    st.markdown("`WORKSPACE ACTIVE`")
    st.markdown("---")
    
    st.markdown("## 🧭 Main Menu")
    navigation_selection = st.radio(
        "Choose Workspace Selectors:",
        ["📥 Quick Paste Workspace", "📊 View Data & Cloud Exports", "🏆 Patronage Dashboard"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    
    bulb_label = "💡 Theme Mode: Dark" if st.session_state.theme_dark else "💡 Theme Mode: Light"
    if st.button(bulb_label, use_container_width=True):
        st.session_state.theme_dark = not st.session_state.theme_dark
        st.query_params["theme"] = "dark" if st.session_state.theme_dark else "light"
        st.rerun()
        
    if st.button("🚪 Log Out of Profile", type="secondary", use_container_width=True):
        st.session_state.user_authenticated = False
        st.session_state.user_id = None
        st.session_state.biz_name = ""
        st.session_state.biz_logo = None
        st.query_params.clear()
        st.rerun()

# --- ADMIN VIEW TIE-IN ---
with st.sidebar: show_raw_database = st.checkbox("🔍 Open Secret Admin DB Viewer")
if show_raw_database:
    st.markdown("## 🔐 Master Database Administrative Overview")
    conn = sqlite3.connect(DB_FILE)
    st.subheader("👥 Registered Corporate Users (`users` Table)")
    try:
        all_users_df = pd.read_sql_query("SELECT id, Email, Business_Name, Owner_Name, Country, Phone_Number FROM users", conn)
        st.dataframe(all_users_df, use_container_width=True)
    except Exception as e: st.error(f"Could not read users table: {e}")
    st.subheader("📦 All Customer Dispatches Master Log (`orders` Table)")
    try:
        all_orders_df = pd.read_sql_query("SELECT * FROM orders", conn)
        st.dataframe(all_orders_df, use_container_width=True)
    except Exception as e: st.error(f"Could not read orders table: {e}")
    conn.close()

# --- WORKSPACE APP VIEW CONTROLLERS ---
USER_CONTEXT_ID = st.session_state.user_id

if navigation_selection == "📥 Quick Paste Workspace":
    st.markdown(f"### <span style='color:{accent_color}'>Paste Raw Customer Dispatch Block</span>", unsafe_allow_html=True)
    placeholder_text = "Customer Name: Adefarasin John\nCustomer Phone No: 09071234567\nReceiver Name: Pelumi Odulaja\nAddress: 10 Surulere\nReceiver State/Province: Lagos State"
    raw_pasted_text = st.text_area("Drop plain text string block here:", height=220, placeholder=placeholder_text)
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1: payment_condition = st.selectbox("Direct Ledger Payment Status", ["Paid", "Pending Verify", "COD - Cash on Delivery"])
    with col_opt2: source_channel = st.selectbox("Marketplace Origin Channel", ["Instagram DMs", "WhatsApp Business", "TikTok Direct", "Facebook DM"])
        
    if st.button("⚡ Save Customer Details", type="primary", use_container_width=True):
        if raw_pasted_text.strip():
            parsed_data = extract_order_details(raw_pasted_text)
            if parsed_data["Customer_Name"] != "Not Provided" or parsed_data["Delivery_Address"] != "Not Provided":
                final_row = {
                    "Time_Log": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Customer_Name": parsed_data["Customer_Name"], "Customer_Phone": parsed_data["Customer_Phone"],
                    "Receiver_Name": parsed_data["Receiver_Name"], "Delivery_Address": parsed_data["Delivery_Address"],
                    "Receiver_State": parsed_data["Receiver_State"], "Receiver_Phone": parsed_data["Receiver_Phone"],
                    "Status": f"{payment_condition} ({source_channel})", "Payment_Status": payment_condition, "Marketplace_Channel": source_channel
                }
                save_order_to_db(final_row, USER_CONTEXT_ID)
                st.success(f"🎯 Saved! Record written permanently to database disk for {final_row['Customer_Name']}.")
                
                outbound_receipt = f"Hello {final_row['Customer_Name']},\n\nWe've successfully logged your order! ✨\n\n📦 Dispatch To: {final_row['Receiver_Name']}\n📍 Target Address: {final_row['Delivery_Address']}, {final_row['Receiver_State']}\n\nThank you for shopping with {st.session_state.biz_name}! 🛍️"
                st.text_area("Copy and send directly to customer:", value=outbound_receipt, height=140)
            else: st.error("Parse Error: Check formatting tags.")
        else: st.error("Text field is empty.")

elif navigation_selection == "📊 View Data & Cloud Exports":
    st.markdown(f"### <span style='color:{accent_color}'>View Data & File Exporters</span>", unsafe_allow_html=True)
    raw_ledger_df = load_orders_from_db(USER_CONTEXT_ID)
    
    if not raw_ledger_df.empty:
        date_objects = pd.to_datetime(raw_ledger_df['Time_Log'], errors='coerce')
        raw_ledger_df['Log_Month'] = date_objects.dt.strftime('%B').fillna('Unknown')
        raw_ledger_df['Day_of_Week'] = date_objects.dt.strftime('%A').fillna('Unknown')
        arranged_df = raw_ledger_df[['id', 'Log_Month', 'Day_of_Week', 'Customer_Name', 'Customer_Phone', 'Receiver_Name', 'Delivery_Address', 'Receiver_State', 'Receiver_Phone', 'Payment_Status', 'Marketplace_Channel']]
        
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1: sel_month = st.selectbox("Log Month", ["All"] + sorted(arranged_df['Log_Month'].unique().tolist()))
        with f_col2: sel_day = st.selectbox("Weekday", ["All"] + sorted(arranged_df['Day_of_Week'].unique().tolist()))
        with f_col3: sel_state = st.selectbox("Receiver State", ["All"] + sorted(arranged_df['Receiver_State'].unique().tolist()))
        with f_col4: sel_pay = st.selectbox("Payment Status", ["All"] + sorted(arranged_df['Payment_Status'].unique().tolist()))

        filtered_df = arranged_df.copy()
        if sel_month != "All": filtered_df = filtered_df[filtered_df['Log_Month'] == sel_month]
        if sel_day != "All": filtered_df = filtered_df[filtered_df['Day_of_Week'] == sel_day]
        if sel_state != "All": filtered_df = filtered_df[filtered_df['Receiver_State'] == sel_state]
        if sel_pay != "All": filtered_df = filtered_df[filtered_df['Payment_Status'] == sel_pay]

        export_df = filtered_df.drop(columns=["id"], errors="ignore")
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        col_dl1.download_button("📄 Download Filtered CSV", export_df.to_csv(index=False).encode('utf-8'), "ledger.csv", "text/csv", use_container_width=True)
        
        xlsx_io = io.BytesIO()
        with pd.ExcelWriter(xlsx_io, engine='openpyxl') as wr: export_df.to_excel(wr, index=False, sheet_name="Deliveries")
        xlsx_io.seek(0)
        col_dl2.download_button("📈 Download Filtered Excel", xlsx_io, "ledger.xlsx", use_container_width=True)
        col_dl3.download_button("📕 Export Filtered PDF", generate_pdf(export_df), "ledger.pdf", "application/pdf", use_container_width=True)
        
        st.dataframe(export_df, use_container_width=True)
    else:
        st.info("The database storage space is empty for this profile.")

elif navigation_selection == "🏆 Patronage Dashboard":
    st.markdown(f"### <span style='color:{accent_color}'>🏆 Customer Loyalty Insights</span>", unsafe_allow_html=True)
    dash_df = load_orders_from_db(USER_CONTEXT_ID)
    
    if not dash_df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("📦 Total Orders Handled", len(dash_df))
        col_m2.metric("👥 Total Unique Customers", dash_df['Customer_Phone'].nunique())
        col_m3.metric("🔄 Loyal Repeat Customers", sum(dash_df['Customer_Phone'].value_counts() > 1))
        
        date_series = pd.to_datetime(dash_df['Time_Log'], errors='coerce')
        dash_df['Extracted_Day'] = date_series.dt.strftime('%A').fillna('Unknown')
        
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("#### 📅 Day of the Week Sales")
            day_counts = dash_df['Extracted_Day'].value_counts().reset_index()
            day_counts.columns = ['Day of Week', 'Sales Volume']
            st.bar_chart(data=day_counts, x='Day of Week', y='Sales Volume', color=chart_color_1, use_container_width=True)
        with chart_col2:
            st.markdown("#### 📍 Regional Distribution")
            state_counts = dash_df['Receiver_State'].value_counts().reset_index()
            state_counts.columns = ['Receiver State', 'Orders Volume']
            st.bar_chart(data=state_counts, x='Receiver State', y='Orders Volume', color=chart_color_2, use_container_width=True)
    else:
        st.info("No data available yet. Save entries to populate metrics.")
