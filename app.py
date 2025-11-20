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
if 'search_summary' not in st.session_state:
    st.session_state.search_summary = ""
if 'current_results' not in st.session_state:
    st.session_state.current_results = []

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
    user_query = st.text_area(
        "Enter your requirement", 
        placeholder="Example: 'Diesel BMW Series 3 from 2018, max 80k km, price between 20.000€ and 30.000€'",
        height=100,
        help="You can specify Brand, Model, Fuel Type, Minimum Year, Max KM, and Price Range."
    )

    # --- ACTION: FETCH DATA ---
    if st.button("Search", type="primary"):
        if not user_query.strip():
            st.warning("Please enter a query.")
        else:
            with st.spinner("Searching Market... (Check the opened browser window!)"):
                # Lazy Initialization
                if st.session_state.car_service is None:
                    try:
                        st.session_state.car_service = CarSearchService()
                    except Exception as e:
                        st.error(f"Failed to initialize service: {e}")
                        st.stop()
                
                # 1. Parse Query
                filters = st.session_state.car_service.parse_query(user_query)
                
                # 2. Scrape Data
                raw_results = st.session_state.car_service.search_cars(filters)
                
                if raw_results:
                    # 3. AI Rank & Annotate
                    with st.spinner("🤖 AI is analyzing and ranking deals..."):
                        try:
                            processed_results = st.session_state.car_service.rank_and_annotate(user_query, raw_results)
                            st.session_state.current_results = processed_results
                        except AttributeError:
                            st.session_state.current_results = raw_results
                    
                    # 4. Generate Market Summary
                    with st.spinner("Generating final market report..."):
                        try:
                            summary = st.session_state.car_service.summarize_results(
                                st.session_state.current_results, 
                                context_text=st.session_state.pdf_context
                            )
                            st.session_state.search_summary = summary
                        except AttributeError:
                            st.session_state.search_summary = ""
                else:
                    st.session_state.current_results = []
                    st.warning("No cars found matching your query. Check the terminal for details.")

    # --- DISPLAY: RENDER DATA (Outside button block so it persists) ---
    if st.session_state.current_results:
        results = st.session_state.current_results
        
        st.divider()
        
        # Friendly Intro
        st.markdown("### 🎯 Best Matches (Ranked by AI)")
        st.success(f"Found {len(results)} listings based on your criteria.")
        
        # Show Listings
        for car in results:
            with st.container(border=True):
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    if car.get('image_url') and "http" in car['image_url']:
                        st.image(car['image_url'], use_column_width=True)
                    else:
                        st.caption("No Image Available")
                
                with col2:
                    st.subheader(car.get('title', 'No Title'))
                    
                    # AI Description
                    if car.get('ai_description'):
                        st.info(f"🤖 **AI says:** {car['ai_description']}")

                    st.markdown(
                        f"**Price:** €{car.get('price', 0):,} | "
                        f"**Year:** {car.get('year', 'N/A')} | "
                        f"**KM:** {car.get('km', 0):,} km | "
                        f"**Fuel:** {car.get('fuel', 'N/A')}"
                    )
                    if car.get('link'):
                        st.markdown(f"[👉 View Full Listing]({car['link']})")
        
        # Market Summary at the bottom
        if st.session_state.search_summary:
            st.divider()
            st.info(f"**📊 Market Overview:**\n\n{st.session_state.search_summary}")

# --- TAB 2: CHAT ---
with tab2:
    st.header("Chat About Results")
    
    if not st.session_state.current_results:
        st.info("Please perform a search in the 'Search Cars' tab first.")
    else:
        if st.session_state.pdf_context:
            st.caption("✅ Answering using search results + uploaded document context")
        else:
            st.caption("ℹ️ Answering using search results only")

        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

        for msg in st.session_state.chat_history:
            with st.chat_message(msg['role']):
                st.write(msg['content'])

        q = st.chat_input("Ask questions (e.g., 'Which represents the best value?')")
        if q:
            st.session_state.chat_history.append({'role': 'user', 'content': q})
            
            with st.spinner("Analyzing..."):
                ans = st.session_state.car_service.chat_about_results(
                    q, 
                    st.session_state.current_results,
                    context_text=st.session_state.pdf_context
                )
            
            st.session_state.chat_history.append({'role': 'assistant', 'content': ans})
            st.rerun()

        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

# Footer
st.divider()
st.caption("Built with ❤️ using Streamlit | CarSearch AI")