"""
HelpDesk AI - Customer Support Ticket Analyzer
A Streamlit app demonstrating clean architecture and AI integration.
"""
import streamlit as st
from dotenv import load_dotenv

# Import our services
from services.ticket_service import TicketService
from utils.tracing import init_tracing

# Load environment variables
load_dotenv()

# Initialize tracing (Week 7 - Langfuse)
init_tracing()

# Configure page
st.set_page_config(
    page_title="HelpDesk AI",
    page_icon="🎫",
    layout="wide"
)

# Initialize service in session state
if 'ticket_service' not in st.session_state:
    st.session_state.ticket_service = TicketService()

# Main header
st.title("🎫 HelpDesk AI")
st.markdown("AI-powered customer support ticket analyzer")

# Sidebar with info
with st.sidebar:
    st.header("About")
    st.markdown("""
    This app demonstrates:
    - 🤖 AI classification (Week 2-3)
    - 📄 Structured extraction (Week 3)
    - 🔧 Function calling (Week 5)
    - 🎨 Streamlit UI (Week 6)
    - 📊 Langfuse tracing (Week 7)
    - 🏗️ Clean architecture (Week 8)
    - 📝 Separated prompts (Week 8)
    """)

    st.divider()

    st.subheader("SLA Response Times")
    st.markdown("""
    - **Critical:** 4 hours
    - **High:** 24 hours
    - **Medium:** 48 hours
    - **Low:** 72 hours
    """)

    st.divider()

    st.subheader("Routing Teams")
    teams = st.session_state.ticket_service.get_routing_options()
    for team in sorted(teams):
        st.text(f"• {team}")

# Main content area
tab1, tab2 = st.tabs(["📝 Analyze Ticket", "💬 Chat About Ticket"])

with tab1:
    st.header("Analyze Support Ticket")

    # Sample tickets for quick testing
    with st.expander("📋 Try Sample Tickets"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔴 Critical: Can't login"):
                st.session_state.sample_ticket = "I can't log into my account. It keeps saying my password is invalid even though I'm sure it's correct. I've tried resetting it twice but the email never arrives. This is urgent!"

        with col2:
            if st.button("🟡 Medium: Slow performance"):
                st.session_state.sample_ticket = "The dashboard is loading very slowly, taking 30+ seconds. This started happening this morning."

    # Ticket input
    ticket_text = st.text_area(
        "Paste customer ticket here:",
        value=st.session_state.get('sample_ticket', ''),
        height=150,
        placeholder="Example: I can't log into my account..."
    )

    # Process button
    if st.button("🔍 Analyze Ticket", type="primary", use_container_width=True):
        if not ticket_text.strip():
            st.warning("Please enter a ticket to analyze")
        else:
            with st.spinner("Processing ticket..."):
                # Call our service (all logic is in the service layer!)
                result = st.session_state.ticket_service.process_ticket(ticket_text)

                # Store in session state for chat
                st.session_state.current_ticket = result

            # Display results
            st.success("✅ Ticket analyzed!")

            # Metrics row
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                urgency_colors = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢"
                }
                urgency_emoji = urgency_colors.get(result['urgency'], "⚪")
                st.metric("Urgency", f"{urgency_emoji} {result['urgency'].upper()}")

            with col2:
                st.metric("Category", result['category'])

            with col3:
                hours = result['hours_until_deadline']
                st.metric("Hours Until SLA", f"{hours:.1f}")

            with col4:
                st.metric("Route To", result['route_to'])

            # Details section
            st.divider()

            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("📋 Ticket Details")
                st.write(f"**Customer:** {result['customer_name']}")
                st.write(f"**Issue Summary:**")
                st.info(result['issue_summary'])
                st.write(f"**SLA Deadline:** {result['sla_deadline']}")

                # Business hours status
                bh_status = result['business_hours_status']
                if bh_status['is_business_hours']:
                    st.success(f"✅ {bh_status['message']}")
                else:
                    st.warning(f"⏰ {bh_status['message']}")

            with col_right:
                st.subheader("💬 Suggested Response")
                with st.spinner("Generating response..."):
                    response = st.session_state.ticket_service.generate_response(result)
                st.write(response)

                if st.button("📋 Copy Response"):
                    st.toast("Response copied to clipboard!")

            # Original ticket
            with st.expander("📄 View Original Ticket"):
                st.text(result['original_text'])

with tab2:
    st.header("Chat About Ticket")

    if 'current_ticket' not in st.session_state:
        st.info("👈 Analyze a ticket first to enable chat")
    else:
        ticket = st.session_state.current_ticket

        # Show ticket summary
        st.markdown(f"""
        **Current Ticket:**
        - Category: {ticket['category']}
        - Urgency: {ticket['urgency']}
        - Customer: {ticket['customer_name']}
        """)

        st.divider()

        # Initialize chat history
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []

        # Chat container for messages
        chat_container = st.container()

        with chat_container:
            # Display chat history
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

        # Chat input (outside container for proper positioning)
        question = st.chat_input("Ask a question about this ticket...")

        if question:
            # Add user message to history
            st.session_state.chat_history.append({
                "role": "user",
                "content": question
            })

            # Get AI response
            with st.spinner("Thinking..."):
                answer = st.session_state.ticket_service.ask_about_ticket(
                    question,
                    ticket
                )

            # Add assistant message to history
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": answer
            })

            # Rerun to display new messages
            st.rerun()

        # Clear chat button
        if len(st.session_state.chat_history) > 0:
            if st.button("🗑️ Clear Chat History"):
                st.session_state.chat_history = []
                st.rerun()

# Footer
st.divider()
st.caption("Built with ❤️ using Streamlit and Google Gemini | Week 9 Integration Workshop")
