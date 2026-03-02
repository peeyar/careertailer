import { useState } from 'react'
import { FileText, Copy, Check } from 'lucide-react'

interface Props {
  coverLetter: string
}

export default function CoverLetterCard({ coverLetter }: Props) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(coverLetter)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-100">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-bold text-indigo-900 flex items-center gap-2">
          <FileText className="w-4 h-4" /> Cover Letter
        </h4>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition"
        >
          {copied ? <><Check className="w-3.5 h-3.5" /> Copied!</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
        </button>
      </div>
      <pre className="text-sm text-indigo-900 whitespace-pre-wrap font-sans leading-relaxed">
        {coverLetter}
      </pre>
    </div>
  )
}
