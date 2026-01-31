import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import google.genai as genai
import re
import io
from groq import Groq

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Financial Health", layout="wide")
API_KEY = "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"# Use your API key here 
client = Groq(api_key=API_KEY)

# --- 2. DATA EXTRACTION LOGIC ---
def extract_bank_data(uploaded_file):
    """Parses bank statements from PDF or CSV."""
    if uploaded_file.name.endswith('.csv'):
        return pd.read_csv(uploaded_file)
    
    elif uploaded_file.name.endswith('.pdf'):
        all_rows = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    all_rows.extend(table)
        
        if not all_rows: return None
        # Use first row as header and subsequent rows as data
        df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        return df

# --- 3. VIRTUAL CFO ENGINE ---
@st.cache_data(show_spinner=False)
def get_cfo_insights(df_summary):
    # Llama-3 70B is excellent for financial reasoning
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a Virtual CFO for Indian SMEs."},
            {"role": "user", "content": f"Analyze this data: {df_summary}"}
        ],
        model="llama-3.3-70b-versatile",
    )
    return chat_completion.choices[0].message.content

# --- 4. UI LAYOUT ---
st.title("💰Financial Health Assessment Tool")
st.info("Upload your bank statement to get an AI-powered financial audit.")

file = st.file_uploader("Upload Bank Statement", type=["csv", "pdf"])

if file:
    with st.spinner("Processing statement..."):
        df = extract_bank_data(file)
        
        if df is not None:
            # Display Raw Data
            with st.expander("View Extracted Data"):
                st.write(df)

            # Analysis Columns
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("📈 Financial Overview")
                st.metric("Total Transactions Detected", len(df))

                # 1. Clean numerical columns (Handling commas and string types)
                # We dynamically find columns that might be 'Amount', 'Debit', or 'Credit'
                for col in df.columns:
                    if any(term in col.lower() for term in ['amount', 'debit', 'credit', 'balance']):
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')

                # 2. Explicit Column Mapping for Plotly
                try:
                    # We use the first column for X (Date/Desc) and the last detected numeric column for Y
                    fig = px.bar(
                        df.head(10), 
                        x=df.columns[0],  # Usually Date or Narration
                        y=df.columns[-1], # Usually Balance or Amount
                        title="Recent Cash Movement",
                        labels={df.columns[0]: "Entry", df.columns[-1]: "Value (INR)"},
                        color_discrete_sequence=['#00CC96']
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.warning(f"Could not render chart: {e}. Showing table instead.")
                    st.table(df.head(10))
                
            with col2:
             st.subheader("🤖 Virtual CFO Insights")
    
    # Create a form to prevent automatic reruns from calling the API
            with st.form("financial_analysis_form"):
                    st.write("Click below to analyze the top 10 transactions.")
                    data_preview = df.head(10).to_string()
        
        # The submit button for the form
                    submit_button = st.form_submit_button("Generate CFO Audit")
        
                    if submit_button:
                        try:
                         with st.spinner("Consulting AI..."):
                           insights = get_cfo_insights(data_preview)
                           st.markdown(insights)
                        except Exception as e:
                         st.error(f"Quota error: Please wait 60 seconds and try again. {e}")
        
        else:
            st.error("Could not extract data. Ensure the PDF contains text-based tables.")
