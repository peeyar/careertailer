import asyncio
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from app.core.interfaces import IJobScraper

# ── Constants ─────────────────────────────────────────────────────────────────

# Realistic browser headers — helps avoid bot detection on httpx requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Smart selectors — tried in order, first match with >100 chars wins
# Same list as before, shared between both tiers
ATS_SELECTORS = [
    '[data-automation-id="jobPostingDescription"]',  # Workday
    '#grnhse_app',                                   # Greenhouse wrapper
    '#job-content',                                  # Generic
    '.job-description',                              # Generic
    'div[id*="job-description"]',                    # Generic
    '#content',                                      # Greenhouse / Lever
    'main',                                          # Semantic HTML standard
]

# Minimum acceptable content length
MIN_CONTENT_LENGTH = 200

# Sites that always need JS rendering — skip httpx entirely for these
# Saves the ~300ms httpx attempt that will always fail
JS_REQUIRED_DOMAINS = [
    "workday.com",
    "myworkdayjobs.com",
    "greenhouse.io",
    "linkedin.com",
    "metacareers.com",
    "careers.microsoft.com",
    "jobs.lever.co",
    "smartrecruiters.com",
    "icims.com",
]


def _needs_js(url: str) -> bool:
    """Returns True if the URL is known to require JavaScript rendering."""
    return any(domain in url.lower() for domain in JS_REQUIRED_DOMAINS)


def _extract_with_selectors(soup: BeautifulSoup) -> str | None:
    """
    Tries smart ATS selectors against a BeautifulSoup tree.
    Returns cleaned text if a match is found, None otherwise.
    """
    for selector in ATS_SELECTORS:
        # BeautifulSoup CSS selector syntax
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator=" ", strip=True)
            if len(text) > 100:
                print(f"✨ Smart Scrape (httpx): Found content in '{selector}'")
                return " ".join(text.split())
    return None


def _clean_body(soup: BeautifulSoup) -> str:
    """
    Fallback: remove junk elements and return body text.
    Mirrors the Playwright evaluate() cleanup logic.
    """
    for tag in soup.select("nav, footer, script, style, iframe, .ad, .cookie-banner, [role='navigation']"):
        tag.decompose()

    body = soup.find("body")
    if not body:
        return ""
    return " ".join(body.get_text(separator=" ", strip=True).split())


# ── Scraper ───────────────────────────────────────────────────────────────────

class JobScraper(IJobScraper):
    """
    Two-tier scraper — fast httpx first, Playwright fallback.

    Tier 1 — httpx + BeautifulSoup (~200-400ms):
        Pure HTTP request, no browser. Works for static or SSR pages.
        Uses same smart ATS selectors as Tier 2.
        Skipped automatically for known JS-heavy domains.

    Tier 2 — Playwright (~4-8s):
        Full Chromium browser. Used when:
          - URL is a known JS-required domain
          - httpx returns content that's too short (JS placeholder)
          - httpx raises any exception (blocked, redirect loop, etc.)
        Exact same logic as the original scraper — nothing removed.
    """

    async def scrape(self, url: str) -> str:
        print(f"🕷️ Service: Scraping URL: {url}")

        # Skip httpx for known JS-heavy sites — go straight to Playwright
        if _needs_js(url):
            print(f"⚡ Tier 2 (direct): Known JS site, skipping httpx")
            return await self._scrape_playwright(url)

        # Try httpx first
        try:
            result = await self._scrape_httpx(url)
            if result and len(result) >= MIN_CONTENT_LENGTH:
                return result
            else:
                print(f"⚠️ Tier 1 result too short ({len(result) if result else 0} chars) — falling back to Playwright")
        except Exception as e:
            print(f"⚠️ Tier 1 failed ({type(e).__name__}: {e}) — falling back to Playwright")

        # Fall back to Playwright
        return await self._scrape_playwright(url)

    # ── Tier 1: httpx ─────────────────────────────────────────────────────────

    async def _scrape_httpx(self, url: str) -> str:
        """
        Fast HTTP scrape using httpx + BeautifulSoup.
        No browser, no JavaScript execution.
        """
        async with httpx.AsyncClient(
            headers=HEADERS,
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try smart selectors first
            result = _extract_with_selectors(soup)
            if result:
                return result

            # Fallback: clean body
            print("⚠️ No smart selector matched (httpx) — cleaning body")
            return _clean_body(soup)

    # ── Tier 2: Playwright ────────────────────────────────────────────────────

    async def _scrape_playwright(self, url: str) -> str:
        """
        Full browser scrape using Playwright + Chromium.
        Identical logic to the original scraper — no regressions.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"]
            )
            page = await context.new_page()

            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")

                # Buffer for JS frameworks (React/Vue) to render
                try:
                    await page.wait_for_timeout(2000)
                except:
                    pass

                # Try smart selectors
                for selector in ATS_SELECTORS:
                    if await page.locator(selector).count() > 0:
                        content = await page.locator(selector).first.inner_text()
                        if len(content) > 100:
                            print(f"✨ Smart Scrape (Playwright): Found content in '{selector}'")
                            return " ".join(content.split())

                # Fallback: remove junk and grab body
                print("⚠️ No smart selector found (Playwright). Cleaning page manually...")
                await page.evaluate("""() => {
                    const elements = document.querySelectorAll('nav, footer, script, style, iframe, .ad, .cookie-banner, [role="navigation"]');
                    elements.forEach(el => el.remove());
                }""")

                body_text = await page.evaluate("document.body.innerText")
                clean_text = " ".join(body_text.split())

                if len(clean_text) < MIN_CONTENT_LENGTH:
                    print(f"⚠️ Warning: Scraped text is very short ({len(clean_text)} chars). Page may have blocked us.")

                return clean_text

            except Exception as e:
                print(f"❌ Scraping Error: {str(e)}")
                raise e
            finally:
                await browser.close()