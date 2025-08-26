import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import zipfile
import os

# Helper to make column names unique
def make_unique_columns(columns):
    seen = {}
    new_columns = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            new_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_columns.append(col)
    return new_columns

# Helper to reset session state
def reset_app():
    st.session_state.clear()
    st.experimental_rerun()

# Streamlit UI
st.set_page_config(layout="wide")
st.sidebar.title("PDF Table Extractor")

# Reset button
if st.sidebar.button("Reset App"):
    reset_app()

st.title("PDF Table Extractor")

# Upload and Options
uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")
header_option = st.radio("Where are headers present?", ["All Pages", "Only First Page"], index=0)

# PDF Processing
if uploaded_file is not None:
    if "last_uploaded_filename" not in st.session_state or st.session_state.last_uploaded_filename != uploaded_file.name:
        st.session_state.pdf_data = {}
        st.session_state.selected_page = 1
        st.session_state.last_uploaded_filename = uploaded_file.name

        try:
            with st.spinner("Extracting tables from PDF..."):
                with pdfplumber.open(uploaded_file) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        image = page.to_image(resolution=72).original  # Lower resolution for performance
                        extracted_tables = page.extract_tables()
                        page_tables = []
                        for table_num, table in enumerate(extracted_tables):
                            if table:
                                if header_option == "All Pages" or (header_option == "Only First Page" and page_num == 0):
                                    headers = make_unique_columns(table[0])
                                    df = pd.DataFrame(table[1:], columns=headers)
                                else:
                                    df = pd.DataFrame(table)
                                label = f"Page {page_num + 1} - Table {table_num + 1}"
                                page_tables.append((label, df))
                        st.session_state.pdf_data[page_num + 1] = {
                            "image": image,
                            "tables": page_tables
                        }
        except Exception as e:
            st.error(f"Failed to process PDF: {e}")
            st.session_state.pdf_data = {}

# Table Selection and Export
if "pdf_data" in st.session_state and st.session_state.pdf_data:
    st.subheader("Table Selection and Export")
    all_tables = [df for page in st.session_state.pdf_data.values() for _, df in page["tables"]]
    table_labels = [label for page in st.session_state.pdf_data.values() for label, _ in page["tables"]]

    select_all = st.checkbox("Select All Tables")
    if select_all:
        selected_tables = all_tables
    else:
        selected_labels = st.multiselect("Select tables to combine:", options=table_labels)
        selected_tables = [df for label, df in zip(table_labels, all_tables) if label in selected_labels]

    if selected_tables:
        combined_df = pd.concat(selected_tables, ignore_index=True)
        st.subheader("Combined Table")
        st.dataframe(combined_df)

        # Download as CSV
        csv = combined_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv, file_name="combined_table.csv", mime="text/csv")

        # Download as Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            combined_df.to_excel(writer, index=False, sheet_name='Sheet1')
        st.download_button("Download Excel", data=output.getvalue(), file_name="combined_table.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Export all tables as individual CSVs in ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
            for label, df in zip(table_labels, all_tables):
                csv_data = df.to_csv(index=False)
                zip_file.writestr(f"{label}.csv", csv_data)
        st.download_button("Download All Tables as ZIP", data=zip_buffer.getvalue(), file_name="all_tables.zip", mime="application/zip")

# Page Viewer
if "pdf_data" in st.session_state and st.session_state.pdf_data:
    st.markdown("---")
    st.subheader("Page Viewer")
    col1, col2 = st.columns([1, 3], gap="medium")

    with col1:
        st.markdown("### Page Thumbnails")
        for i, page in st.session_state.pdf_data.items():
            if st.button(f"Page {i}"):
                st.session_state.selected_page = i
            st.image(page["image"], caption=f"Page {i}", use_container_width=True)

    with col2:
        selected_page = st.session_state.get("selected_page", 1)
        st.markdown("### Tables from Selected Page")
        for label, df in st.session_state.pdf_data[selected_page]["tables"]:
            with st.expander(label):
                st.dataframe(df)
else:
    st.info("Please upload a PDF to begin.")
