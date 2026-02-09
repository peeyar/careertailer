import { useState } from 'react';
import axios from 'axios';
import { UploadCloud, FileText, CheckCircle, AlertCircle } from 'lucide-react';

// Define the shape of the data coming from Python
interface AnalysisResult {
  match_score: number;
  missing_keywords: string[];
  matching_keywords: string[];
  summary_reasoning: string;
}

function App() {
  const [jobUrl, setJobUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isAnalyze, setIsAnalyze] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const handleAnalyze = async () => {
    if (!file || !jobUrl) return;
    setIsAnalyze(true);
    setResult(null);
    
    const formData = new FormData();
    formData.append('resume', file);
    formData.append('job_url', jobUrl);

    try {
      // Send to Python Backend
      const response = await axios.post('http://127.0.0.1:8000/api/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(response.data);
    } catch (error) {
      console.error("Error analyzing:", error);
      alert("Analysis failed! Make sure your Python backend is running.");
    } finally {
      setIsAnalyze(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-800 font-sans">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 py-4 px-8 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2">
          <div className="bg-indigo-600 p-2 rounded-lg">
            <FileText className="text-white w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-gray-900">CareerTailor AI</h1>
        </div>
        <div className="text-sm text-gray-500">v0.3 (Frontend)</div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto py-12 px-6">
        <div className="text-center mb-10">
          <h2 className="text-3xl font-extrabold text-gray-900 mb-2">Tailor Your Resume</h2>
          <p className="text-lg text-gray-600">Paste a job link, upload your CV, and let AI do the rest.</p>
        </div>

        {/* Input Card */}
        <div className="bg-white rounded-xl shadow-lg p-8 border border-gray-100">
          
          {/* 1. Job URL Input */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">Job Description URL</label>
            <input 
              type="text" 
              placeholder="https://linkedin.com/jobs/..." 
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
            />
          </div>

          {/* 2. File Upload Zone */}
          <div className="mb-8">
            <label className="block text-sm font-medium text-gray-700 mb-2">Upload Resume (PDF)</label>
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 flex flex-col items-center justify-center bg-gray-50 hover:bg-indigo-50 transition cursor-pointer relative">
              <input 
                type="file" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                accept=".pdf"
                onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
              />
              {file ? (
                <div className="flex items-center gap-2 text-indigo-700 font-medium">
                  <CheckCircle className="w-6 h-6" />
                  <span>{file.name}</span>
                </div>
              ) : (
                <>
                  <UploadCloud className="w-10 h-10 text-gray-400 mb-3" />
                  <p className="text-gray-500">Click or Drag PDF here</p>
                </>
              )}
            </div>
          </div>

          {/* 3. Action Button */}
          <button 
            onClick={handleAnalyze}
            disabled={!file || !jobUrl || isAnalyze}
            className={`w-full py-4 rounded-lg font-bold text-lg text-white transition shadow-md
              ${(!file || !jobUrl) ? 'bg-gray-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700 hover:shadow-lg'}
            `}
          >
            {isAnalyze ? 'Analyzing with Gemini...' : 'Analyze Match'}
          </button>
        </div>

        {/* 4. Results Section (Appears after analysis) */}
        {result && (
          <div className="mt-8 bg-white rounded-xl shadow-lg p-8 border border-gray-100 animate-fade-in">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-2xl font-bold text-gray-900">Analysis Results</h3>
              <div className={`px-4 py-2 rounded-full font-bold text-white 
                ${result.match_score >= 70 ? 'bg-green-500' : result.match_score >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}>
                Score: {result.match_score}%
              </div>
            </div>

            {/* AI Summary Section (New!) */}
            <div className="mb-6 bg-indigo-50 p-4 rounded-lg border border-indigo-100 text-indigo-900">
               <h4 className="font-bold flex items-center gap-2 mb-2">
                 <FileText className="w-4 h-4" /> AI Summary
               </h4>
               <p className="text-sm leading-relaxed">{result.summary_reasoning}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Missing Keywords */}
              <div className="bg-red-50 p-4 rounded-lg border border-red-100">
                <h4 className="font-bold text-red-800 mb-2 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4"/> Missing Keywords
                </h4>
                <ul className="list-disc pl-5 text-red-700 space-y-1">
                  {result.missing_keywords && result.missing_keywords.length > 0 ? (
                    result.missing_keywords.map((skill: string, i: number) => (
                      <li key={i}>{skill}</li>
                    ))
                  ) : (
                    <li className="italic text-gray-500">None found (Good job!)</li>
                  )}
                </ul>
              </div>
              
              {/* Matching Keywords */}
              <div className="bg-green-50 p-4 rounded-lg border border-green-100">
                <h4 className="font-bold text-green-800 mb-2 flex items-center gap-2">
                  <CheckCircle className="w-4 h-4"/> Matching Keywords
                </h4>
                <ul className="list-disc pl-5 text-green-700 space-y-1">
                  {result.matching_keywords && result.matching_keywords.length > 0 ? (
                    result.matching_keywords.map((skill: string, i: number) => (
                      <li key={i}>{skill}</li>
                    ))
                  ) : (
                    <li>None found</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}

export default App;