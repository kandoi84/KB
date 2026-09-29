import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), "src"))

from kb_runtime.live_storage import LiveKBStorage
from kb_runtime.live_query import LiveQueryEngine
from kb_runtime.thesis_wiki import ThesisWiki

# Page config
st.set_page_config(page_title="Indian Equities Live KB", layout="wide")

# Initialize components
@st.cache_resource
def get_kb_components():
    root_dir = Path(".")
    storage = LiveKBStorage(root_dir)
    query_engine = LiveQueryEngine(storage)
    wiki = ThesisWiki(root_dir)
    return storage, query_engine, wiki

storage, query_engine, wiki = get_kb_components()

st.title("📈 Indian Equities Knowledge Base")

# Sidebar: Company Selection
st.sidebar.header("Company Selection")
# Fetch all companies from storage
companies_df = pd.read_sql_query("SELECT isin, symbol FROM companies", storage.conn)
company_list = companies_df["isin"].tolist()
selected_isin = st.sidebar.selectbox("Select Company (ISIN)", company_list)

if not selected_isin:
    st.warning("Please select a company from the sidebar.")
    st.stop()

# Main UI Tabs
tab_metrics, tab_rag, tab_wiki = st.tabs(["📊 Metrics", "🔍 Research (RAG)", "✍️ Thesis Wiki"])

with tab_metrics:
    st.header(f"Financial Metrics for {selected_isin}")
    # Get most recent metrics
    metrics_df = pd.read_sql_query(
        "SELECT metric_name, value, filing_date, period_end FROM metrics WHERE isin = ? ORDER BY filing_date DESC",
        storage.conn, 
        params=(selected_isin,)
    )
    if not metrics_df.empty:
        # Pivot for a cleaner view: Metric Name vs Filing Date
        pivot_df = metrics_df.pivot(index="metric_name", columns="filing_date", values="value")
        st.dataframe(pivot_df, use_container_width=True)
    else:
        st.info("No metrics found for this company.")

with tab_rag:
    st.header("Contextual Research")
    query = st.text_input("Ask a question about the company (e.g., 'What is the capex guidance?')")
    as_of_date = st.date_input("As of date", value=pd.Timestamp.now())
    
    if query:
        with st.spinner("Searching documents..."):
            # In a real app, we'd generate a real embedding here.
            # For now, we use a mock vector as in the CLI.
            import hashlib
            hash_val = int(hashlib.md5(query.encode()).hexdigest(), 16)
            mock_vector = [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(1536)]
            
            results = query_engine.query_context(
                selected_isin, 
                as_of_date.strftime("%Y-%m-%d"), 
                mock_vector
            )
            
            if results:
                for i, res in enumerate(results):
                    with st.expander(f"Source {i+1} (Date: {res['filing_date']})"):
                        st.write(res['text'])
            else:
                st.error("No relevant documents found for this query as of the selected date.")

with tab_wiki:
    st.header("Thesis & Research Notes")
    
    # Thesis Section
    st.subheader("Core Thesis")
    thesis_file = wiki.get_thesis_file(selected_isin)
    if thesis_file.exists():
        current_thesis = thesis_file.read_text(encoding="utf-8")
        new_thesis = st.text_area("Edit Thesis", value=current_thesis, height=300)
        if st.button("Update Thesis"):
            # Note: In this simple version, we append. 
            # To 'edit', we'd need to rewrite the file.
            wiki.update_thesis(selected_isin, new_thesis)
            st.success("Thesis entry added!")
    else:
        st.info("No thesis yet. Start writing below.")
        new_thesis = st.text_area("Initial Thesis")
        if st.button("Save Thesis"):
            wiki.update_thesis(selected_isin, new_thesis)
            st.rerun()

    # Notes Section
    st.divider()
    st.subheader("Research Notes")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        note_id = st.text_input("Note ID (e.g., note_1)")
        links = st.text_input("Links (JSON list of versions, e.g., ['v1'])")
    with col2:
        note_content = st.text_area("Note Content", height=150)
    
    if st.button("Add Note"):
        try:
            link_list = []
            if links:
                import json
                link_list = json.loads(links)
            wiki.add_note(selected_isin, note_id, note_content, link_list)
            st.success("Note added!")
        except Exception as e:
            st.error(f"Error adding note: {e}")

    # List Notes
    st.divider()
    notes = wiki.list_notes(selected_isin)
    if notes:
        for n_path in notes:
            with st.expander(f"📝 {n_path.name}"):
                st.write(wiki.get_note_content(selected_isin, n_path.stem))
    else:
        st.info("No research notes found.")

