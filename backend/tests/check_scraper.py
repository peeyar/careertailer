import asyncio
from playwright.async_api import async_playwright

async def check_my_scraper(url: str):
    print(f"--- Starting Playwright Scrape for: {url} ---")
    
    async with async_playwright() as p:
        # Launch a headless browser (not visible on screen)
        browser = await p.chromium.launch(headless=True)
        
        # Create a new page and disguise it slightly
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            # Go to the URL and wait for the network to be idle (page loaded)
            await page.goto(url, timeout=60000)
            
            # Specific hack for Workday: Wait for the main content to appear
            # We wait for the 'body' to be populated or a specific job description container
            await page.wait_for_load_state("networkidle") 
            
            # Extract the text
            content = await page.content()
            
            # We can still use BeautifulSoup to clean the HTML we got from Playwright
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            
            # Remove junk
            for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                element.extract()

            clean_text = soup.get_text(separator=" ", strip=True)
            
            print(f"Status: Success")
            print(f"Final Character Count: {len(clean_text)}")
            
            if len(clean_text) > 500:
                print("\n--- Preview of Scraped Content ---")
                print(clean_text[:500] + "...")
            else:
                print("\nWARNING: Text count is low. The page might still be loading or blocking us.")
                
        except Exception as e:
            print(f"Error scraping: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    # The Salesforce Workday URL
    target_url = "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site/job/California---San-Francisco/Software-Engineering-LMTS_JR310801?source=LinkedIn_Jobs"
    asyncio.run(check_my_scraper(target_url))