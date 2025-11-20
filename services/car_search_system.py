import json
import os
import backoff
import requests
from typing import Dict, Any, List

# --- SAFE IMPORT FOR LANGFUSE ---
try:
    from langfuse.decorators import observe
except ImportError:
    # Define a dummy decorator that does nothing, allowing the code to run
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
# --------------------------------

# Import the StandvirtualScraper
from tools.standvirtual_scraper import StandvirtualScraper

class CarSearchService:
    """
    Manages the core application logic, orchestrating LLM calls for parsing
    and scraping activities.
    """
    
    LLM_MODEL = "gemini-2.5-flash-preview-09-2025"
    API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"

    def __init__(self):
        # Initialize the Portuguese scraper
        print("[Service] Initializing Standvirtual Scraper...")
        self.scraper = StandvirtualScraper()
        
        # Check for both GEMINI_API_KEY and GOOGLE_API_KEY
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        self.api_url = f"{self.API_BASE_URL}{self.LLM_MODEL}:generateContent"
        
        if not self.api_key:
            print("[Service Init] WARNING: LLM API key not found. AI features are disabled.")
        else:
            print(f"[Service Init] LLM API key loaded.")
        
        # --- UPDATED PROMPT TO INCLUDE MIN_PRICE ---
        self.parse_system_prompt = (
            "You are a helpful assistant that extracts structured search parameters from a user's car search query. "
            "The search will be conducted on Standvirtual, a Portuguese marketplace. Output MUST be valid JSON, according to the schema provided. "
            "Extract the following fields:"
            "\n- brand (string, e.g., BMW, Mercedes, Fiat)"
            "\n- model (string, e.g., Series 3, Class A, Panda)"
            "\n- min_price (integer, numeric value only)"
            "\n- max_price (integer, numeric value only)"
            "\n- min_year (integer, 4 digit year)"
            "\n- max_km (integer, numeric value only)"
            "\n- fuel (string, valid values: Diesel, Gasolina, Elétrico, Híbrido, Petrol)"
            "\n- location (string) - Set to null as scraping is country-wide."
            "\nRules:"
            "\n1. If a value is not mentioned, set it to null."
            "\n2. Convert \"k\" to thousands (e.g., \"20k km\" -> 20000)."
            "\n3. Infer the Brand if only the Model is given (e.g., \"Golf\" -> Brand: VW, Model: Golf)."
            "\n\nExamples:"
            "\nUser: 'find me Fiat Panda between 5000 and 10000'"
            "\nOutput: { \"brand\": \"Fiat\", \"model\": \"Panda\", \"min_price\": 5000, \"max_price\": 10000, \"min_year\": null, \"max_km\": null, \"fuel\": null, \"location\": null }"
            "\n\nUser: 'BMW X5 under 30000 euros diesel'"
            "\nOutput: { \"brand\": \"BMW\", \"model\": \"X5\", \"min_price\": null, \"max_price\": 30000, \"min_year\": null, \"max_km\": null, \"fuel\": \"Diesel\", \"location\": null }"
        )

        # Updated Schema with min_price
        self.parse_schema = {
            "type": "OBJECT",
            "properties": {
                "brand": {"type": "STRING", "nullable": True},
                "model": {"type": "STRING", "nullable": True},
                "min_price": {"type": "INTEGER", "nullable": True},
                "max_price": {"type": "INTEGER", "nullable": True},
                "min_year": {"type": "INTEGER", "nullable": True},
                "max_km": {"type": "INTEGER", "nullable": True},
                "fuel": {"type": "STRING", "nullable": True},
                "location": {"type": "STRING", "nullable": True}
            }
        }

    def _call_gemini_structured(self, user_prompt, system_instruction, response_schema):
        if not self.api_key:
            raise EnvironmentError("API key is not set.")
        
        @backoff.on_exception(
            backoff.expo, 
            (requests.exceptions.RequestException, json.JSONDecodeError), 
            max_tries=5
        )
        def attempt_call():
            payload = {
                "contents": [{"parts": [{"text": user_prompt}]}],
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": { 
                    "responseMimeType": "application/json",
                    "responseSchema": response_schema,
                    "temperature": 0.0
                },
            }

            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(
                f"{self.api_url}?key={self.api_key}", 
                headers=headers, 
                data=json.dumps(payload)
            )
            
            if response.status_code != 200:
                print(f"[Gemini Error] Status: {response.status_code}. Response: {response.text[:200]}...")
                response.raise_for_status() 
            
            result = response.json()
            json_str = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '{}')
            
            return json.loads(json_str)

        return attempt_call()

    @observe(as_type="generation")
    def parse_query(self, user_query: str) -> Dict[str, Any]:
        if not self.api_key:
            return {}
        
        try:
            filters = self._call_gemini_structured(
                user_query,
                self.parse_system_prompt,
                self.parse_schema
            )
            print(f"[parse_query] Parsed filters: {filters}")
            return filters
        except EnvironmentError as e:
            print(f"[parse_query] Error: {e}. LLM services will be skipped.")
            return {}
        except Exception as e:
            print(f"[parse_query] Error parsing query with Gemini: {e}")
            return {}

    @observe(as_type="span")
    def search_cars(self, filters: dict) -> list:
        cleaned_filters = {k: v for k, v in filters.items() if v is not None}
        
        brand = cleaned_filters.get('brand', '')
        model = cleaned_filters.get('model', '')
        min_price = cleaned_filters.get('min_price')
        max_price = cleaned_filters.get('max_price')
        min_year = cleaned_filters.get('min_year')
        
        try:
            print(f"[Scraper] Search initiated for: {cleaned_filters}")
            results = self.scraper.search(
                brand=brand, 
                model=model, 
                min_price=min_price,
                max_price=max_price, 
                min_year=min_year
            )
            return results
        except Exception as e:
            print(f"[search_cars] Error during scraping: {e}")
            return []

    @observe(as_type="generation")
    def chat_about_results(self, question: str, results: list, context_text: str = "") -> str:
        if not self.api_key:
            return "Cannot analyze results: API key is missing."

        chat_system_prompt = (
            "You are a helpful car analyst. Analyze the following list of car listings "
            "and answer the user's question concisely. "
            "If 'DOCUMENT CONTEXT' is provided, use it to cross-reference the cars (e.g., does a car fit the policy?). "
            "Base your answer ONLY on the provided data."
        )

        # Format inputs
        context_block = f"\n\nDOCUMENT CONTEXT:\n{context_text}\n" if context_text else ""
        results_json = json.dumps(results, indent=2)
        
        full_prompt = (
            f"{context_block}"
            f"\n\nCAR LISTINGS (JSON):\n{results_json}\n\n"
            f"USER QUESTION: {question}"
        )
        
        @backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
        def attempt_chat_call():
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "systemInstruction": {"parts": [{"text": chat_system_prompt}]},
                "generationConfig": {
                    "temperature": 0.5
                }
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                f"{self.api_url}?key={self.api_key}", 
                headers=headers, 
                data=json.dumps(payload)
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Could not generate a response.')

        try:
            return attempt_chat_call()
        except Exception as e:
            print(f"[chat_about_results] Error calling Gemini for chat: {e}")
            return "Sorry, I encountered an error while trying to analyze the results."
            
    def __del__(self):
        try:
            if hasattr(self, 'scraper'):
                del self.scraper
        except:
            pass