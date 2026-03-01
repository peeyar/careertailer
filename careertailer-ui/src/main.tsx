import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// StrictMode removed — it registers effects twice in development which
// causes duplicate axios interceptors and multiple polling loops.
// Re-enable only when debugging React lifecycle issues.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <App />
)