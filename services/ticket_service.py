"""
Ticket Service - Main orchestration for ticket processing
Coordinates AI, SLA calculations, and routing.
"""
from langfuse import observe
from services.ai_service import AIService
from tools.sla_calculator import SLACalculator
from tools.business_hours import BusinessHoursChecker


class TicketService:
    """Service for processing and managing support tickets."""

    # Routing rules: category -> team
    ROUTING_RULES = {
        "Authentication": "Auth Team",
        "Billing": "Billing Team",
        "Technical": "Technical Team",
        "Account Management": "Account Team",
        "Sales": "Sales Team",
        "Data Recovery": "Technical Team",
        "General Support": "Support Team"
    }

    def __init__(self):
        """Initialize ticket service with dependencies."""
        self.ai_service = AIService()
        self.sla_calculator = SLACalculator()
        self.business_hours = BusinessHoursChecker()

    @observe()
    def process_ticket(self, ticket_text: str) -> dict:
        """
        Complete ticket processing pipeline.

        This is the main entry point that orchestrates:
        1. AI classification
        2. SLA deadline calculation
        3. Team routing
        4. Business hours check

        Args:
            ticket_text: Raw ticket text from customer

        Returns:
            Complete ticket analysis with all enriched data
        """
        # Step 1: Classify ticket with AI
        classification = self.ai_service.classify_ticket(ticket_text)

        # Step 2: Calculate SLA deadline based on urgency
        sla_deadline = self.sla_calculator.calculate_deadline(
            urgency=classification['urgency']
        )

        # Step 3: Determine which team should handle this
        route_to = self.ROUTING_RULES.get(
            classification['category'],
            "Support Team"  # Default routing
        )

        # Step 4: Check business hours status
        business_status = self.business_hours.get_status()

        # Step 5: Build complete ticket data
        ticket_data = {
            **classification,  # Include all classification fields
            "original_text": ticket_text,
            "sla_deadline": sla_deadline,
            "route_to": route_to,
            "business_hours_status": business_status,
            "hours_until_deadline": self.sla_calculator.hours_remaining(sla_deadline)
        }

        return ticket_data

    @observe()
    def generate_response(self, ticket_data: dict) -> str:
        """
        Generate suggested response for a ticket.

        Args:
            ticket_data: Processed ticket information

        Returns:
            Suggested response text
        """
        return self.ai_service.suggest_response(ticket_data)

    @observe()
    def ask_about_ticket(self, question: str, ticket_data: dict) -> str:
        """
        Answer questions about a specific ticket.

        Args:
            question: User's question
            ticket_data: Ticket information for context

        Returns:
            Answer to the question
        """
        return self.ai_service.answer_question(question, ticket_data)

    def get_routing_options(self) -> list[str]:
        """
        Get list of available teams.

        Returns:
            List of team names
        """
        return list(set(self.ROUTING_RULES.values()))

    def get_category_options(self) -> list[str]:
        """
        Get list of support categories.

        Returns:
            List of category names
        """
        return list(self.ROUTING_RULES.keys())
