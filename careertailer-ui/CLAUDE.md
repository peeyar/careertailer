# Frontend (careertailer-ui)

React 18 + TypeScript + Vite + Tailwind CSS + Supabase JS + Axios

## Commands

```bash
npm run dev       # port 5173
npm run build
npm run lint
```

## Structure

```
src/
├── lib/
│   └── supabase.ts        # singleton Supabase client — import this everywhere
├── components/
│   └── HistorySidebar.tsx
├── App.tsx                # main app — auth gate, ingest, analyze, results
├── AuthPage.tsx           # email/password login + signup
└── main.tsx               # React root — StrictMode intentionally removed
```

## Key Patterns

**Auth:** Supabase JS session → JWT auto-attached via Axios interceptor  
Interceptor registered once using `interceptorRef` — prevents duplicate registration  
`verify_token` on backend returns `(user_id, token)` tuple — both needed for RLS

**Resume logic (priority order):**
1. User uploads file in Step 2 → backend sets use_rag=False
2. hasMasterResume=true + no file → RAG used automatically
3. Neither → Analyze button disabled

**Job result delivery:**  
Supabase Realtime subscription (primary) + setInterval fallback (3s)  
Call `stopListening()` on done/failed — removes both the channel AND the interval

**hasMasterResume state:**  
Set on login via `GET /api/ingest/status`  
Set to true immediately after successful ingest — don't wait for re-fetch

## .env Required

```
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY   # publishable key — safe for frontend
```

## Do Not

- Re-enable StrictMode — causes duplicate Axios interceptors and polling loops
- Use localStorage or sessionStorage — not supported in this environment
- Set hasMasterResume based only on onAuthStateChange — also check after ingest

## What's Next

Phase 5 — download button + docx generation UI  
See FRONTEND_README.md for full pending list and parking lot items

## Phase 5 — Resume Download UI Spec

### New state in App.tsx

```typescript
const [isGenerating, setIsGenerating] = useState(false)
const [docxReady, setDocxReady]       = useState(false)
```

### When results arrive (job.status === 'done')

Check `job.result.docx_path` — if truthy, set `docxReady(true)`.

### Download button

Replaces the current "Apply for this Job" layout at the bottom of results.
Show BOTH buttons side by side:

```
[ ⬇ Download Tailored Resume ]    [ Apply for this Job ↗ ]
```

Download button behavior:
- onClick: GET /api/resume/{job_id} with Authorization header
- Use axios with responseType: 'blob'
- Create object URL, trigger anchor click, revoke URL
- Show spinner while downloading (isGenerating state)
- If docx_path is null/missing: show "Resume generation failed" in gray, Apply button still works

### axios blob download pattern

```typescript
const response = await axios.get(`${API_BASE}/api/resume/${currentJobId}`, {
  responseType: 'blob'
})
const url = window.URL.createObjectURL(new Blob([response.data]))
const link = document.createElement('a')
link.href = url
link.setAttribute('download', 'tailored_resume.docx')
document.body.appendChild(link)
link.click()
link.remove()
window.URL.revokeObjectURL(url)
```

### Do not

- Do not show the download button until job.status === 'done'
- Do not disable the Apply button if docx generation failed
- Do not use window.open for the download — must use blob pattern above for auth headers