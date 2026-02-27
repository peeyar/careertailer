import { useState, useEffect } from 'react';
import axios from 'axios';

// 1. Explicitly export the interface to keep TypeScript perfectly happy
export interface HistoryItem {
  id: string;
  job_url: string;
  match_score: number;
  created_at: string;
}

// 2. Define the props this component accepts
interface HistorySidebarProps {
  refreshTrigger: number;
}

export default function HistorySidebar({ refreshTrigger }: HistorySidebarProps) {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 3. Add refreshTrigger to the dependency array
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:8000/api/history');
        if (response.data.status === 'success') {
          setHistory(response.data.data);
        } else {
          setError('Failed to load history.');
        }
      } catch (err) {
        setError('Server unreachable. :' + err);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [refreshTrigger]); // <--- This tells React: "Re-run this fetch if refreshTrigger changes!"

  const formatUrl = (urlStr: string) => {
    try {
      const domain = new URL(urlStr).hostname.replace('www.', '');
      return domain;
    } catch {
      return 'Unknown Company';
    }
  };

  return (
    <div className="w-80 bg-white border-l border-gray-200 h-screen overflow-y-auto flex flex-col shadow-lg">
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-800">📊 Past Analyses</h2>
      </div>

      <div className="flex-1 p-4">
        {loading && <p className="text-gray-500 text-sm animate-pulse">Loading history...</p>}
        {error && <p className="text-red-500 text-sm">{error}</p>}
        
        {!loading && !error && history.length === 0 && (
          <p className="text-gray-500 text-sm text-center mt-10">No past analyses found.</p>
        )}

        <ul className="space-y-4">
          {history.map((item) => (
            <li key={item.id} className="p-4 border rounded-lg hover:shadow-md transition-shadow bg-white">
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium text-gray-800 truncate" title={item.job_url}>
                  {formatUrl(item.job_url)}
                </span>
                <span className={`px-2 py-1 text-xs font-bold rounded-full ${
                  item.match_score >= 80 ? 'bg-green-100 text-green-800' :
                  item.match_score >= 60 ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                }`}>
                  {item.match_score}%
                </span>
              </div>
              <div className="text-xs text-gray-400">
                {new Date(item.created_at).toLocaleDateString()}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}