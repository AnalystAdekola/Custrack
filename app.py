import re
import pandas as pd
import streamlit as st
from datetime import datetime
import io

# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- HIGH-CONTRAST PDF GENERATOR ---
def generate_pdf(dataframe):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=1 
    )
    
    story.append(Paragraph("Fabskollexionn Customer & Delivery Tracker", title_style))
    story.append(Spacer(1, 15))
    
    columns = list(dataframe.columns)
    data = [columns] 
    
    for _, row in dataframe.iterrows():
        data.append([str(val) for val in row.values])
        
    t = Table(data, colWidths=[65, 80, 80, 80, 110, 80, 65])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F3F4F6")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E5E7EB")),
        ('FONTSIZE', (0,1), (-1,-1), 8),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- REGEX EXTRACTOR ENGINE ---
def extract_order_details(text_block):
    """
    Looks for the target variables inside the pasted block,
    regardless of the order they appear in.
    """
    # Regex compilation to cleanly snap up everything following the label up to the next newline
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
        
    # Validation optimization fallback logic
    if extracted["Receiver_Name"] == "Not Provided" or not extracted["Receiver_Name"]:
        extracted["Receiver_Name"] = extracted["Customer_Name"]
    if extracted["Receiver_Phone"] == "Not Provided" or not extracted["Receiver_Phone"]:
        extracted["Receiver_Phone"] = extracted["Customer_Phone"]
        
    return extracted

# --- STREAMLIT PAGE SETUP ---
st.set_page_config(
    page_title="Fabskollexionn Tracker", 
    page_icon="🛍️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- MASTER SESSIONS INITIALIZATION ---
if "tracker_db" not in st.session_state:
    st.session_state.tracker_db = pd.DataFrame(columns=[
        "Time_Log", "Customer_Name", "Customer_Phone", "Receiver_Name", "Delivery_Address", "Receiver_Phone", "Status"
    ])

# --- FIXED DUAL THEME MECHANICS (High Contrast Injection) ---
if "theme" not in st.session_state:
    st.session_state.theme = "Light Mode"

# Simple clear radio controller for UI state swapping
theme_choice = st.radio("🌓 Toggle Workspace Theme:", ["Light Mode", "Dark Mode"], horizontal=True)

if theme_choice == "Dark Mode":
    # Strong accessibility contrast definitions for Dark theme
    text_color = "#FFFFFF"      # Crisp stark white text
    accent_color = "#38BDF8"    # Bright electric sky blue for highlights
    card_bg = "#1E293B"          # Deep Slate Card backing
    
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
    # Standard clean Light theme 
    text_color = "#1E293B"
    accent_color = "#1E3A8A"
    card_bg = "#FFFFFF"
    st.markdown("""
        <style>
        .stApp { background-color: #F8FAFC !important; color: #1E293B !important; }
        textarea { background-color: #FFFFFF !important; color: #1E293B !important; border: 1px solid #CBD5E1 !important; }
        </style>
    """, unsafe_allow_html=True)

# --- APPLICATION HEADER BAR ---
st.title("🛍️ Fabskollexionn Customer & Delivery Tracker")
st.markdown("Copy, paste, and commit unstructured customer lists straight into your core operational dataset.")
st.markdown("---")

# Navigation Tabs Framework
tab_paste, tab_view = st.tabs(["📥 Quick Paste Workspace", "📊 View Data & Cloud Exports"])

# --- TAB 1: PASTE PARSER ENGINE WORKSPACE ---
with tab_paste:
    st.markdown(f"### <span style='color:{accent_color}'>Paste Raw Customer Dispatch Block</span>", unsafe_allow_html=True)
    
    placeholder_text = (
        "Customer Name: Adefarasin John\n"
        "Customer Phone No: 09071234567\n"
        "Receiver Name: Pelumi Odulaja\n"
        "Address: 10 Surulere, Lagos State\n"
        "Receiver Phone No: 08081234567"
    )
    
    raw_pasted_text = st.text_area(
        "Drop the plain text string block here directly from your DMs or chats:", 
        height=220, 
        placeholder=placeholder_text
    )
    
    # Context Processing Parameters
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        payment_condition = st.selectbox("💳 Direct Ledger Payment Status", ["Paid", "Pending Verify", "COD - Cash on Delivery"])
    with col_opt2:
        source_channel = st.selectbox("📱 Marketplace Origin Channel", ["Instagram DMs", "WhatsApp Business", "TikTok Direct", "Facebook DM"])
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("⚡ Parse Block & Commit Row", type="primary", use_container_width=True):
        if raw_pasted_text.strip():
            # Trigger parsing dictionary processing framework
            parsed_data = extract_order_details(raw_pasted_text)
            
            # Defensive check: verify that at least a name or address was extracted
            if parsed_data["Customer_Name"] != "Not Provided" or parsed_data["Delivery_Address"] != "Not Provided":
                timestamp_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Assemble structured ledger row data matrix map
                final_row = {
                    "Time_Log": timestamp_log,
                    "Customer_Name": parsed_data["Customer_Name"],
                    "Customer_Phone": parsed_data["Customer_Phone"],
                    "Receiver_Name": parsed_data["Receiver_Name"],
                    "Delivery_Address": parsed_data["Delivery_Address"],
                    "Receiver_Phone": parsed_data["Receiver_Phone"],
                    "Status": f"{payment_condition} ({source_channel})"
                }
                
                # Commit seamlessly into persistent memory block stack
                st.session_state.tracker_db = pd.concat([st.session_state.tracker_db, pd.DataFrame([final_row])], ignore_index=True)
                
                # High-contrast execution container notice layout
                st.markdown(f"""
                <div style="background-color: #10B981; padding: 15px; border-radius: 8px; color: white; font-weight: bold; margin-bottom: 15px;">
                    🎯 Success! Record saved smoothly for {final_row['Customer_Name']} at {final_row['Time_Log']}.
                </div>
                """, unsafe_allow_html=True)
                
                # Instantly spit back a validation receipt copy box
                st.markdown("#### Outbound Confirmation Copy Block")
                outbound_receipt = (
                    f"Hello {final_row['Customer_Name']},\n\n"
                    f"We've successfully logged your order delivery details! ✨\n\n"
                    f"📦 Dispatch To: {final_row['Receiver_Name']}\n"
                    f"📍 Target Address: {final_row['Delivery_Address']}\n"
                    f"📞 Delivery Hotline: {final_row['Receiver_Phone']}\n\n"
                    f"Thank you for shopping with Fabskollexionn! 🛍️"
                )
                st.text_area("Copy and send directly to customer chat window:", value=outbound_receipt, height=140)
            else:
                st.markdown("""
                <div style="background-color: #EF4444; padding: 15px; border-radius: 8px; color: white; font-weight: bold;">
                    ⚠️ Parse Error: Could not extract details. Make sure your text contains indicators like 'Customer Name:' and 'Address:'.
                </div>
                """, unsafe_allow_html=True)
        else:
            st.error("Text field is currently completely empty.")

# --- TAB 2: DATA REGISTRY ENGINE (VIEW DATA) ---
with tab_view:
    st.markdown(f"### <span style='color:{accent_color}'>View Data & File Exporters</span>", unsafe_allow_html=True)
    
    current_ledger_df = st.session_state.tracker_db
    
    if not current_ledger_df.empty:
        # Export Actions Panel Row
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        
        # CSV Downloader Compilation Engine
        csv_bin = current_ledger_df.to_csv(index=False).encode('utf-8')
        col_dl1.download_button("📄 Download Master CSV File", csv_bin, "fabskollexionn_ledger.csv", "text/csv", use_container_width=True)
        
        # Excel Engine File Generator Loop
        xlsx_io = io.BytesIO()
        with pd.ExcelWriter(xlsx_io, engine='openpyxl') as wr:
            current_ledger_df.to_excel(wr, index=False, sheet_name="DeliveriesMaster")
        xlsx_io.seek(0)
        col_dl2.download_button("📈 Download Excel Ledger (.xlsx)", xlsx_io, "fabskollexionn_ledger.xlsx", use_container_width=True)
        
        # PDF Exporter Engine File Generator Loop
        pdf_io = generate_pdf(current_ledger_df)
        col_dl3.download_button("📕 Export Professional PDF Document", pdf_io, "fabskollexionn_ledger.pdf", "application/pdf", use_container_width=True)
        
        st.markdown("---")
        
        # Row Multi-Selection Drop deletion mechanism
        st.markdown("#### 🚨 Drop Specified Data Rows")
        deletion_registry_options = [f"Index Row {i} | {row['Customer_Name']} ➡️ {row['Receiver_Name']}" for i, row in current_ledger_df.iterrows()]
        target_indices_to_drop = st.multiselect("Select the target data row strings you intend to delete permanently:", options=deletion_registry_options)
        
        if st.button("🗑️ Drop Selection Permanently from Base DataFrame", type="secondary"):
            if target_indices_to_drop:
                clean_target_integers = [int(item.split(" ")[2]) for item in target_indices_to_drop]
                st.session_state.tracker_db = current_ledger_df.drop(clean_target_integers).reset_index(drop=True)
                st.toast("Selected data metrics dropped from session DataFrame frame.")
                st.rerun()
        
        st.markdown("---")
        
        # Render Interactive Full Data Frame Layout (Requirement 8)
        st.markdown("#### 👁️ Current Master DataFrame Matrix")
        st.dataframe(st.session_state.tracker_db, use_container_width=True)
        
    else:
        st.info("The system database ledger dataframe is currently clean and empty. Log verified orders inside the quick paste workspace tab.")
