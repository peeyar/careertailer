import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { UploadCloud, FileText, CheckCircle, AlertCircle, BookOpen, Loader2, LogOut, Clock, XCircle, ExternalLink } from 'lucide-react'
import HistorySidebar from './components/HistorySidebar'
import AuthPage from './AuthPage'
import { supabase } from './lib/supabase'
import type { Session } from '@supabase/supabase-js'

const API_BASE = 'http://127.0.0.1:8000'

interface AnalysisResult {
  match_score:       number
  missing_keywords:  string[]
  matching_keywords: string[]
  summary_reasoning: string
}

type IngestStatus = 'idle' | 'loading' | 'success' | 'skipped' | 'error'
type JobStatus    = 'pending' | 'processing' | 'done' | 'failed' | null

function App() {
  // ── Auth state ───────────────────────────────────────────────────────────
  const [session, setSession] = useState<Session | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  // ── Ingest state ─────────────────────────────────────────────────────────
  const [masterResume, setMasterResume]   = useState<File | null>(null)
  const [ingestStatus, setIngestStatus]   = useState<IngestStatus>('idle')
  const [ingestMessage, setIngestMessage] = useState('')
  const [ingestChunks, setIngestChunks]   = useState(0)

  const [hasMasterResume, setHasMasterResume] = useState<boolean | null>(null)  // null = loading

  // ── Analyze state ─────────────────────────────────────────────────────────
  const [jobUrl, setJobUrl]               = useState('')
  const [file, setFile]                   = useState<File | null>(null)
  const [isSubmitting, setIsSubmitting]   = useState(false)
  const [, setCurrentJobId]   = useState<string | null>(null)
  const [jobStatus, setJobStatus]         = useState<JobStatus>(null)
  const [result, setResult]               = useState<AnalysisResult | null>(null)
  const [jobError, setJobError]           = useState('')
  const [refreshSidebar, setRefreshSidebar] = useState(0)

  const realtimeRef = useRef<ReturnType<typeof supabase.channel> & { _fallback?: ReturnType<typeof setInterval> } | null>(null)

  // ── Auth listener ─────────────────────────────────────────────────────────
  const checkMasterResume = (session: Session) => {
    axios.get(`${API_BASE}/api/ingest/status`, {
      headers: { Authorization: `Bearer ${session.access_token}` }
    }).then(res => setHasMasterResume(res.data.has_master_resume))
      .catch(() => setHasMasterResume(false))
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setAuthLoading(false)
      if (session) checkMasterResume(session)  // check on initial load too
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) checkMasterResume(session)
      else setHasMasterResume(null)
    })

    return () => subscription.unsubscribe()
  }, [])

  // ── Axios interceptor — attach JWT to every request ───────────────────────
  // Registered once using a ref — prevents StrictMode double-registration
  const interceptorRef = useRef<number | null>(null)
  useEffect(() => {
    if (interceptorRef.current !== null) return  // already registered
    interceptorRef.current = axios.interceptors.request.use(async (config) => {
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`
      }
      return config
    })
    return () => {
      if (interceptorRef.current !== null) {
        axios.interceptors.request.eject(interceptorRef.current)
        interceptorRef.current = null
      }
    }
  }, [])

  // ── Job polling ───────────────────────────────────────────────────────────
  const stopListening = () => {
    if (realtimeRef.current) {
      if (realtimeRef.current._fallback) {
        clearInterval(realtimeRef.current._fallback)
      }
      supabase.removeChannel(realtimeRef.current)
      realtimeRef.current = null
    }
  }

  const handleJobUpdate = (job: Record<string, unknown>) => {
    console.log('🔄 handleJobUpdate called:', job.status, job)
    setJobStatus(job.status as JobStatus)
    if (job.status === 'done') {
      console.log('✅ Job done, setting result:', job.result)
      stopListening()
      setResult(job.result as AnalysisResult)
      setRefreshSidebar(prev => prev + 1)
    } else if (job.status === 'failed') {
      stopListening()
      setJobError((job.error_message as string) || 'Analysis failed.')
    }
  }

  const startListening = (jobId: string) => {
    stopListening()

    // 1. Realtime subscription — fires instantly when job row updates
    realtimeRef.current = supabase
      .channel(`job-${jobId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'analysis_jobs',
          filter: `id=eq.${jobId}`,
        },
        (payload: unknown) => handleJobUpdate((payload as { new: Record<string, unknown> }).new)
      )
      .subscribe((status: string) => {
        console.log('Realtime status:', status)
      })

    // 2. Fallback poll — one request every 3s in case Realtime misses the update
    // (e.g. job completes before subscription is established, or RLS blocks Realtime)
    const fallbackInterval = setInterval(async () => {
      try {
        console.log('⏱️ Fallback poll firing for job:', jobId)
        const response = await axios.get(`${API_BASE}/api/jobs/${jobId}`)
        const job = response.data
        console.log('⏱️ Fallback poll result:', job.status)
        if (job.status === 'done' || job.status === 'failed') {
          clearInterval(fallbackInterval)
          handleJobUpdate(job)
        }
      } catch (err) {
        console.error('⏱️ Fallback poll error:', err)
        clearInterval(fallbackInterval)
      }
    }, 3000)

    // Store interval so we can clear it on unmount
    realtimeRef.current._fallback = fallbackInterval
  }

  useEffect(() => () => stopListening(), [])  // cleanup on unmount

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  const handleIngest = async () => {
    if (!masterResume) return
    setIngestStatus('loading')
    setIngestMessage('')

    const formData = new FormData()
    formData.append('resume', masterResume)

    try {
      const response = await axios.post(`${API_BASE}/api/ingest`, formData)
      const { status, message, chunks } = response.data
      setIngestStatus(status === 'skipped' ? 'skipped' : 'success')
      setIngestMessage(message)
      setIngestChunks(chunks)
      if (status !== 'error') setHasMasterResume(true)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setIngestStatus('error')
      setIngestMessage(error.response?.data?.detail || 'Ingestion failed.')
    }
  }

  const handleAnalyze = async () => {
    if ((!file && !hasMasterResume) || !jobUrl) return
    setIsSubmitting(true)
    setResult(null)
    setJobError('')
    setJobStatus(null)
    setCurrentJobId(null)

    const formData = new FormData()
    if (file) formData.append('resume', file)  // optional if master resume exists
    formData.append('job_url', jobUrl)

    try {
      const response = await axios.post(`${API_BASE}/api/analyze`, formData)
      const { job_id } = response.data
      setCurrentJobId(job_id)
      setJobStatus('pending')
      startListening(job_id)
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } }
      if (error.response?.status === 429) {
        setJobError('Daily limit reached. You can analyze 5 jobs per day.')
      } else {
        setJobError(error.response?.data?.detail || 'Failed to start analysis.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // ── Loading / Auth gate ───────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    )
  }

  if (!session) {
    return <AuthPage />
  }

  // ── Status helpers ────────────────────────────────────────────────────────
  const ingestStatusConfig = {
    idle:    { color: 'text-gray-500',   bg: '' },
    loading: { color: 'text-indigo-600', bg: 'bg-indigo-50' },
    success: { color: 'text-green-700',  bg: 'bg-green-50'  },
    skipped: { color: 'text-yellow-700', bg: 'bg-yellow-50' },
    error:   { color: 'text-red-700',    bg: 'bg-red-50'    },
  }

  const jobStatusLabel: Record<string, { label: string; color: string; icon: React.ReactElement }> = {
    pending:    { label: 'Job queued...',      color: 'text-gray-600',   icon: <Clock className="w-4 h-4 animate-pulse" /> },
    processing: { label: 'Analyzing with AI...', color: 'text-indigo-600', icon: <Loader2 className="w-4 h-4 animate-spin" /> },
    done:       { label: 'Analysis complete!', color: 'text-green-700',  icon: <CheckCircle className="w-4 h-4" /> },
    failed:     { label: 'Analysis failed.',   color: 'text-red-700',    icon: <XCircle className="w-4 h-4" /> },
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-gray-50 text-gray-800 font-sans overflow-hidden">
      <div className="flex-1 flex flex-col h-full overflow-y-auto">

        {/* Header */}
        <header className="bg-white border-b border-gray-200 py-4 px-8 flex items-center justify-between shadow-sm sticky top-0 z-10">
          <div className="flex items-center gap-2">
            <div className="bg-indigo-600 p-2 rounded-lg">
              <FileText className="text-white w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">CareerTailor AI</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{session.user.email}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 transition"
            >
              <LogOut className="w-4 h-4" /> Sign out
            </button>
          </div>
        </header>

        <main className="max-w-4xl mx-auto py-12 px-6 w-full space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-extrabold text-gray-900 mb-2">Tailor Your Resume</h2>
            <p className="text-lg text-gray-600">Step 1: Ingest your master resume once. Step 2: Analyze any job.</p>
          </div>

          {/* ── Step 1: Ingest ── */}
          <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
            <div className="flex items-center gap-2 mb-1">
              <div className="bg-indigo-100 p-2 rounded-lg">
                <BookOpen className="text-indigo-600 w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Step 1 — Ingest Master Resume</h3>
            </div>
            <p className="text-sm text-gray-500 mb-5 ml-11">
              Upload your full resume once. We embed it into your personal knowledge base.
            </p>

            <div className="border-2 border-dashed border-indigo-200 rounded-xl p-6 flex flex-col items-center bg-indigo-50 hover:bg-indigo-100 transition cursor-pointer relative mb-4">
              <input
                type="file"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                accept=".pdf,.docx,.txt"
                onChange={e => {
                  setMasterResume(e.target.files?.[0] || null)
                  setIngestStatus('idle')
                  setIngestMessage('')
                }}
              />
              {masterResume ? (
                <div className="flex items-center gap-2 text-indigo-700 font-medium">
                  <CheckCircle className="w-6 h-6" /><span>{masterResume.name}</span>
                </div>
              ) : (
                <>
                  <UploadCloud className="w-8 h-8 text-indigo-400 mb-2" />
                  <p className="text-indigo-600 font-medium">Click or Drag Master Resume here</p>
                  <p className="text-xs text-indigo-400 mt-1">PDF, DOCX, or TXT</p>
                </>
              )}
            </div>

            <button
              onClick={handleIngest}
              disabled={!masterResume || ingestStatus === 'loading'}
              className={`w-full py-3 rounded-lg font-bold text-white transition flex items-center justify-center gap-2
                ${!masterResume || ingestStatus === 'loading' ? 'bg-gray-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
            >
              {ingestStatus === 'loading'
                ? <><Loader2 className="w-5 h-5 animate-spin" /> Embedding...</>
                : 'Ingest into Knowledge Base'}
            </button>

            {ingestStatus !== 'idle' && ingestStatus !== 'loading' && (
              <div className={`mt-4 p-3 rounded-lg ${ingestStatusConfig[ingestStatus].bg}`}>
                <p className={`text-sm font-medium ${ingestStatusConfig[ingestStatus].color}`}>
                  {ingestStatus === 'success' && `✅ ${ingestMessage} (${ingestChunks} chunks stored)`}
                  {ingestStatus === 'skipped' && `⚡ ${ingestMessage}`}
                  {ingestStatus === 'error'   && `❌ ${ingestMessage}`}
                </p>
              </div>
            )}
          </div>

          {/* ── Step 2: Analyze ── */}
          <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
            <div className="flex items-center gap-2 mb-5">
              <div className="bg-green-100 p-2 rounded-lg">
                <FileText className="text-green-600 w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">Step 2 — Analyze a Job</h3>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">Job Description URL</label>
              <input
                type="text"
                placeholder="https://linkedin.com/jobs/..."
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
                value={jobUrl}
                onChange={e => setJobUrl(e.target.value)}
              />
            </div>

            <div className="mb-8">
              {hasMasterResume && !file ? (
                // Master resume is active — show badge, let user optionally override
                <div className="border-2 border-green-200 bg-green-50 rounded-xl p-5 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-6 h-6 text-green-600" />
                    <div>
                      <p className="text-sm font-semibold text-green-800">Master resume active</p>
                      <p className="text-xs text-green-600">Your resume knowledge base is ready — no upload needed</p>
                    </div>
                  </div>
                  <label className="text-xs text-indigo-600 font-medium cursor-pointer hover:underline">
                    Use different resume
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.txt"
                      onChange={e => setFile(e.target.files?.[0] || null)}
                    />
                  </label>
                </div>
              ) : (
                // No master resume — show full upload zone
                <>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Upload Resume {hasMasterResume ? '(overrides master resume)' : '(PDF, DOCX, or TXT)'}
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 flex flex-col items-center bg-gray-50 hover:bg-indigo-50 transition cursor-pointer relative">
                    <input
                      type="file"
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      accept=".pdf,.docx,.txt"
                      onChange={e => setFile(e.target.files?.[0] || null)}
                    />
                    {file ? (
                      <div className="flex items-center gap-2 text-indigo-700 font-medium">
                        <CheckCircle className="w-6 h-6" />
                        <span>{file.name}</span>
                        <button
                          onClick={e => { e.stopPropagation(); setFile(null) }}
                          className="ml-2 text-xs text-red-500 hover:underline"
                        >clear</button>
                      </div>
                    ) : (
                      <>
                        <UploadCloud className="w-10 h-10 text-gray-400 mb-3" />
                        <p className="text-gray-500">Click or Drag resume here</p>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>

            <button
              onClick={handleAnalyze}
              disabled={(!file && !hasMasterResume) || !jobUrl || isSubmitting || (jobStatus === 'pending' || jobStatus === 'processing')}
              className={`w-full py-4 rounded-lg font-bold text-lg text-white transition shadow-md
                ${((!file && !hasMasterResume) || !jobUrl || isSubmitting)
                  ? 'bg-gray-300 cursor-not-allowed'
                  : 'bg-green-600 hover:bg-green-700'}`}
            >
              {isSubmitting ? 'Submitting...' : 'Analyze Match'}
            </button>

            {/* Live job status */}
            {jobStatus && jobStatus !== 'done' && (
              <div className={`mt-4 p-4 rounded-lg bg-gray-50 border border-gray-200 flex items-center gap-3 ${jobStatusLabel[jobStatus].color}`}>
                {jobStatusLabel[jobStatus].icon}
                <span className="text-sm font-medium">{jobStatusLabel[jobStatus].label}</span>
              </div>
            )}

            {jobError && (
              <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-100">
                <p className="text-sm text-red-700">❌ {jobError}</p>
              </div>
            )}
          </div>

          {/* ── Results ── */}
          {result && (
            <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold text-gray-900">Analysis Results</h3>
                <div className={`px-4 py-2 rounded-full font-bold text-white
                  ${result.match_score >= 70 ? 'bg-green-500' : result.match_score >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}>
                  Score: {result.match_score}%
                </div>
              </div>

              <div className="mb-6 bg-indigo-50 p-4 rounded-lg border border-indigo-100 text-indigo-900">
                <h4 className="font-bold flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4" /> AI Summary
                </h4>
                <p className="text-sm leading-relaxed">{result.summary_reasoning}</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-red-50 p-4 rounded-lg border border-red-100">
                  <h4 className="font-bold text-red-800 mb-2 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" /> Missing Keywords
                  </h4>
                  <ul className="list-disc pl-5 text-red-700 space-y-1">
                    {result.missing_keywords?.length > 0
                      ? result.missing_keywords.map((s, i) => <li key={i}>{s}</li>)
                      : <li className="italic text-gray-500">None found</li>}
                  </ul>
                </div>
                <div className="bg-green-50 p-4 rounded-lg border border-green-100">
                  <h4 className="font-bold text-green-800 mb-2 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" /> Matching Keywords
                  </h4>
                  <ul className="list-disc pl-5 text-green-700 space-y-1">
                    {result.matching_keywords?.length > 0
                      ? result.matching_keywords.map((s, i) => <li key={i}>{s}</li>)
                      : <li>None found</li>}
                  </ul>
                </div>
              </div>

              {/* Apply CTA — after user has read the full analysis */}
              <div className="mt-6 pt-6 border-t border-gray-100">
                <a
                  href={jobUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full flex items-center justify-center gap-2 py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-lg rounded-xl transition shadow-md"
                >
                  <ExternalLink className="w-5 h-5" />
                  Apply for this Job
                </a>
                <p className="text-center text-xs text-gray-400 mt-2">Opens the job posting in a new tab</p>
              </div>

            </div>
          )}
        </main>
      </div>

      <HistorySidebar refreshTrigger={refreshSidebar} />
    </div>
  )
}

export default App