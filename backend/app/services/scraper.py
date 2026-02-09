import asyncio
from playwright.async_api import async_playwright
from app.core.interfaces import IJobScraper

class JobScraper(IJobScraper):
    """
    Production-grade Scraper using Playwright.
    Implements the IJobScraper interface.
    
    MEMORY LOG APPLIED:
    - Uses 'networkidle' to handle SPAs (Workday/Greenhouse).
    - Uses Smart Locators to avoid scraping navbars.
    """

    async def scrape(self, url: str) -> str:
        print(f"🕷️ Service: Scraping URL: {url}")
        
        async with async_playwright() as p:
            # Launch browser (headless for server environment)
            browser = await p.chromium.launch(headless=True)
            
            # Create a context with a real user agent to mimic a human user
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            
            try:
                # RULE: Wait for network to settle (fixes Workday blank page issue)
                await page.goto(url, timeout=60000, wait_until="networkidle")
                
                # RULE: Smart Locators for common ATS platforms
                ats_selectors = [
                    '[data-automation-id="jobPostingDescription"]', # Workday
                    '#job-content', # Generic
                    '.job-description', # Generic
                    'div[id*="job-description"]' # Generic
                ]

                # Try to find a specific job container first
                for selector in ats_selectors:
                    if await page.locator(selector).count() > 0:
                        print(f"✨ Smart Scrape: Found content in '{selector}'")
                        return await page.locator(selector).first.inner_text()

                # Fallback: Clean up the page and grab body
                print("⚠️ No smart selector found. Cleaning page manually...")
                await page.evaluate("""() => {
                    const elements = document.querySelectorAll('nav, footer, script, style, iframe, .ad, .cookie-banner');
                    elements.forEach(el => el.remove());
                }""")
                
                body_text = await page.evaluate("document.body.innerText")
                clean_text = " ".join(body_text.split())
                
                # RULE: Validate content length
                if len(clean_text) < 200:
                    print(f"⚠️ Warning: Scraped text is very short ({len(clean_text)} chars). Page might have blocked us or failed to load.")
                
                return clean_text
                
            except Exception as e:
                print(f"❌ Scraping Error: {str(e)}")
                raise e
            finally:
                await browser.close()