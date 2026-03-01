import { createClient } from '@supabase/supabase-js'

// These are the FRONTEND/public env vars — safe to expose in browser
// Add to careertailer-ui/.env:
//   VITE_SUPABASE_URL=https://yourproject.supabase.co
//   VITE_SUPABASE_ANON_KEY=your-anon-key

const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL  as string
const supabaseKey  = import.meta.env.VITE_SUPABASE_ANON_KEY as string

if (!supabaseUrl || !supabaseKey) {
  throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in .env')
}

// Singleton — import this wherever you need auth or DB access
export const supabase = createClient(supabaseUrl, supabaseKey)
