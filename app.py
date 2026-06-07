import re
import pandas as pd
import streamlit as st
from datetime import datetime

def parse_social_order(text_block):
    """Advanced parser separating Customer, Receiver, and Platform details."""
    platform = "WhatsApp"
    if "ig:" in text_block.lower() or "instagram" in text_block.lower():
        platform = "Instagram"
    elif "fb:" in text_block.lower() or "facebook" in text_block.lower():
        platform = "Facebook"
    elif "tt:" in text_block.lower() or "tiktok" in text_block.lower():
        platform = "TikTok"

    cust_name = re.search(r"(?:Customer Name|Buyer|Sender):\s*(.*)", text_block, re.IGNORECASE)
    username = re.search(r"(?:Username|Handle|IG|TikTok):\s*(.*)", text_block, re.IGNORECASE)
    cust_phone = re.search(r"(?:Customer Phone|Buyer Phone):\s*([\+\d\s-]+)", text_block, re.IGNORECASE)
    
    recv_name = re.search(r"(?:Receiver Name|Recipient|Name):\s*(.*)", text_block, re.IGNORECASE)
    recv_phone = re.search(r"(?:Receiver Phone|Phone No|Phone):\s*([\+\d\s-]+)", text_block, re.IGNORECASE)
    address = re.search(r"(?:Address|Delivery Address):\s*(.*)", text_block, re.IGNORECASE)
    
    c_name = cust_name.group(1).strip() if cust_name else "Same as Receiver"
    u_handle = username.group(1).strip() if username else "Not Provided"
    c_phone = cust_phone.group(1).strip() if cust_phone else "Not Provided"
    
    r_name = recv_name.group(1).strip() if recv_name else "Unknown"
    r_phone = recv_phone.group(1).strip() if recv_phone else "Unknown"
    addr = address.group(1).strip() if address else "Unknown"
    
    if c_name.lower() == "same as receiver" or not cust_name:
        if r_name != "Unknown":
            c_name = r_name

    # Basic normalization for standard formatting
    if r_phone != "Unknown":
        r_phone = r_phone.replace(" ", "").replace("-", "")
        if r_phone.startswith("+234"):
            r_phone = "0" + r_phone[4:]

    return {
        "Order_ID": datetime.now().strftime("%H%M%S"), # Quick unique ID based on time
        "Order_Date": datetime.now().strftime("%Y-%m-%d"),
        "Platform": platform,
        "Customer_Name": c_name,
        "Social_Handle": u_handle,
        "Customer_Phone": c_phone,
        "Receiver_Name": r_name,
        "Receiver_Phone": r_phone,
        "Delivery_Address": addr,
        "Payment_Status": "Pending"
    }

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Data Growth Lab | Master Ledger", page_icon="📈", layout="wide")

st.title("📈 Data Growth Lab: Master Order Ledger")
st.subheader("Process multiple orders sequentially and build a persistent database.")
st.markdown("---")

# --- INITIALIZE SESSION STATE MEMORY ---
# This checks if our master order list exists. If not, it creates a clean list once.
if "master_orders" not in st.session_state:
    st.session_state.master_orders = []

# Split Layout
col1, col2 = st.columns([1, 1.2])

with col1:
    st.markdown("### 📥 Input Order Details")
    user_input = st.text_area("Paste chat block here:", height=180, placeholder="Name: Pelumi...\nAddress: Ibafo...")
    
    payment_received = st.checkbox("💳 Payment Confirmed by Vendor", value=False)
    
    # Process Button Action
    if st.button("⚡ Process & Append Order", type="primary"):
        if user_input.strip():
            # 1. Parse the raw text into a dict
            new_record = parse_social_order(user_input)
            
            # 2. Update payment status based on verification toggle
            if payment_received:
                new_record["Payment_Status"] = "Paid"
                
                # 3. APPEND CRITICAL STEP: Add directly to the running list in memory
                st.session_state.master_orders.append(new_record)
                st.success(f"🎉 Success! Appended record for {new_record['Receiver_Name']} to the next line.")
            else:
                st.error("❌ Truth Mode Block: Order not saved! You must verify and check 'Payment Confirmed' before appending to the database.")
            
            # 4. Draft Outbound Notification text block
            st.markdown("### ✉️ Confirmation Message (Ready to Send)")
            greeting = new_record["Customer_Name"]
            success_msg = (
                f"Hello {greeting},\n\n"
                f"Your payment has been received! 🛍️\n"
                f"Order Details Saved:\n"
                f"📦 To: {new_record['Receiver_Name']}\n"
                f"📍 Address: {new_record['Delivery_Address']}\n"
                f"📞 Contact: {new_record['Receiver_Phone']}\n\n"
                f"Thanks for your business!"
            )
            st.text_area("Copy and paste to customer:", value=success_msg, height=140)
        else:
            st.error("Please paste the customer text first.")

with col2:
    st.markdown("### 📑 Active Database Ledger")
    
    # Render the accumulated list if it contains records
    if st.session_state.master_orders:
        # Convert our persistent session state list into a readable Pandas DataFrame
        master_df = pd.DataFrame(st.session_state.master_orders)
        
        # Display the complete running database
        st.dataframe(master_df, use_container_width=True)
        
        # Action Buttons row
        btn_col1, btn_col2 = st.columns([1, 1])
        
        with btn_col1:
            # Download entire active sheet
            csv_data = master_df.to_csv(index=False).encode('utf-8')
            current_date = datetime.now().strftime("%Y_%m_%d")
            st.download_button(
                label="📥 Download Master CSV File",
                data=csv_data,
                file_name=f"datagrowthlab_ledger_{current_date}.csv",
                mime='text/csv',
                use_container_width=True
            )
            
        with btn_col2:
            # Clear memory button to reset the list for a new batch
            if st.button("🗑️ Clear Active Ledger Memory", type="secondary", use_container_width=True):
                st.session_state.master_orders = []
                st.rerun()
                
    else:
        st.info("The ledger is currently empty. Process confirmed payments on the left to build the dataset rows.")
