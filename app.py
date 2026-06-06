import re
import pandas as pd
import streamlit as st
from datetime import datetime

# --- CORE LOGIC ---
def parse_customer_chat(text_block):
    """Parses a single raw text block and returns a dictionary."""
    name_pattern = r"(?:Name|Receiver's Name|Recipient):\s*(.*)"
    address_pattern = r"(?:Address|Delivery Address):\s*(.*)"
    phone_pattern = r"(?:Phone No|Phone|Mobile|Number):\s*([\+\d\s-]+)"
    
    name_match = re.search(name_pattern, text_block, re.IGNORECASE)
    address_match = re.search(address_pattern, text_block, re.IGNORECASE)
    phone_match = re.search(phone_pattern, text_block, re.IGNORECASE)
    
    name = name_match.group(1).strip() if name_match else "Unknown"
    address = address_match.group(1).strip() if address_match else "Unknown"
    phone = phone_match.group(1).strip() if phone_match else "Unknown"
    
    if phone != "Unknown":
        phone = phone.replace(" ", "").replace("-", "")
        if phone.startswith("+234"):
            phone = "0" + phone[4:]
        elif phone.startswith("234") and len(phone) > 10:
            phone = "0" + phone[3:]
            
    return {
        "Date_Logged": datetime.now().strftime("%Y-%m-%d"),
        "Customer_Name": name,
        "Delivery_Address": address,
        "Phone_Number": phone
    }

# --- STREAMLIT UI ---
st.set_page_config(page_title="Data Growth Lab | Parser", page_icon="📊", layout="wide")

st.title("📊 Data Growth Lab: Social Commerce Parser")
st.subheader("Turn messy Instagram & WhatsApp checkout texts into clean data instantly.")

st.markdown("---")

# Instruction for the user
st.info("💡 **How to use:** Copy the text blocks from your chat app, paste them into the box below, separate multiple orders with a blank line or double dashes (`--`), and hit Process.")

# Input text area
user_input = st.text_area("Paste your messy chat blocks here:", height=250, 
                          placeholder="Name: Adefarasin John\nAddress: 10 Surulere Lagos\nPhone No: 09071234567\n\n---\n\nName: Odulaja Pelumi\nAddress: 10 Ibafo, Lagos\nPhone No: 08081234567")

if st.button("🚀 Process & Generate Database", type="primary"):
    if user_input.strip():
        # Split blocks by common separators (double newlines or explicit lines/dashes)
        # This regex splits by double new lines or horizontal lines/dashes
        raw_blocks = re.split(r'\n\s*\n|--+', user_input)
        
        # Clean out any empty blocks caused by extra spaces
        raw_blocks = [block.strip() for block in raw_blocks if block.strip()]
        
        parsed_records = []
        for block in raw_blocks:
            # Check if it looks like a valid record containing name or phone
            if "name" in block.lower() or "phone" in block.lower():
                record = parse_customer_chat(block)
                parsed_records.append(record)
        
        if parsed_records:
            # Create DataFrame
            df = pd.DataFrame(parsed_records)
            
            st.success(f"Successfully processed {len(df)} customer records!")
            
            # Display interactive table
            st.dataframe(df, use_container_width=True)
            
            # Generate CSV download
            csv_data = df.to_csv(index=False).encode('utf-8')
            current_date = datetime.now().strftime("%Y_%m_%d")
            
            st.download_button(
                label="📥 Download Clean CSV File",
                data=csv_data,
                file_name=f"datagrowthlab_orders_{current_date}.csv",
                mime='text/csv',
            )
        else:
            st.warning("We couldn't extract any valid data. Ensure fields contain prefixes like 'Name:', 'Address:', and 'Phone No:'.")
    else:
        st.error("The text area is empty. Please paste some data first!")