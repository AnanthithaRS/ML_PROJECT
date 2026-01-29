import streamlit as st
import pandas as pd
import plotly.express as px
from pypdf import PdfReader
from docx import Document
import spacy
from spacy.matcher import PhraseMatcher
import json
import google.genai as genai
import re

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="LegaL Contract Checker", layout="centered")

# Setup Gemini
MODEL_ID = "gemini-2.0-flash"

GEMINI_API_KEY = 'AIzaSyCKLt-I0GiJeHkbA7-8vbUMNpWENjxQ5nQ' # Put your key here
client = genai.Client(api_key=GEMINI_API_KEY)

nlp = spacy.load("en_core_web_sm")

# --- 2. INGESTION LOGIC ---
def ingest_file(uploaded_file):
    raw_text = ""
    if uploaded_file.name.endswith('.pdf'):
        reader = PdfReader(uploaded_file)
        for page in reader.pages:
            raw_text += page.extract_text() + "\n"
    elif uploaded_file.name.endswith('.docx'):
        doc = Document(uploaded_file)
        raw_text = "\n".join([para.text for para in doc.paragraphs])
    return re.sub(r'\s+', ' ', raw_text).strip()

# --- 3. SEGMENTATION LOGIC ---
def segment_clauses(text):
    doc = nlp(text)
    headers = [# --- General Legal & Contracts ---
        "Termination", "Indemnity", "Governing Law", "Jurisdiction", 
        "Payment Terms", "Liability", "Confidentiality", "Force Majeure",
        "Dispute Resolution", "Representations and Warranties",
        
        # --- Partnership & Company Structure ---
        "Capital Contribution", "Profit Sharing", "Partnership Dissolution", 
        "Roles and Responsibilities", "Board Meetings", "Transfer of Shares",
        "Nominee Director", "Memorandum of Association", "Articles of Association",
        
        # --- Intellectual Property (Patents/Trademarks) ---
        "Intellectual Property Rights", "Trademark License", "Patent Assignment",
        "Royalties", "Infringement", "Scope of License",
        
        # --- Registrations & Compliance (MCA, GST, Income Tax) ---
        "GST Registration", "GSTR-1", "GSTR-3B", "Income Tax Return", "ITR-6",
        "FSSAI License", "Food Safety Management", "Form IX",
        "Annual Return", "MGT-7", "AOC-4", "Director KYC", "DIR-3 KYC",
        "MSME Registration", "Udyam Registration",
        
        # --- Rental & Real Estate ---
        "Security Deposit", "Base Rent", "Maintenance Charges", "Demised Premises",
        "Lock-in Period", "Notice Period"]
    clauses = {}
    
    # 1. We search for keywords while ignoring case and handling extra spaces
    for word in headers:
        # This regex looks for a keyword at the start of a line, 
        pattern = rf"(?i)(?:^|\n)[0-9.\s]*({word}.*?)(?=\n[0-9.\s]*(?:{'|'.join(headers)})|$)"
        
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            # We take the content found and clean up extra whitespace
            clauses[word] = re.sub(r'\s+', ' ', matches[0]).strip()
            
    # 2. Safety Fallback: If no keywords found, don't return an empty dict
    if not clauses:
        return {"General Analysis": text[:4000]}
        
    return clauses

# --- 4. GEMINI RISK SCORING & MULTILINGUAL LOGIC ---
def analyze_risk_gemini(header, content):
    prompt = f"""
    Analyze this '{header}' clause for an Indian SME. 
    Return ONLY a JSON object with these keys:
    "score" (1-10), "level" (Low/Medium/High), "issue" (English | Hindi), "advice" (English | Hindi), "alt" (SME-friendly version).
    
    Text: {content}
    """
    
    response = client.models.generate_content(
        model=MODEL_ID, 
        contents=prompt
    )
    
    # Debugging: print to terminal to see raw output
    print(f"DEBUG {header}: {response.text}")

    # Robust cleaning to handle Markdown JSON blocks
    # Uses regex to find the first '{' and last '}'
    raw_text = response.text
    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    
    if json_match:
        clean_json = json_match.group(0)
        return json.loads(clean_json)
    else:
        # Fallback if AI fails to return JSON
        return {
            "score": 0, "level": "Error", 
            "issue": "Failed to parse AI response", 
            "advice": "Try re-uploading", "alt": "N/A"
        }
    
# --- 5. UI LAYOUT ---
st.title("⚖️ AI Legal Assistant (Gemini Free Edition)")
st.markdown("---")

uploaded_file = st.file_uploader("Upload Contract (PDF or DOCX)", type=["pdf", "docx"])

if uploaded_file:
    with st.spinner("Gemini is analyzing your contract..."):
        full_text = ingest_file(uploaded_file)
        segments = segment_clauses(full_text)
        
        results = {}
        for h, c in list(segments.items())[:5]: 
            try:
                results[h] = analyze_risk_gemini(h, c)
            except:
                continue
        
        # 1. Check if we actually have results to display
        if results:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Risk Distribution")
                # Create the DataFrame safely
                df_plot = pd.DataFrame([{"Clause": k, "Score": v['score']} for k, v in results.items()])
                
                # 2. Check if the DataFrame columns are present before plotting
                if not df_plot.empty and 'Clause' in df_plot.columns:
                    fig = px.pie(df_plot, values='Score', names='Clause', hole=0.4, 
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No measurable risk data found to chart.")

            with col2:
                st.subheader("Detailed Breakdown")
                for h, res in results.items():
                    # Your existing color-coded expander logic
                    color = "green" if res['score'] <= 3 else "orange" if res['score'] <= 7 else "red"
                    with st.expander(f"{h} - Risk Score: {res['score']}/10"):
                        st.markdown(f"**Risk Level:** :{color}[{res['level']}]")
                        st.write(f"**Issue:** {res['issue']}")
                        st.write(f"**Advice:** {res['advice']}")
                        st.success(f"**Alternative Clause:**\n{res['alt']}")
        else:
            # 3. Handle the case where no clauses were processed
            st.error("⚠️ No legal clauses were identified or processed. Check your document headers or API connection.")
        