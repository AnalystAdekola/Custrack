import re
import pandas as pd
import streamlit as st
from datetime import datetime

def smart_parse(text_block):
    """
    Smart extraction engine that recognizes phone numbers, social handles,
    and addresses without relying on strict 'Label:' formats.
    """
    lines = [line.strip() for line in text_block.split('\n') if line.strip()]
    
    # 1. Identify Platform
    platform = "WhatsApp"
    text_lower = text_block.lower()
    if any(k in text_lower for k in ["ig", "instagram", "insta"]): platform = "Instagram"
    elif any(k in text_lower for k in ["fb", "facebook"]): platform = "Facebook"
    elif any(k in text_lower for k in ["tt", "tiktok"]): platform = "TikTok"

    # 2. Extract Social Handles (Looking for @ symbol)
    handle_match = re.search(r"@([A-Za-z0-9_.]+)", text_block)
    social_handle = f"@{handle_match.group(1)}" if handle_match else "Not Provided"

    # 3. Extract All Phone Numbers (Looking for sequences of 10-14 digits)
    # This catches 090..., 080..., +234... with or without spaces/dashes
    phone_pattern = r"(?:\+?234|0)[789][01]\d[\s-]?\d{3}[\s-]?\d{4}"
    phones = re.findall(phone_pattern, text_block)
    
    # Standardize extracted numbers to local format
    clean_phones = []
    for p in phones:
        nums = p.replace(" ", "").replace("-", "")
        if nums.startswith("+234"):
            nums = "0" + nums[4:]
        clean_phones.append(nums)
    
    # Map customer vs receiver phone numbers based on discovery order
    cust_phone = clean_phones[0] if len(clean_phones) > 0 else "Unknown"
    recv_phone = clean_phones[1] if len(clean_phones) > 1 else cust_phone

    # 4. Extract Address by Keyword Scoring
    # We look for lines containing common address markers or local landmarks
    address_keywords = [
        "street", "st", "avenue", "ave", "road", "rd", "way", "close", "cls",
        "lagos", "ikeja", "surulere", "lekki", "yaba", "vi", "island", "mainland", "ibafo", "ketu"
    ]
    
    delivery_address = "Unknown"
    max_score = 0
    
    for line in lines:
        line_lower = line.lower()
        # Count how many address keywords match this line
        score = sum(1 for kw in address_keywords if kw in line_lower)
        # Give extra points if the line contains numbers (like a street number)
        if any(char.isdigit() for char in line):
            score += 1
            
        if score > max_score and score >= 2:  # Must match at least 2 indicators
            max_score = score
            delivery_address = line

    # 5. Extract Names (Fallback Logic)
    # Simple heuristic: Lines that aren't the address or phone number are likely names
    remaining_lines = []
    for line in lines:
        if line != delivery_address and not any(p in line for p in phones) and "@" not in line and "platform" not in line.lower():
            # Strip out loose greeting words
            clean_line = re.sub(r"(hey|hello|hi|sis|dear|buyer|sender|customer|name|receiver)[:,\s]*", "", line, flags=re.IGNORECASE).strip()
            if clean_line:
                remaining_lines.append(clean_line)

    cust_name = remaining_lines[0] if len(remaining_lines) > 0 else "Unknown"
    recv_name = remaining_lines[1] if len(remaining_lines) > 1 else cust_name

    return {
        "Order_ID": datetime.now().strftime("%H%M%S"),
        "Date_Logged": datetime.now().strftime("%Y-%m-%d"),
        "Platform": platform,
        "Customer_Name": cust_name,
        "Social_Handle": social_handle,
        "Customer_Phone": cust_phone,
        "Receiver_Name": recv_name,
        "Receiver_Phone": recv_phone,
        "Delivery_Address": delivery_address,
        "Payment_Status": "Pending"
    }

# --- STREAMLIT UI ---
st.set_page_config(page_title="Data Growth Lab | Smart Engine", page_icon="📈", layout="wide")

st.title("📈 Data Growth Lab: Smart Order Engine")
st.subheader("Zero Labels Required. The engine detects fields automatically from raw paragraphs.")
st.markdown("---")

if "master_orders" not in st.session_state:
    st.session_state.master_orders = []

col1, col2 = st.columns([1, 1.2])

with col1:
    st.markdown("### 📥 Input Unstructured Chat")
    user_input = st.text_area("Paste the raw text block here:", height=200, 
                          placeholder="Example:\nSend a bag to Bukola Amusan. Delivery address is 12 Allen Avenue, Ikeja. Reach her on 08022334455. My handle is @bisi_chic")
    
    payment_received = st.checkbox("💳 Payment Confirmed by Vendor", value=False)
    
    if st.button("⚡ Smart Parse & Save", type="primary"):
        if user_input.strip():
            new_record = smart_parse(user_input)
            
            if payment_received:
                new_record["Payment_Status"] = "Paid"
                st.session_state.master_orders.append(new_record)
                st.success(f"🎉 Saved! Detected Address: '{new_record['Delivery_Address']}'")
            else:
                st.error("❌ Order not saved. Check 'Payment Confirmed' first.")
                
            # Outbound receipt generator
            st.markdown("### ✉️ Confirmation Message")
            success_msg = (
                f"Hello {new_record['Customer_Name']},\n\n"
                f"Payment verified! Your order details have been saved:\n"
                f"📦 To: {new_record['Receiver_Name']}\n"
                f"📍 Address: {new_record['Delivery_Address']}\n"
                f"📞 Contact: {new_record['Receiver_Phone']}\n\n"
                f"Thanks for shopping with us!"
            )
            st.text_area("Copy message:", value=success_msg, height=130)
        else:
            st.error("Please paste text data first.")

with col2:
    st.markdown("### 📑 Dynamic Database Ledger")
    if st.session_state.master_orders:
        master_df = pd.DataFrame(st.session_state.master_orders)
        st.dataframe(master_df, use_container_width=True)
        
        csv_data = master_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Master CSV File", csv_data, f"smart_ledger_{datetime.now().strftime('%m_%d')}.csv", "text/csv")
        
        if st.button("🗑️ Clear Memory"):
            st.session_state.master_orders = []
            st.rerun()
    else:
        st.info("The ledger sheet is empty. Ready for rows.")
