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
    """Initializes the local database file and creates the table if it doesn't exist."""
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
    conn.commit()
    conn.close()

def save_order_to_db(order_dict):
    """Inserts a new parsed order row directly onto the disk storage."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (Time_Log, Customer_Name, Customer_Phone, Receiver_Name, Delivery_Address, Receiver_Phone, Status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        order_dict["Time_Log"], order_dict["Customer_Name"], order_dict["Customer_Phone"],
        order_dict["Receiver_Name"], order_dict["Delivery_Address"], order_dict["Receiver_Phone"], order_dict["Status"]
    ))
    conn.commit()
    conn.close()

def load_orders_from_db():
    """Loads all saved rows directly into a clean Pandas DataFrame."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM orders", conn)
    conn.close()
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

# Initialize the database file upon bootup
init_db()


# --- FIXED HIGH-CONTRAST PDF GENERATOR WITH AUTO-WRAPPING ---
def generate_pdf(dataframe):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor("#1E3A8A"), alignment=1 
    )
    header_cell_style = ParagraphStyle(
        'HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.whitesmoke, alignment=1
    )
    body_cell_style = ParagraphStyle(
        'BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor("#1E293B"), alignment=1
    )
    
    story.append(Paragraph("Fabskollexionn Customer & Delivery Tracker", title_style))
    story.append(Spacer(1, 15))
    
    # Exclude the internal SQLite 'id' column from the printed PDF report
    pdf_df = dataframe.drop(columns=["id"], errors="ignore")
    
    columns = list(pdf_df.columns)
    header_row = [Paragraph(str(col).replace("_", " "), header_cell_style) for col in columns]
    data = [header_row] 
    
    for _, row in pdf_df.iterrows():
        body_row = [Paragraph(str(val), body_cell_style) for val in row.values]
        data.append(body_row)
        
    column_widths = [65, 80, 80, 80, 152, 65, 50]
    t = Table(data, colWidths=column_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
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
        "Delivery_Address": r"(?:Address|Delivery\s*Address):\s*(.*)",
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

# --- FIXED DUAL THEME MECHANICS ---
theme_choice = st.radio("🌓 Toggle Workspace Theme:", ["Light Mode", "Dark Mode"], horizontal=True)

if theme_choice == "Dark Mode":
    text_color = "#FFFFFF"
    accent_color = "#38BDF8"
    st.markdown(f"""
        <style>
        .stApp {{ background-color: #0F172A !important; color: {text_color} !important; }}
        h1, h2, h3, h4, h5, h6, p, label, span, [data-testid="stMarkdownContainer"] p {{ color: {text_color} !important; font-weight: 500; }}
        textarea {{ background-color: #1E293B !important; color: #FFFFFF !important; border: 1px solid #475569 !important; font-size: 16px !important; }}
        .stTabs [data-baseweb="tab"] {{ color: #94A3B8 !important; }}
        .stTabs [aria-selected="true"] {{ color: {accent_color} !important; font-weight: bold !important; }}
        </style>
    """, unsafe_allow_html=True)
else:
    accent_color = "#1E3A8A"
    st.markdown("""
        <style>
        .stApp { background-color: #F8FAFC !important; color: #1E293B !important; }
        textarea { background-color: #FFFFFF !important; color: #1E293B !important; border: 1px solid #CBD5E1 !important; }
        </style>
    """, unsafe_allow_html=True)

st.title("🛍️ Fabskollexionn Customer & Delivery Tracker")
st.markdown("Copy, paste, and permanently lock data rows onto local database storage.")
st.markdown("---")

# Navigation Tabs Framework with Added Analytics Tab
tab_paste, tab_view, tab_dash = st.tabs(["📥 Quick Paste Workspace", "📊 View Data & Cloud Exports", "🏆 Patronage Dashboard"])

# --- TAB 1: PASTE WORKSPACE (BACKEND WRITING) ---
with tab_paste:
    st.markdown(f"### <span style='color:{accent_color}'>Paste Raw Customer Dispatch Block</span>", unsafe_allow_html=True)
    
    placeholder_text = (
        "Customer Name: Adefarasin John\n"
        "Customer Phone No: 09071234567\n"
        "Receiver Name: Pelumi Odulaja\n"
        "Address: 10 Surulere, Lagos State\n"
        "Receiver Phone No: 08081234567"
    )
    
    raw_pasted_text = st.text_area("Drop plain text string block here:", height=200, placeholder=placeholder_text)
    
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
                timestamp_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                final_row = {
                    "Time_Log": timestamp_log,
                    "Customer_Name": parsed_data["Customer_Name"],
                    "Customer_Phone": parsed_data["Customer_Phone"],
                    "Receiver_Name": parsed_data["Receiver_Name"],
                    "Delivery_Address": parsed_data["Delivery_Address"],
                    "Receiver_Phone": parsed_data["Receiver_Phone"],
                    "Status": f"{payment_condition} ({source_channel})"
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
                    f"📍 Target Address: {final_row['Delivery_Address']}\n"
                    f"📞 Delivery Hotline: {final_row['Receiver_Phone']}\n\n"
                    f"Thank you for shopping with Fabskollexionn! 🛍️"
                )
                st.text_area("Copy and send directly to customer:", value=outbound_receipt, height=130)
            else:
                st.error("Parse Error: Could not extract details. Check text tags.")
        else:
            st.error("Text field is empty.")

# --- TAB 2: DATA REGISTRY ENGINE (WITH DYNAMIC FILTERING & DELETION) ---
with tab_view:
    st.markdown(f"### <span style='color:{accent_color}'>View Data & File Exporters</span>", unsafe_allow_html=True)
    
    current_ledger_df = load_orders_from_db()
    
    if not current_ledger_df.empty:
        st.markdown("#### 🔍 Quick Search Filter")
        search_query = st.text_input(
            "Search by Customer Name, Receiver Name, Phone Number, or Address:", 
            placeholder="Type anything to filter instantly..."
        ).strip().lower()
        
        if search_query:
            filtered_df = current_ledger_df[
                current_ledger_df['Customer_Name'].str.lower().str.contains(search_query, na=False) |
                current_ledger_df['Receiver_Name'].str.lower().str.contains(search_query, na=False) |
                current_ledger_df['Customer_Phone'].str.lower().str.contains(search_query, na=False) |
                current_ledger_df['Receiver_Phone'].str.lower().str.contains(search_query, na=False) |
                current_ledger_df['Delivery_Address'].str.lower().str.contains(search_query, na=False)
            ]
            st.caption(f"Showing {len(filtered_df)} of {len(current_ledger_df)} records matching '{search_query}'")
        else:
            filtered_df = current_ledger_df.copy()

        col_dl1, col_dl2, col_dl3 = st.columns(3)
        export_df = filtered_df.drop(columns=["id"], errors="ignore")
        
        csv_bin = export_df.to_csv(index=False).encode('utf-8')
        col_dl1.download_button("📄 Download Filtered CSV", csv_bin, "fabskollexionn_ledger.csv", "text/csv", use_container_width=True)
        
        xlsx_io = io.BytesIO()
        with pd.ExcelWriter(xlsx_io, engine='openpyxl') as wr:
            export_df.to_excel(wr, index=False, sheet_name="DeliveriesMaster")
        xlsx_io.seek(0)
        col_dl2.download_button("📈 Download Filtered Excel (.xlsx)", xlsx_io, "fabskollexionn_ledger.xlsx", use_container_width=True)
        
        pdf_io = generate_pdf(filtered_df)
        col_dl3.download_button("📕 Export Filtered PDF", pdf_io, "fabskollexionn_ledger.pdf", "application/pdf", use_container_width=True)
        
        st.markdown("---")
        
        st.markdown("#### 🚨 Delete Specified Data Rows")
        deletion_options = {
            f"Row ID {row['id']} | {row['Customer_Name']} ➡️ {row['Receiver_Name']} ({row['Time_Log']})": row['id']
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
            st.info("No matching rows found to delete based on your current search query.")
        
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
        unique_customers = dash_df['Customer_Name'].nunique()
        repeat_customers = sum(dash_df['Customer_Name'].value_counts() > 1)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("📦 Total Orders Handled", total_orders)
        with col_m2:
            st.metric("👥 Total Unique Customers", unique_customers)
        with col_m3:
            st.metric("🔄 Loyal Repeat Customers", repeat_customers)
            
        st.markdown("---")
        
        st.markdown("#### 📈 Customer Patronage Leaderboard")
        st.markdown("This live table ranks your customers based on how many times they have placed orders.")
        
        leaderboard = dash_df.groupby(['Customer_Name', 'Customer_Phone']).size().reset_index(name='Total_Patronage_Count')
        leaderboard = leaderboard.sort_values(by='Total_Patronage_Count', ascending=False).reset_index(drop=True)
        leaderboard.columns = ["👑 Customer Name", "📞 Phone / Contact Channel", "🛍️ Times Patronized"]
        
        vip_customer = leaderboard.iloc[0]["👑 Customer Name"]
        vip_count = leaderboard.iloc[0]["🛍️ Times Patronized"]
        
        st.markdown(f"""
        <div style="background-color: #1E293B; border-left: 5px solid #38BDF8; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
            <span style="color: #38BDF8; font-weight: bold;">✨ VIP Customer Alert:</span><br>
            <strong style="color: white; font-size: 18px;">{vip_customer}</strong> is currently your top customer, patronizing your brand <strong>{vip_count} times</strong>!
        </div>
        """, unsafe_allow_html=True)
        
        st.dataframe(leaderboard, use_container_width=True)
        
    else:
        st.info("No analytics data available yet. Once you begin saving order entries in Tab 1, your loyalty metrics will populate here automatically.")
