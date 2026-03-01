# CareerTailor UI — Frontend README

**Stack:** React 18 · TypeScript · Vite · Tailwind CSS · Axios · Supabase JS  
**Last updated:** Phase 2 + Phase 3 complete

---

## Project Structure

```
careertailer-ui/
├── src/
│   ├── lib/
│   │   └── supabase.ts             # Supabase JS client singleton
│   ├── components/
│   │   └── HistorySidebar.tsx      # Past analyses sidebar
│   ├── App.tsx                     # Main app — auth gate, ingest, analyze, results
│   ├── AuthPage.tsx                # Login + signup UI
│   └── main.tsx                    # React root (StrictMode removed)
├── .env
└── package.json
```

---

## Environment Variables

```bash
# careertailer-ui/.env
VITE_SUPABASE_URL=https://yourproject.supabase.co
VITE_SUPABASE_ANON_KEY=your-publishable-key    # NOT the legacy secret or service key
```

---

## Authentication Flow

**Library:** `@supabase/supabase-js`  
**Method:** Email + Password (Supabase Auth)  
**Token type:** ES256 JWT issued by Supabase

```
App loads
    │
    ├── supabase.auth.getSession()
    │     Session exists  → show main app, check master resume status
    │     No session      → show AuthPage
    │
    └── onAuthStateChange listener
          Login  → setSession, checkMasterResume()
          Logout → clear session, show AuthPage
```

**JWT attached to every request via Axios interceptor:**
```typescript
axios.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})
```
Interceptor registered once using a `useRef` guard — prevents duplicate registration in development.

---

## App State

```typescript
// Auth
session: Session | null          // Supabase session
authLoading: boolean             // true while getSession() is pending

// Step 1 — Ingest
masterResume: File | null        // selected file for ingestion
ingestStatus: idle|loading|success|skipped|error
ingestMessage: string
ingestChunks: number             // chunk count returned by backend
hasMasterResume: boolean | null  // null=loading, true=chunks exist in DB

// Step 2 — Analyze
jobUrl: string
file: File | null                // optional custom resume for this analysis
isSubmitting: boolean
currentJobId: string | null
jobStatus: pending|processing|done|failed|null
result: AnalysisResult | null
jobError: string
refreshSidebar: number           // incremented to trigger sidebar reload
```

---

## Step 1 — Master Resume Ingestion

1. User selects PDF/DOCX/TXT file
2. POST `/api/ingest` with `Authorization` header
3. Backend parses → SHA-256 dedup check → chunk → embed → save to pgvector
4. On success/skipped: `setHasMasterResume(true)` — Step 2 badge updates immediately
5. Status feedback: green (success), yellow (skipped — same file), red (error)

---

## Step 2 — Job Analysis

**Resume source logic (in order of priority):**
1. User uploads a file in Step 2 → that file is used, RAG is skipped
2. `hasMasterResume === true` and no file → master resume RAG chunks used automatically
3. Neither → Analyze button stays disabled

**Master resume active state:**
- Green badge: "Master resume active — Your resume knowledge base is ready, no upload needed"
- "Use different resume" link — hidden file input lets user optionally override
- If user selects an override file: shows filename + "clear" button to revert to master

**Analyze button enabled when:**
```typescript
(!file && !hasMasterResume) || !jobUrl || isSubmitting  // any true = disabled
```

---

## Async Job Flow

```
User clicks Analyze Match
    │
    ├── POST /api/analyze → { job_id, status: "pending" }
    │
    ├── startListening(job_id) called
    │     │
    │     ├── Supabase Realtime subscription on analysis_jobs WHERE id = job_id
    │     │     Fires instantly on UPDATE → done | failed
    │     │
    │     └── Fallback: setInterval every 3s → GET /api/jobs/{job_id}
    │           Clears itself when status = done | failed
    │
    └── On done:
          stopListening() → removes Realtime channel + clears fallback interval
          setResult(job.result) → results card renders
          setRefreshSidebar() → sidebar reloads
```

**Why Realtime + fallback:**  
Supabase Realtime fires instantly when the DB row updates. The fallback poll exists because Realtime can occasionally miss events if the subscription isn't fully established before the job completes (fast jobs on cold connections).

---

## Results Display

```
┌─────────────────────────────────────────┐
│ Analysis Results              Score: 78% │
├─────────────────────────────────────────┤
│ 🤖 AI Summary                           │
│    Paragraph explaining the match...    │
├────────────────┬────────────────────────┤
│ ❌ Missing     │ ✅ Matching            │
│  • Kubernetes  │  • React               │
│  • Terraform   │  • TypeScript          │
│                │  • FastAPI             │
├─────────────────────────────────────────┤
│         [ Apply for this Job ↗ ]        │
│    Opens the job posting in a new tab   │
└─────────────────────────────────────────┘
```

Score badge color: green ≥70, yellow ≥40, red <40  
Apply button: opens `jobUrl` in new tab (`target="_blank"`)

---

## AuthPage

- Email + password fields
- Toggle between Login and Sign Up modes
- Enter key submits
- Sign Up shows confirmation message to check email
- Errors displayed inline (wrong password, email taken, etc.)

---

## Key Design Decisions

**StrictMode removed (`main.tsx`)**  
React 18 StrictMode mounts components twice in development. This caused the Axios interceptor to register twice, creating duplicate requests. Removed to prevent this. Re-enable only when debugging React lifecycle issues.

**Supabase Realtime over pure polling**  
Pure `setInterval` polling created race conditions — multiple in-flight requests arriving after `done` status was received. Realtime pushes exactly one event per status change.

**`interceptorRef` guard**  
The Axios interceptor registration is wrapped in a `useRef` check — if `interceptorRef.current !== null`, skip registration. Prevents any duplicate interceptor regardless of how many times the effect runs.

---

## ✅ Completed

### Phase 3 — RAG UI
- [x] Step 1: Master resume ingestion flow with drag-and-drop dropzone
- [x] Ingest status feedback (success / skipped / error) with color-coded banners
- [x] Chunk count shown on successful ingestion
- [x] `hasMasterResume` state — checked on login and updated after ingest
- [x] Step 2: Green "Master resume active" badge when knowledge base is ready
- [x] Optional resume upload — hidden when master resume is active
- [x] "Use different resume" override link
- [x] Custom resume upload bypasses RAG (frontend sends file, backend sets `use_rag=False`)
- [x] "Clear" button to revert from custom file back to master resume

### Phase 2 — Auth + Async Queue
- [x] `AuthPage.tsx` — email/password login + signup with inline error handling
- [x] `supabase.ts` singleton client using publishable key
- [x] Auth gate in `App.tsx` — unauthenticated users see AuthPage only
- [x] Loading spinner while `getSession()` resolves
- [x] JWT auto-attached to every Axios request via interceptor
- [x] User email shown in header with Sign Out button
- [x] Async analyze flow — POST returns `job_id` immediately
- [x] Supabase Realtime subscription per job — instant result delivery
- [x] Fallback interval poll (3s) in case Realtime misses an event
- [x] Live job status indicator (queued → analyzing → complete)
- [x] 429 rate limit error handled with friendly message
- [x] Apply button — full-width CTA at bottom of results, opens job URL in new tab
- [x] `HistorySidebar` refresh triggered after analysis completes
- [x] StrictMode removed to prevent duplicate interceptor registration

---

## 🔴 Pending

### Phase 4 — Scraper UX
- [ ] Show which site is being scraped (LinkedIn, Workday, etc.) in status indicator
- [ ] Detect and surface scrape failures clearly (login-gated jobs, paywalled roles)
- [ ] "Try again" button on scrape failure without re-uploading resume

### Phase 5 — Resume Generation UI
- [ ] Download button after analysis — triggers `.docx` generation
- [ ] Loading state while `.docx` is being generated
- [ ] Preview panel — show which keywords were injected and where
- [ ] "Regenerate" option if user wants a different tailoring pass

### General UX
- [ ] Mobile responsive layout (currently desktop-only)
- [ ] Dark mode
- [ ] Keyboard navigation and accessibility audit (ARIA labels, focus management)
- [ ] Toast notifications instead of inline banners for transient messages

---

## 🅿️ Parking Lot

### Multi-Resume Profiles
User can have up to 5 named resume profiles (e.g. "Senior SWE", "Engineering Manager").
- Profile selector dropdown in Step 2 (replaces current badge)
- Most recently used = default
- Upload a one-off resume for a single analysis without saving to any profile
- Settings page to rename, delete, or reorder profiles
- On hitting 5-profile limit: modal prompts which profile to replace
- **Build after Phase 5** — real users will inform the actual UX needs