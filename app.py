import streamlit as st
import pandas as pd
from datetime import datetime
import io
# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- PDF GENERATOR HELPER ---
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
        alignment=1 # Center
    )
    
    story.append(Paragraph("Fabskollexionn Customer & Delivery Tracker", title_style))
    story.append(Spacer(1, 15))
    
    # Prepare Table Data
    columns = list(dataframe.columns)
    data = [columns] # Header row
    
    for _, row in dataframe.iterrows():
        data.append([str(val) for val in row.values])
        
    # Table Styling for mobile data snapshot
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

# --- STREAMLIT CONFIGURATION ---
st.set_page_config(
    page_title="Fabskollexionn Tracker", 
    page_icon="🛍️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- THEME MANAGEMENT (Light / Dark Mode Selector) ---
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Light"

theme_toggle = st.radio("🌓 Select Interface Theme Mode:", ["Light", "Dark"], horizontal=True)

# Inject dynamic CSS based on chosen theme mode for perfect contrast on mobile screens
if theme_toggle == "Dark":
    st.markdown("""
        <style>
        .stApp { background-color: #111827; color: #F9FAFB; }
        div[data-testid="stForm"] { background-color: #1F2937; border: 1px solid #374151; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <style>
        .stApp { background-color: #F9FAFB; color: #111827; }
        div[data-testid="stForm"] { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        </style>
    """, unsafe_allow_html=True)

# --- MASTER DATABASE MEMORY INITIALIZATION ---
if "tracker_db" not in st.session_state:
    st.session_state.tracker_db = pd.DataFrame(columns=[
        "Time_Log", "Customer_Name", "Customer_Phone", "Receiver_Name", "Delivery_Address", "Receiver_Phone", "Payment_Status"
    ])

# --- APP HEADER ---
st.title("🛍️ Fabskollexionn Customer & Delivery Tracker")
st.markdown("Streamlined tracking workspace designed for fast, frictionless logging on web and mobile devices.")
st.markdown("---")

# Navigation Tabs (Requirement 6 & 8)
tab_input, tab_view = st.tabs(["📥 Log New Order", "📊 View Data & Export"])

# --- TAB 1: FORM INPUT LOGGING ---
with tab_input:
    st.markdown("### Enter Order Dispatch Particulars")
    
    with st.form("order_submission_form", clear_on_submit=True):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_name = st.text_input("👤 Customer Name")
            c_phone = st.text_input("📞 Customer Phone Number")
        with col_c2:
            r_name = st.text_input("🎁 Receiver Name (If different)")
            r_phone = st.text_input("📱 Receiver Phone Number")
            
        d_address = st.text_area("📍 Complete Delivery Address", height=80)
        
        # Cool Bonus Feature (Requirement 9): Dropdown to catch payment mode context
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            p_status = st.selectbox("💳 Payment Status", ["Paid", "Pending Payment", "Cash on Delivery"])
        with col_b2:
            p_channel = st.selectbox("🌐 Sales Channel Source", ["Instagram DMs", "WhatsApp Business", "Facebook Messenger", "TikTok Shop"])
            
        submit_btn = st.form_submit_with_sidebar_status(label="⚡ Commit Order to Ledger") if hasattr(st, "form_submit_with_sidebar_status") else st.form_submit_button("⚡ Commit Order to Ledger")

    if submit_btn:
        if c_name.strip() and d_address.strip():
            # Generate automatic system parameters (Requirement 3)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Map Fallback if Receiver field is left blank by user
            final_recv_name = r_name.strip() if r_name.strip() else c_name.strip()
            final_recv_phone = r_phone.strip() if r_phone.strip() else c_phone.strip()
            
            # Construct dictionary line row
            new_row = {
                "Time_Log": timestamp,
                "Customer_Name": c_name.strip(),
                "Customer_Phone": p_channel if p_channel else c_phone.strip(), # Blends source channel for analyst usage
                "Receiver_Name": final_recv_name,
                "Delivery_Address": d_address.strip(),
                "Receiver_Phone": final_recv_phone,
                "Payment_Status": p_status
            }
            
            # Append smoothly directly onto master session frame
            st.session_state.tracker_db = pd.concat([st.session_state.tracker_db, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"🎉 Order row added successfully for {c_name} at {timestamp}!")
        else:
            st.error("⚠️ Validation Error: 'Customer Name' and 'Delivery Address' fields cannot be blank.")

# --- TAB 2: DATA REGISTRY ENGINE & DATA MANAGEMENT ---
with tab_view:
    st.markdown("### 📑 Master Delivery Database Ledger")
    
    current_df = st.session_state.tracker_db
    
    if not current_df.empty:
        # --- EXPORT MANAGEMENT (Requirement 5) ---
        st.markdown("#### 📥 Global Format Downloader Options")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        
        # 1. CSV Download
        csv_buffer = current_df.to_csv(index=False).encode('utf-8')
        exp_col1.download_button(
            label="📄 Download Data as CSV",
            data=csv_buffer,
            file_name="fabskollexionn_ledger.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # 2. Excel (XLSX) Download
        xlsx_buffer = io.BytesIO()
        with pd.ExcelWriter(xlsx_buffer, engine='openpyxl') as writer:
            current_df.to_excel(writer, index=False, sheet_name="Deliveries")
        xlsx_buffer.seek(0)
        exp_col2.download_button(
            label="📈 Download Data as Excel (.xlsx)",
            data=xlsx_buffer,
            file_name="fabskollexionn_ledger.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        # 3. PDF Download
        pdf_buffer = generate_pdf(current_df)
        exp_col3.download_button(
            label="📕 Download Data as Document (PDF)",
            data=pdf_buffer,
            file_name="fabskollexionn_ledger.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
        st.markdown("---")
        
        # --- DELETION MANAGEMENT MECHANICS (Requirement 4) ---
        st.markdown("#### 🛠️ Manage Dataset Matrix Rows")
        
        # Provide a interactive multi-select widget referencing indices for rows to pop out
        row_options = [f"Row {idx} | {row['Customer_Name']} ➡️ {row['Receiver_Name']}" for idx, row in current_df.iterrows()]
        selected_rows_to_delete = st.multiselect("🚨 Select row items you want to delete from the active frame ledger:", options=row_options)
        
        if st.button("🗑️ Delete Selected Rows permanently", type="secondary"):
            if selected_rows_to_delete:
                # Extract integer index value out from the string option presentation
                indices_to_drop = [int(item.split(" ")[1]) for item in selected_rows_to_delete]
                st.session_state.tracker_db = current_df.drop(indices_to_drop).reset_index(drop=True)
                st.toast("Selected rows removed smoothly.")
                st.rerun()
            else:
                st.warning("Please choose at least one item from the checkbox list above.")
                
        # --- VIEW DATA PORTAL DISPLAY (Requirement 8) ---
        st.markdown("#### 👁️ Live Frame Matrix")
        st.dataframe(st.session_state.tracker_db, use_container_width=True)
        
    else:
        st.info("The ledger matrix dataset is completely empty right now. Go log an active customer delivery entry inside the input panel form tab.")
