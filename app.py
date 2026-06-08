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

# --- BACKEND DATABASE ENGINE (SQLITE) ---
DB_FILE = "fabskollexionn.db"

def init_db():
    """Initializes the local database file and handles structural updates seamlessly."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Time_Log TEXT,
            Customer_Name TEXT,
            Customer_Phone TEXT,
            Receiver_Name TEXT,
            Delivery_Address TEXT,
            Receiver_Phone TEXT,
            Status TEXT
        )
    """)
    
    # DYNAMIC DATA MIGRATION: Safe lookahead to add missing columns to existing databases
    cursor.execute("PRAGMA table_info(orders)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "Receiver_State" not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN Receiver_State TEXT DEFAULT 'Not Provided'")
    if "Payment_Status" not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN Payment_Status TEXT DEFAULT 'Paid'")
    if "Marketplace_Channel" not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN Marketplace_Channel TEXT DEFAULT 'WhatsApp Business'")
        
    conn.commit()
    conn.close()

def save_order_to_db(order_dict):
    """Inserts a new parsed order row directly onto the disk storage."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
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

def load_orders_from_db():
    """Loads saved rows and handles legacy rows gracefully if they lack split statuses."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM orders", conn)
    conn.close()
    
    if not df.empty:
        if 'Payment_Status' not in df.columns or df['Payment_Status'].isnull().all():
            df['Payment_Status'] = "Paid"
        if 'Marketplace_Channel' not in df.columns or df['Marketplace_Channel'].isnull().all():
            df['Marketplace_Channel'] = "WhatsApp Business"
            
    return df

def delete_orders_from_db(id_list):
    """Deletes rows permanently using their unique primary key IDs."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if len(id_list) == 1:
        cursor.execute(f"DELETE FROM orders WHERE id = {id_list[0]}")
    else:
        cursor.execute(f"DELETE FROM orders WHERE id IN {tuple(id_list)}")
    conn.commit()
    conn.close()

# Initialize database components
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
    
    story.append(Paragraph("Fabskollexionn Customer & Delivery Tracker", title_style))
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


# --- STREAMLIT PAGE SETUP ---
st.set_page_config(page_title="Fabskollexionn Tracker", page_icon="🛍️", layout="wide", initial_sidebar_state="collapsed")

# Keep track of theme state via Session State
if "theme_dark" not in st.session_state:
    st.session_state.theme_dark = False

# --- ASYMMETRIC HEADER ROW GRID ---
head_title_col, head_toggle_col = st.columns([15, 1])

with head_toggle_col:
    # Explicit container padding prevents button labels from being cropped or hidden
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    bulb_label = "💡 On" if st.session_state.theme_dark else "💡 Off"
    help_hint = "Switch to Light Mode" if st.session_state.theme_dark else "Switch to Dark Mode"
    
    if st.button(bulb_label, help=help_hint, use_container_width=True):
        st.session_state.theme_dark = not st.session_state.theme_dark
        st.rerun()

with head_title_col:
    st.title("🛍️ Fabskollexionn Customer & Delivery Tracker")

# --- HIGH-CONTRAST GLOBAL CSS WORKSPACE SYSTEM ---
if st.session_state.theme_dark:
    text_color = "#F8FAFC"
    accent_color = "#38BDF8"
    card_bg = "#1E293B"
    border_color = "#334155"
    
    st.markdown(f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background-color: #0F172A !important;
            color: {text_color} !important;
            font-family: 'Inter', -apple-system, sans-serif !important;
        }}
        /* Target headers, body markers, select labels, and custom text blocks */
        h1, h2, h3, h4, h5, h6, p, label, span, sm, [data-testid="stMarkdownContainer"] p {{
            color: {text_color} !important;
        }}
        /* Force standard visibility across inputs and drop-downs */
        .stSelectbox div[data-baseweb="select"], .stTextInput input, .stTextArea textarea {{
            background-color: {card_bg} !important;
            color: #FFFFFF !important;
            border: 1px solid {border_color} !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: #94A3B8 !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: {accent_color} !important;
            font-weight: 600 !important;
        }}
        </style>
    """, unsafe_allow_html=True)
else:
    text_color = "#0F172A"
    accent_color = "#1E3A8A"
    card_bg = "#FFFFFF"
    border_color = "#CBD5E1"
    
    st.markdown(f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background-color: #F8FAFC !important;
            color: {text_color} !important;
            font-family: 'Inter', -apple-system, sans-serif !important;
        }}
        h1, h2, h3, h4, h5, h6, p, label, span, [data-testid="stMarkdownContainer"] p {{
            color: {text_color} !important;
        }}
        .stSelectbox div[data-baseweb="select"], .stTextInput input, .stTextArea textarea {{
            background-color: {card_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border_color} !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: #475569 !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: {accent_color} !important;
            font-weight: 600 !important;
        }}
        </style>
    """, unsafe_allow_html=True)

st.markdown("Copy, paste, and permanently lock data rows onto local database storage.")
st.markdown("---")

tab_paste, tab_view, tab_dash = st.tabs(["📥 Quick Paste Workspace", "📊 View Data & Cloud Exports", "🏆 Patronage Dashboard"])

# --- TAB 1: PASTE WORKSPACE ---
with tab_paste:
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
        payment_condition = st.selectbox("💳 Direct Ledger Payment Status", ["Paid", "Pending Verify", "COD - Cash on Delivery"])
    with col_opt2:
        source_channel = st.selectbox("📱 Marketplace Origin Channel", ["Instagram DMs", "WhatsApp Business", "TikTok Direct", "Facebook DM"])
        
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
                
                save_order_to_db(final_row)
                
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
                    f"Thank you for shopping with Fabskollexionn! 🛍️"
                )
                st.text_area("Copy and send directly to customer:", value=outbound_receipt, height=140)
            else:
                st.error("Parse Error: Could not extract details. Check text tags.")
        else:
            st.error("Text field is empty.")

# --- TAB 2: DATA REGISTRY ENGINE (WITH EXCEL-STYLE DROPDOWN FILTERS) ---
with tab_view:
    st.markdown(f"### <span style='color:{accent_color}'>View Data & File Exporters</span>", unsafe_allow_html=True)
    
    raw_ledger_df = load_orders_from_db()
    
    if not raw_ledger_df.empty:
        # --- DATETIME TRANSFORMATION ENGINE ---
        date_objects = pd.to_datetime(raw_ledger_df['Time_Log'], errors='coerce')
        raw_ledger_df['Log_Month'] = date_objects.dt.strftime('%B').fillna('Unknown')
        raw_ledger_df['Day_of_Week'] = date_objects.dt.strftime('%A').fillna('Unknown')
        
        # Structural Reordering Matrix
        arranged_df = raw_ledger_df[[
            'id', 'Log_Month', 'Day_of_Week', 'Customer_Name', 'Customer_Phone', 
            'Receiver_Name', 'Delivery_Address', 'Receiver_State', 'Receiver_Phone', 
            'Payment_Status', 'Marketplace_Channel'
        ]]

        # --- EXCEL INTERACTIVE FILTER ROW ---
        st.markdown("#### 📑 Excel Column-Level Filter Dropdowns")
        
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        f_col5, f_col6, f_col7, f_col8 = st.columns(4)
        
        with f_col1:
            month_list = ["All"] + sorted(arranged_df['Log_Month'].unique().tolist())
            sel_month = st.selectbox("📅 Filter Log Month", month_list)
        with f_col2:
            day_list = ["All"] + sorted(arranged_df['Day_of_Week'].unique().tolist())
            sel_day = st.selectbox("📆 Filter Weekday", day_list)
        with f_col3:
            state_list = ["All"] + sorted(arranged_df['Receiver_State'].unique().tolist())
            sel_state = st.selectbox("📍 Filter Receiver State", state_list)
        with f_col4:
            pay_list = ["All"] + sorted(arranged_df['Payment_Status'].unique().tolist())
            sel_pay = st.selectbox("💳 Filter Payment Status", pay_list)
        with f_col5:
            chan_list = ["All"] + sorted(arranged_df['Marketplace_Channel'].unique().tolist())
            sel_chan = st.selectbox("📱 Filter Channel", chan_list)
        with f_col6:
            cust_list = ["All"] + sorted(arranged_df['Customer_Name'].unique().tolist())
            sel_cust = st.selectbox("👤 Filter Customer Name", cust_list)
        with f_col7:
            phone_list = ["All"] + sorted(arranged_df['Customer_Phone'].unique().tolist())
            sel_phone = st.selectbox("📞 Filter Customer Phone", phone_list)
        with f_col8:
            text_address_query = st.text_input("🏠 Search Street Address", placeholder="Type keywords...").strip().lower()

        # --- CASCADE FILTERING CALCULATOR ---
        filtered_df = arranged_df.copy()
        
        if sel_month != "All":
            filtered_df = filtered_df[filtered_df['Log_Month'] == sel_month]
        if sel_day != "All":
            filtered_df = filtered_df[filtered_df['Day_of_Week'] == sel_day]
        if sel_state != "All":
            filtered_df = filtered_df[filtered_df['Receiver_State'] == sel_state]
        if sel_pay != "All":
            filtered_df = filtered_df[filtered_df['Payment_Status'] == sel_pay]
        if sel_chan != "All":
            filtered_df = filtered_df[filtered_df['Marketplace_Channel'] == sel_chan]
        if sel_cust != "All":
            filtered_df = filtered_df[filtered_df['Customer_Name'] == sel_cust]
        if sel_phone != "All":
            filtered_df = filtered_df[filtered_df['Customer_Phone'] == sel_phone]
        if text_address_query:
            filtered_df = filtered_df[filtered_df['Delivery_Address'].str.lower().str.contains(text_address_query, na=False)]

        st.caption(f"Showing {len(filtered_df)} of {len(arranged_df)} records matching active criteria filters.")

        # --- EXPORT ACTIONS PANEL ---
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        export_df = filtered_df.drop(columns=["id"], errors="ignore")
        
        csv_bin = export_df.to_csv(index=False).encode('utf-8')
        col_dl1.download_button("📄 Download Filtered CSV", csv_bin, "fabskollexionn_ledger.csv", "text/csv", use_container_width=True)
        
        xlsx_io = io.BytesIO()
        with pd.ExcelWriter(xlsx_io, engine='openpyxl') as wr:
            export_df.to_excel(wr, index=False, sheet_name="DeliveriesMaster")
        xlsx_io.seek(0)
        col_dl2.download_button("📈 Download Filtered Excel (.xlsx)", xlsx_io, "fabskollexionn_ledger.xlsx", use_container_width=True)
        
        pdf_io = generate_pdf(export_df)
        col_dl3.download_button("📕 Export Filtered PDF", pdf_io, "fabskollexionn_ledger.pdf", "application/pdf", use_container_width=True)
        
        st.markdown("---")
        
        # --- SMART DELETION MANAGEMENT ---
        st.markdown("#### 🚨 Delete Specified Data Rows")
        deletion_options = {
            f"Row ID {row['id']} | {row['Customer_Name']} ({row['Log_Month']}, {row['Day_of_Week']})": row['id']
            for _, row in filtered_df.iterrows()
        }
        
        if deletion_options:
            target_selections = st.multiselect(
                "Select the specific records to remove permanently from storage file:", 
                options=list(deletion_options.keys())
            )
            
            if st.button("🗑️ Drop Selected Rows Permanently", type="secondary"):
                if target_selections:
                    ids_to_delete = [deletion_options[item] for item in target_selections]
                    delete_orders_from_db(ids_to_delete)
                    st.toast("Selected rows dropped from database file successfully.")
                    st.rerun()
        else:
            st.info("No matching rows found to delete based on your current filters.")
        
        st.markdown("---")
        st.markdown("#### 👁️ Live Filtered DataFrame Matrix")
        st.dataframe(export_df, use_container_width=True)
        
    else:
        st.info("The database storage file is currently empty. Log verified orders inside the quick paste workspace tab.")

# --- TAB 3: CUSTOMER PATRONAGE DASHBOARD ---
with tab_dash:
    st.markdown(f"### <span style='color:{accent_color}'>🏆 Fabskollexionn Customer Loyalty Insights</span>", unsafe_allow_html=True)
    
    dash_df = load_orders_from_db()
    
    if not dash_df.empty:
        total_orders = len(dash_df)
        unique_customers = dash_df['Customer_Phone'].nunique()
        repeat_customers = sum(dash_df['Customer_Phone'].value_counts() > 1)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("📦 Total Orders Handled", total_orders)
        with col_m2:
            st.metric("👥 Total Unique Customers", unique_customers)
        with col_m3:
            st.metric("🔄 Loyal Repeat Customers", repeat_customers)
            
        st.markdown("---")
        
        st.markdown("#### 📈 Customer Patronage Leaderboard")
        st.markdown("This live table ranks your customers based on their unique phone numbers.")
        
        leaderboard = dash_df.groupby('Customer_Phone').agg(
            Customer_Name=('Customer_Name', 'first'),
            Total_Patronage_Count=('id', 'count')
        ).reset_index()
        
        leaderboard = leaderboard.sort_values(by='Total_Patronage_Count', ascending=False).reset_index(drop=True)
        leaderboard = leaderboard[["Customer_Name", "Customer_Phone", "Total_Patronage_Count"]]
        leaderboard.columns = ["👑 Customer Name Reference", "📞 Unique Phone Number", "🛍️ Times Patronized"]
        
        vip_customer = leaderboard.iloc[0]["👑 Customer Name Reference"]
        vip_phone = leaderboard.iloc[0]["📞 Unique Phone Number"]
        vip_count = leaderboard.iloc[0]["🛍️ Times Patronized"]
        
        # High contrast fallback colors for dynamic loyalty alert box components
        alert_box_bg = "#1E293B" if st.session_state.theme_dark else "#E2E8F0"
        alert_text_base = "#FFFFFF" if st.session_state.theme_dark else "#1E293B"
        
        st.markdown(f"""
        <div style="background-color: {alert_box_bg}; border-left: 5px solid #38BDF8; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
            <span style="color: #38BDF8; font-weight: bold;">✨ VIP Customer Alert:</span><br>
            <span style="color: {alert_text_base};">The customer with phone number <strong>{vip_phone}</strong> ({vip_customer}) is your top patron, ordering <strong>{vip_count} times</strong>!</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.dataframe(leaderboard, use_container_width=True)
        
    else:
        st.info("No analytics data available yet. Once you begin saving order entries in Tab 1, your loyalty metrics will populate here automatically.")
