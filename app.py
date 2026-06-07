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
        
    column_widths =
