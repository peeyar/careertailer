# 🧠 Project Memory & Decision Log
*A record of critical technical decisions and fixed bugs to prevent regression.*

## 1. Environment Variables & Paths
* **Issue:** `load_dotenv()` often fails in nested folders (e.g., inside `backend/app/services/`).
* **Fix:** ALWAYS use `pathlib` to find the `.env` file relative to the script location, not the terminal's working directory.
* **Rule:** ```python
    from pathlib import Path
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    ```
* **Naming:** The key is `GEMINI_API_KEY`, not `GOOGLE_API_KEY`. Align code to `.env`.

## 2. Web Scraping (Playwright)
* **Issue:** SPAs like Workday/Greenhouse load an empty shell first. `wait_until="domcontentloaded"` returns blank pages (Score: 0%).
* **Fix:** 1. Use `wait_until="networkidle"` to wait for API calls to finish.
    2. Implement "Smart Locators" for specific ATS platforms (e.g., `[data-automation-id="jobPostingDescription"]` for Workday).
* **Rule:** Never assume a page is loaded just because the HTML body exists. Always verify text length > 200 chars.

## 3. Frontend-Backend Connection
* **Issue:** Browser blocks requests due to CORS policies.
* **Fix:** Backend `main.py` MUST include `CORSMiddleware` allowing `localhost:5173`.
* **Issue:** JSON key mismatch (`missing_skills` vs `missing_keywords`) caused UI to show "None found".
* **Rule:** Strict Contracts (`interfaces.py`) must be the source of truth for both Python and React types.

## 4. Architecture Standards
* **Style:** No script-kiddie code. Use Classes, Interfaces, and Dependency Injection.
* **Testing:** Always mock external services (Scraper/LLM) in tests to avoid costs/latency.