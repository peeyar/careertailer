import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000'

export interface HistoryResult {
  match_score:       number
  missing_keywords:  string[]
  matching_keywords: string[]
  summary_reasoning: string
  docx_path?:        string | null
  changes_summary?:  string[]
  cover_letter?:     string
}

export interface HistoryItem {
  id:         string
  job_url:    string
  status:     string
  result:     HistoryResult | null
  created_at: string
}

interface HistorySidebarProps {
  refreshTrigger: number
  onSelect: (item: HistoryItem) => void
  selectedId: string | null
}

export default function HistorySidebar({ refreshTrigger, onSelect, selectedId }: HistorySidebarProps) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true)
      try {
        const response = await axios.get(`${API_BASE}/api/history`);
        if (response.data.status === 'success') {
          setHistory(response.data.data);
        } else {
          setError('Failed to load history.');
        }
      } catch (err) {
        setError('Server unreachable: ' + err);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [refreshTrigger]);

  const formatUrl = (urlStr: string) => {
    try {
      return new URL(urlStr).hostname.replace('www.', '');
    } catch {
      return 'Unknown';
    }
  };

  const scoreColor = (score: number) =>
    score >= 70 ? 'bg-green-100 text-green-800' :
    score >= 40 ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'

  return (
    <div className="w-80 bg-white border-l border-gray-200 h-screen overflow-y-auto flex flex-col shadow-lg">
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-800">📊 Past Analyses</h2>
      </div>

      <div className="flex-1 p-4">
        {loading && <p className="text-gray-500 text-sm animate-pulse">Loading history...</p>}
        {error   && <p className="text-red-500 text-sm">{error}</p>}

        {!loading && !error && history.length === 0 && (
          <p className="text-gray-500 text-sm text-center mt-10">No past analyses found.</p>
        )}

        <ul className="space-y-3">
          {history.map((item) => {
            const score    = item.result?.match_score ?? null
            const isSelected = item.id === selectedId
            const isDone   = item.status === 'done'

            return (
              <li
                key={item.id}
                onClick={() => isDone && onSelect(item)}
                className={`p-4 border rounded-lg transition-all
                  ${isDone ? 'cursor-pointer hover:shadow-md hover:border-indigo-300' : 'opacity-50 cursor-default'}
                  ${isSelected ? 'border-indigo-400 bg-indigo-50 shadow-md' : 'bg-white border-gray-200'}
                `}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium text-gray-800 truncate max-w-[160px]" title={item.job_url}>
                    {formatUrl(item.job_url)}
                  </span>
                  {score !== null ? (
                    <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${scoreColor(score)}`}>
                      {score}%
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-500">
                      {item.status}
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-400">
                  {new Date(item.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  );
}
