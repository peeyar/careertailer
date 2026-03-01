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
