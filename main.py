import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import traceback
import time
import traceback
import re
from dateutil.parser import parse

app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920x1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0')

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error initializing ChromeDriver: {str(e)}")
        print(traceback.format_exc())
        return None

def clean_odd_value(odd_text):
    """Clean and standardize odd values, preserving + and - signs"""
    if not odd_text:
        return "N/A"
    
    # Remove any extra spaces or non-breaking spaces
    odd_text = odd_text.strip().replace('\xa0', ' ').replace('\u00a0', ' ')
    
    # Handle fractional odds (e.g., 5/2)
    if '/' in odd_text:
        try:
            numerator, denominator = odd_text.split('/')
            decimal_odd = round(float(numerator) / float(denominator) + 1, 2)
            return str(decimal_odd)
        except:
            return odd_text
    
    # Handle decimal odds with + or -
    match = re.search(r'^([+-]?\d+\.?\d*)', odd_text)
    if match:
        cleaned = match.group(1)
        # For American odds (+200), convert to decimal if needed
        if cleaned.startswith('+'):
            try:
                american_odd = float(cleaned[1:])
                decimal_odd = round(american_odd / 100 + 1, 2)
                return f"+{decimal_odd}"
            except:
                return cleaned
        elif cleaned.startswith('-'):
            try:
                american_odd = float(cleaned[1:])
                decimal_odd = round(100 / american_odd + 1, 2)
                return f"-{decimal_odd}"
            except:
                return cleaned
        else:
            return cleaned
    
    return odd_text

def parse_match_date(date_str, time_str):
    """Parse match date and time into a datetime object"""
    try:
        # Get current date and year
        today = datetime.now()
        current_year = today.year
        
        # Try to parse the date string (e.g., "Today", "Tomorrow", "12 Jan")
        if date_str.lower() == 'today':
            match_date = today.date()
        elif date_str.lower() == 'tomorrow':
            match_date = (today + timedelta(days=1)).date()
        else:
            # Parse date with current year (e.g., "12 Jan" -> "12 Jan 2023")
            date_with_year = f"{date_str} {current_year}"
            match_date = parse(date_with_year).date()
            
            # If the parsed date is in the past, assume it's next year
            if match_date < today.date():
                date_with_year = f"{date_str} {current_year + 1}"
                match_date = parse(date_with_year).date()
        
        # Parse time string
        time_obj = parse(time_str).time()
        
        # Combine date and time
        return datetime.combine(match_date, time_obj).strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"Error parsing date/time: {date_str} {time_str} - {str(e)}")
        return f"{date_str} {time_str}"  # Return original if parsing fails

def scrape_matches():
    """Main scraping function for Oddschecker with complete match details"""
    driver = init_driver()
    if not driver:
        return {"error": "Failed to initialize browser"}
    
    url = "https://www.oddschecker.com/co/futbol"
    print(f"Accessing: {url}")
    
    result = {
        "scraped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "leagues": []
    }
    
    try:
        driver.get(url)
        
        # Wait for page to load and handle cookie consent if present
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check for and accept cookies if present
            cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Aceptar')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                print("Accepted cookies")
                time.sleep(2)
        except Exception as e:
            print(f"Cookie handling error (non-critical): {str(e)}")
        
        # Wait for content to load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article[class*='CardWrapper']"))
            )
            print("Main content loaded")
        except Exception as e:
            print(f"Content loading warning: {str(e)}")
            # Proceed anyway
        
        # Give more time for dynamic content
        time.sleep(5)
        
        # Get page source and create BeautifulSoup object
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract all league sections
        league_cards = soup.find_all('article', class_=lambda c: c and 'CardWrapper' in c)
        if not league_cards:
            league_cards = soup.select("div[class*='league'], div[class*='League'], article")
        
        print(f"Found {len(league_cards)} league cards")
        
        if not league_cards:
            return {"error": "No leagues found. Website structure may have changed."}
        
        # Process each league card
        for card in league_cards:
            # Extract league name
            league_name_tag = card.select_one("a.AccordionText_aws8rxo, a[class*='AccordionText'], h2, h3, div.header, div[class*='header']")
            league_name = league_name_tag.text.strip() if league_name_tag else "Unknown League"
            print(f"\nProcessing league: {league_name}")
            
            league_data = {
                "name": league_name,
                "matches": []
            }
            
            # Extract match groups
            match_groups = card.select("div[class*='GroupWrapper'], div.matches, div.events")
            if not match_groups:
                match_groups = [card]
            
            for group in match_groups:
                # Extract individual matches
                match_rows = group.select("div[class*='RowContent'], div.match, div.event, tr.event")
                print(f"Found {len(match_rows)} matches in this group")
                
                for row in match_rows:
                    try:
                        # Extract date and time
                        date_tag = row.select_one("span[class*='date'], div[class*='date']")
                        time_tag = row.select_one("a[class*='StartTimeText'], span[class*='time'], div[class*='time']")
                        
                        date_str = date_tag.text.strip() if date_tag else "Today"
                        time_str = time_tag.text.strip() if time_tag else "00:00"
                        
                        # Parse full datetime
                        full_datetime = parse_match_date(date_str, time_str)
                        
                        # Extract teams
                        home_team_tag = row.select_one("div[class*='TeamWrapper']:first-child p, div.home-team, span.home-team")
                        away_team_tag = row.select_one("div[class*='TeamWrapper']:last-child p, div.away-team, span.away-team")
                        
                        home_team = home_team_tag.text.strip() if home_team_tag else "Unknown Home Team"
                        away_team = away_team_tag.text.strip() if away_team_tag else "Unknown Away Team"
                        
                        # Extract odds
                        odds_elements = row.select("button[class*='bestOddsButton'], span[class*='odd'], div[class*='odd']")
                        odds_values = [clean_odd_value(odd.text.strip()) for odd in odds_elements if odd.text.strip()]
                        
                        # Extract bookmaker count if available
                        bookmakers_tag = row.select_one("span[class*='bookmakers'], div[class*='bookmakers']")
                        bookmakers_count = bookmakers_tag.text.strip() if bookmakers_tag else "N/A"
                        
                        # Extract match link if available
                        match_link_tag = row.select_one("a[href*='/football/']")
                        match_link = "https://www.oddschecker.com" + match_link_tag['href'] if match_link_tag and match_link_tag.has_attr('href') else "N/A"
                        
                        match_data = {
                            "date": full_datetime,
                            "date_str": date_str,
                            "time_str": time_str,
                            "homeTeam": {
                                "name": home_team,
                                "odds": odds_values[0] if len(odds_values) > 0 else "N/A"
                            },
                            "awayTeam": {
                                "name": away_team,
                                "odds": odds_values[2] if len(odds_values) > 2 else "N/A"
                            },
                            "draw_odds": odds_values[1] if len(odds_values) > 1 else "N/A",
                            "bookmakers_count": bookmakers_count,
                            "match_link": match_link,
                            "raw_odds": odds_values  # Include all odds found
                        }
                        
                        league_data["matches"].append(match_data)
                        
                    except Exception as e:
                        print(f"Error processing match: {str(e)}")
                        print(traceback.format_exc())
                        continue
            
            if league_data["matches"]:
                result["leagues"].append(league_data)
                
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        print(traceback.format_exc())
        try:
            driver.save_screenshot("error_screenshot.png")
            with open("error_page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("Debug files saved")
        except:
            pass
        return {"error": str(e), "stack_trace": traceback.format_exc()}
    finally:
        if driver:
            driver.quit()
    
    return result

@app.get("/")
def root():
    return {"message": "Welcome to the Oddschecker scraper", "endpoints": ["/scrape"]}

@app.get("/scrape")
def get_matches():
    try:
        data = scrape_matches()
        return JSONResponse(content=data)
    except Exception as e:
        print("SCRAPER ERROR:", e)
        print(traceback.format_exc())
        return JSONResponse(content={"error": str(e), "stack_trace": traceback.format_exc()}, status_code=500)