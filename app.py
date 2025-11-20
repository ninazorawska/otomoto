import multiprocessing
try:
    # Fix for Streamlit + Selenium/Multiprocessing on macOS/Linux
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass

import streamlit as st
from dotenv import load_dotenv
import pypdf 
from services.car_search_system import CarSearchService
from utils.tracing import init_tracing

# Load env vars and init tracing
load_dotenv()
init_tracing()

st.set_page_config(
    page_title="CarSearch AI",
    page_icon="🚗",
    layout="wide"
)

# Initialize session state variables
if 'car_service' not in st.session_state:
    st.session_state.car_service = None 
if 'pdf_context' not in st.session_state:
    st.session_state.pdf_context = ""

st.title("🚗 CarSearch AI")

# --- SIDEBAR: PDF DOCUMENT INGESTION ---
with st.sidebar:
    st.header("📁 Document Ingestion")
    st.markdown("Upload a guide or policy to help the AI answer questions (e.g., 'Does this car fit my insurance?').")
    
    uploaded_file = st.file_uploader("Upload Guide/Policy (PDF)", type="pdf")
    
    if uploaded_file:
        try:
            with st.spinner("Processing PDF..."):
                pdf_reader = pypdf.PdfReader(uploaded_file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                st.session_state.pdf_context = text
            st.success(f"✅ Ingested {len(pdf_reader.pages)} pages!")
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
# ---------------------------------------

# Tabs: Search and Chat
tab1, tab2 = st.tabs(["🔍 Search Cars", "💬 Chat About Cars"])

# --- TAB 1: SEARCH ---
with tab1:
    st.header("Search for Cars")
    user_query = st.text_area("Enter search (e.g., 'Fiat Panda under 15k')", height=100)

    if st.button("Search", type="primary"):
        if not user_query.strip():
            st.warning("Please enter a query.")
        else:
            with st.spinner("Searching... (Check the opened browser window!)"):
                # Lazy Initialization: Create Service only when needed to avoid startup errors
                if st.session_state.car_service is None:
                    try:
                        st.session_state.car_service = CarSearchService()
                    except Exception as e:
                        st.error(f"Failed to initialize service: {e}")
                        st.stop()
                
                # 1. Parse Query with LLM
                filters = st.session_state.car_service.parse_query(user_query)
                
                # 2. Scrape Data
                results = st.session_state.car_service.search_cars(filters)
                st.session_state.current_results = results

            # Display Results
            if results:
                st.success(f"Found {len(results)} cars!")
                for car in results:
                    # Layout: Image (Left) | Details (Right)
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 3])
                        
                        with col1:
                            if car.get('image_url') and "http" in car['image_url']:
                                # FIX: Changed 'use_container_width' to 'use_column_width' for compatibility
                                st.image(car['image_url'], use_column_width=True)
                            else:
                                st.caption("No Image Available")
                        
                        with col2:
                            st.subheader(car.get('title', 'No Title'))
                            st.markdown(
                                f"**Price:** €{car.get('price', 0):,} | "
                                f"**Year:** {car.get('year', 'N/A')} | "
                                f"**KM:** {car.get('km', 0):,} km | "
                                f"**Fuel:** {car.get('fuel', 'N/A')}"
                            )
                            if car.get('link'):
                                st.markdown(f"[👉 View Full Listing]({car['link']})")
            else:
                st.warning("No cars found matching your query. Check the terminal for details.")

# --- TAB 2: CHAT ---
with tab2:
    st.header("Chat About Results")
    
    if not st.session_state.get('current_results'):
        st.info("Please perform a search in the 'Search Cars' tab first.")
    else:
        # Indicator if PDF context is active
        if st.session_state.pdf_context:
            st.caption("✅ Answering using search results + uploaded document context")
        else:
            st.caption("ℹ️ Answering using search results only")

        # Initialize chat history
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

        # Display Chat History
        for msg in st.session_state.chat_history:
            with st.chat_message(msg['role']):
                st.write(msg['content'])

        # User Input
        q = st.chat_input("Ask questions (e.g., 'Which represents the best value?')")
        if q:
            st.session_state.chat_history.append({'role': 'user', 'content': q})
            
            with st.spinner("Analyzing..."):
                # Call LLM with both Results and PDF Context
                ans = st.session_state.car_service.chat_about_results(
                    q, 
                    st.session_state.current_results,
                    context_text=st.session_state.pdf_context
                )
            
            st.session_state.chat_history.append({'role': 'assistant', 'content': ans})
            st.experimental_rerun()

        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.experimental_rerun()

# Footer
st.divider()
st.caption("Built with ❤️ using Streamlit | CarSearch AI")