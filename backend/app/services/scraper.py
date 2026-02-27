import asyncio
from playwright.async_api import async_playwright
from app.core.interfaces import IJobScraper

class JobScraper(IJobScraper):
    """
    Production-grade Scraper using Playwright.
    Implements the IJobScraper interface.
    
    MEMORY LOG APPLIED:
    - Switched from 'networkidle' to 'domcontentloaded' to fix timeouts on heavy sites (SoFi).
    - Added specific waits for content to ensure data is ready.
    - Uses Smart Locators to avoid scraping navbars.
    """

    async def scrape(self, url: str) -> str:
        print(f"🕷️ Service: Scraping URL: {url}")
        
        async with async_playwright() as p:
            # Launch browser (headless for server environment)
            browser = await p.chromium.launch(headless=True)
            
            # Create a context with a real user agent to mimic a human user
            # This helps avoid immediate bot detection
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            
            try:
                # RULE: Use 'domcontentloaded' instead of 'networkidle'.
                # 'networkidle' waits for 0 network connections for 500ms, which causes timeouts on modern sites.
                # 'domcontentloaded' fires as soon as HTML is parsed.
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Wait a small buffer for JS frameworks (React/Vue) to render text
                # 2 seconds is usually enough for the main text to appear
                try:
                    await page.wait_for_timeout(2000)
                except:
                    pass

                # RULE: Smart Locators for common ATS platforms
                ats_selectors = [
                    '[data-automation-id="jobPostingDescription"]', # Workday
                    '#grnhse_app',  # <--- NEW: Standard Greenhouse Wrapper
                    '#content',     # <--- NEW: Generic Content Wrapper
                    '#job-content', # Generic
                    '.job-description', # Generic
                    'div[id*="job-description"]', # Generic
                    '#content', # Greenhouse/Lever often use this
                    'main', # Semantic HTML standard
                ]

                # Try to find a specific job container first
                for selector in ats_selectors:
                    # Check if selector exists and is visible
                    if await page.locator(selector).count() > 0:
                        content = await page.locator(selector).first.inner_text()
                        if len(content) > 100: # Ensure it's not just an empty container
                            print(f"✨ Smart Scrape: Found content in '{selector}'")
                            return " ".join(content.split()) # Clean whitespace

                # Fallback: Clean up the page and grab body
                print("⚠️ No smart selector found. Cleaning page manually...")
                
                # Remove junk elements that might confuse the AI
                await page.evaluate("""() => {
                    const elements = document.querySelectorAll('nav, footer, script, style, iframe, .ad, .cookie-banner, [role="navigation"]');
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