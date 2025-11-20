"""
CarSearch AI - Car Search and Analysis App
A Streamlit app demonstrating clean architecture, LLM integration, and web scraping.
"""
import multiprocessing

# CRITICAL FIX: Set the start method for multiprocessing.
# This resolves the RuntimeError caused by Streamlit's process model
# conflicting with undetected-chromedriver's process spawning on macOS/Linux.
try:
    # Use 'spawn' for better cross-platform compatibility and to fix the uc.Chrome error.
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    # Handle case where set_start_method might be called multiple times
    pass

import streamlit as st
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

# Import our services AFTER loading env
from services.car_search_system import CarSearchService
from utils.tracing import init_tracing

# Initialize Langfuse tracing
init_tracing()

# Configure Streamlit page
st.set_page_config(
    page_title="CarSearch AI",
    page_icon="🚗",
    layout="wide"
)

# Initialize CarSearchService in session state
if 'car_service' not in st.session_state:
    # This initialization is now safe because the multiprocessing context
    # has been configured above.
    st.session_state.car_service = CarSearchService()

# Page header
st.title("🚗 CarSearch AI")
st.markdown("AI-powered car search assistant")

# Tabs: Search and Chat
tab1, tab2 = st.tabs(["🔍 Search Cars", "💬 Chat About Cars"])

# ------------------- Tab 1: Search ------------------- #
with tab1:
    st.header("Search for Cars")

    user_query = st.text_area(
        "Enter your search query (brand, model, price, year, etc.)",
        height=150
    )

    if st.button("Search", type="primary"):
        if not user_query.strip():
            st.warning("Please enter a search query.")
        else:
            with st.spinner("Processing your query..."):
                # parse_query and search_cars already traced via @observe
                filters = st.session_state.car_service.parse_query(user_query)
                results = st.session_state.car_service.search_cars(filters)
                st.session_state.current_results = results

            if results:
                st.success(f"Found {len(results)} cars")
                for car in results:
                    st.markdown(
                        f"**{car.get('title','N/A')}** | "
                        f"Price: {car.get('price','N/A')} | "
                        f"Year: {car.get('year','N/A')} | "
                        f"KM: {car.get('km','N/A')} | "
                        f"Fuel: {car.get('fuel','N/A')}"
                    )
                    if car.get('link'):
                        st.markdown(f"[View Listing]({car['link']})")
            else:
                st.info("No cars found matching your query.")

# ------------------- Tab 2: Chat ------------------- #
with tab2:
    st.header("Chat About Cars")

    if 'current_results' not in st.session_state or not st.session_state.current_results:
        st.info("👈 Perform a search first to enable chat")
    else:
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history:
                with st.chat_message(message['role']):
                    st.write(message['content'])

        # Chat input
        question = st.chat_input("Ask a question about these cars...")
        if question:
            st.session_state.chat_history.append({'role': 'user', 'content': question})

            with st.spinner("Generating response..."):
                answer = st.session_state.car_service.chat_about_results(
                    question, st.session_state.current_results
                )

            st.session_state.chat_history.append({'role': 'assistant', 'content': answer})
            st.experimental_rerun()

        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.experimental_rerun()

# Footer
st.divider()
st.caption("Built with ❤️ using Streamlit | CarSearch AI")