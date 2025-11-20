import time
import re
import os
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class StandvirtualScraper:
    """
    Scrapes car listings from Standvirtual.com using Selenium.
    OPTIMIZED: Uses 'eager' loading strategy for faster performance.
    """
    BASE_URL = "https://www.standvirtual.com/carros"

    def __init__(self):
        chrome_options = Options()
        
        # --- OPTIMIZATION: EAGER LOADING ---
        # This tells Selenium not to wait for all images/ads to load before continuing.
        # It drastically reduces the time per search.
        chrome_options.page_load_strategy = 'eager'
        # -----------------------------------

        # --- VISIBLE BROWSER SETTINGS ---
        # chrome_options.add_argument("--headless=new") 
        
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        
        # --- BLOCK POPUPS & NOTIFICATIONS ---
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        prefs = {
            "profile.default_content_setting_values.notifications": 2, # 2 = Block
            "profile.default_content_setting_values.geolocation": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Stealth settings
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        chrome_options.add_argument("--lang=pt-PT")

        try:
            print("[Scraper] Initializing Chrome Driver...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(5) # Reduced implicit wait for speed
            
            # Mask webdriver property
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            print("[Scraper] Chrome Driver initialized successfully.")
        except Exception as e:
            print(f"[Scraper] Failed to initialize Chrome driver: {e}")
            raise

    def search(self, brand="", model="", min_price=None, max_price=None, min_year=None):
        # 1. Navigation Logic
        url = self.BASE_URL
        if brand:
            clean_brand = brand.lower().replace(" ", "-")
            url += f"/{clean_brand}"
            if model:
                clean_model = model.lower().replace(" ", "-")
                url += f"/{clean_model}"
        
        params = {}
        if min_price: params["search[filter_float_price:from]"] = min_price
        if max_price: params["search[filter_float_price:to]"] = max_price
        if min_year: params["search[filter_float_year:from]"] = min_year
        
        if params: url += f"?{urlencode(params)}"
            
        print(f"[Scraper] Navigating to: {url}")
        try:
            self.driver.get(url)
        except Exception as e:
            print(f"[Scraper] Navigation failed: {e}")
            return []

        # 2. Cookie Banner (Fast Check)
        try:
            consent_button = WebDriverWait(self.driver, 2).until( # Reduced timeout
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            consent_button.click()
            # Removed explicit sleep, rely on page load
        except:
            pass

        # 3. Wait for Content
        print("[Scraper] Waiting for listings...")
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except:
            print("[Scraper] Timeout waiting for 'article' tags.")
            return []

        # Reduced safety buffer
        time.sleep(1)

        # 4. Robust Extraction Loop
        results = []
        articles = self.driver.find_elements(By.TAG_NAME, "article")
        print(f"[Scraper] Found {len(articles)} raw items. Extracting details...")

        for i, article in enumerate(articles[:25]):
            try:
                # --- A. Extract Link & Title ---
                try:
                    link_elem = article.find_element(By.TAG_NAME, "a")
                    link = link_elem.get_attribute("href")
                    title = link_elem.text.strip() or "No Title"
                except:
                    continue

                if not link or "standvirtual.com" not in link:
                    continue

                # --- B. Extract Image ---
                image_url = ""
                try:
                    img_elem = article.find_element(By.TAG_NAME, "img")
                    src = img_elem.get_attribute("src")
                    data_src = img_elem.get_attribute("data-src")
                    if src and "http" in src: image_url = src
                    elif data_src and "http" in data_src: image_url = data_src
                except:
                    pass

                # --- C. Extract Price ---
                price = 0
                try:
                    card_text = article.text
                    price_match = re.search(r'([\d\s\.]+)\s?EUR', card_text)
                    if price_match:
                        price = int(re.sub(r'[^\d]', '', price_match.group(1)))
                except:
                    price = 0 

                # --- D. Extract Specs ---
                year = 0
                km = 0
                fuel = "Other"
                
                try:
                    text_lower = article.text.lower()
                    year_match = re.search(r'(19|20)\d{2}', text_lower)
                    if year_match: year = int(year_match.group(0))

                    km_match = re.search(r'(\d[\d\s\.]*)\s?km', text_lower)
                    if km_match: km = int(re.sub(r'[^\d]', '', km_match.group(1)))

                    if "gasolina" in text_lower: fuel = "Gasolina"
                    elif "diesel" in text_lower: fuel = "Diesel"
                    elif "elétrico" in text_lower: fuel = "Elétrico"
                    elif "híbrido" in text_lower: fuel = "Híbrido"
                except:
                    pass 

                # --- VALIDATION ---
                if price == 0 and year == 0:
                    continue

                results.append({
                    "title": title, 
                    "price": price, 
                    "year": year, 
                    "km": km, 
                    "fuel": fuel, 
                    "link": link,
                    "image_url": image_url
                })

            except Exception as e:
                continue

        print(f"[Scraper] Extraction complete. Found {len(results)} valid cars.")
        return results

    def __del__(self):
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except:
            pass