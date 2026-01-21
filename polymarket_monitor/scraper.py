"""
Google Maps Popular Times Scraper using Playwright
Handles IP rotation and anti-bot detection
"""
import asyncio
from datetime import datetime
from typing import Dict, Optional, List
from playwright.async_api import async_playwright, Browser, Page
from loguru import logger
import json
import re
from config import settings


class GoogleMapsScraperError(Exception):
    """Custom exception for scraper errors"""
    pass


class GoogleMapsScraper:
    """
    Scrapes Google Maps Popular Times data using Playwright
    with anti-detection measures and proxy support
    """
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def start(self):
        """Initialize browser with anti-detection settings"""
        playwright = await async_playwright().start()
        
        # Browser launch options
        launch_options = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        }
        
        # Add proxy if configured
        if settings.proxy_dict:
            launch_options["proxy"] = settings.proxy_dict
            logger.info(f"Using proxy: {settings.proxy_dict['server']}")
        
        self.browser = await playwright.chromium.launch(**launch_options)
        
        # Create context with realistic user agent
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )
        
        self.page = await context.new_page()
        
        # Inject anti-detection scripts
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            window.chrome = {
                runtime: {}
            };
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        logger.info("Browser initialized successfully")
        
    async def close(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")
    
    async def search_place(self, query: str) -> Dict:
        """
        Search for a place on Google Maps and extract Popular Times data
        
        Args:
            query: Search query (e.g., "Domino's Pizza 2450 Crystal Dr Arlington VA")
            
        Returns:
            Dict containing place data and current popularity
        """
        try:
            # Navigate to Google Maps
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            logger.info(f"Searching: {query}")
            
            await self.page.goto(search_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)  # Wait for dynamic content
            
            # Extract place name
            place_name = await self._extract_place_name()
            
            # Extract current popularity
            current_popularity = await self._extract_current_popularity()
            
            # Extract popular times data
            popular_times = await self._extract_popular_times()
            
            # Get timestamp
            timestamp = datetime.now().isoformat()
            
            result = {
                "query": query,
                "place_name": place_name,
                "current_popularity": current_popularity,
                "popular_times": popular_times,
                "timestamp": timestamp,
                "success": True
            }
            
            logger.info(f"✅ {place_name}: Current popularity = {current_popularity}%")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error scraping {query}: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False
            }
    
    async def _extract_place_name(self) -> str:
        """Extract place name from the page"""
        try:
            # Try multiple selectors
            selectors = [
                'h1.DUwDvf',
                '[role="main"] h1',
                '.fontHeadlineLarge'
            ]
            
            for selector in selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        name = await element.inner_text()
                        return name.strip()
                except:
                    continue
            
            return "Unknown Place"
        except Exception as e:
            logger.warning(f"Could not extract place name: {e}")
            return "Unknown Place"
    
    async def _extract_current_popularity(self) -> Optional[int]:
        """
        Extract current popularity percentage
        
        Returns:
            Integer 0-100 representing current busyness, or None if not available
        """
        try:
            # Look for "Live" or "Currently" indicators
            # Google Maps shows this in various formats
            
            # Method 1: Look for aria-label with percentage
            page_content = await self.page.content()
            
            # Pattern: "Currently X% as busy as it usually is"
            pattern = r'Currently (\d+)%'
            match = re.search(pattern, page_content)
            if match:
                return int(match.group(1))
            
            # Method 2: Look for "Live" section with bar height
            # This requires analyzing the SVG/div heights in the popular times chart
            try:
                live_selector = '[aria-label*="Currently"]'
                live_element = await self.page.query_selector(live_selector)
                if live_element:
                    aria_label = await live_element.get_attribute('aria-label')
                    match = re.search(r'(\d+)%', aria_label)
                    if match:
                        return int(match.group(1))
            except:
                pass
            
            # Method 3: Check for "Not too busy" / "Usually busy" text indicators
            text_indicators = {
                "not too busy": 20,
                "usually not too busy": 20,
                "usually a little busy": 40,
                "usually as busy as it gets": 90,
                "usually busy": 70
            }
            
            for text, value in text_indicators.items():
                if text.lower() in page_content.lower():
                    logger.info(f"Found text indicator: '{text}' -> {value}%")
                    return value
            
            logger.warning("Could not extract current popularity")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting current popularity: {e}")
            return None
    
    async def _extract_popular_times(self) -> Dict:
        """
        Extract popular times histogram data
        
        Returns:
            Dict with day-of-week keys and hourly popularity arrays
        """
        try:
            # This is complex as Google uses dynamic SVG charts
            # For MVP, we'll return a placeholder
            # Full implementation would parse the SVG bars
            
            return {
                "note": "Popular times extraction requires advanced SVG parsing",
                "available": False
            }
            
        except Exception as e:
            logger.error(f"Error extracting popular times: {e}")
            return {}
    
    async def scrape_multiple(self, queries: List[str]) -> List[Dict]:
        """
        Scrape multiple locations
        
        Args:
            queries: List of search queries
            
        Returns:
            List of results
        """
        results = []
        
        for query in queries:
            result = await self.search_place(query)
            results.append(result)
            
            # Random delay to avoid detection
            await asyncio.sleep(2 + (hash(query) % 3))
        
        return results


# Standalone test function
async def test_scraper():
    """Test the scraper with a sample location"""
    test_query = "Domino's Pizza 2450 Crystal Dr Arlington VA"
    
    async with GoogleMapsScraper() as scraper:
        result = await scraper.search_place(test_query)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(test_scraper())
