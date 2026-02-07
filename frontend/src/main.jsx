import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Note: StrictMode double-mounts in dev which can cause loading state issues with async chat.
// Use <StrictMode><App /></StrictMode> if you need Strict Mode checks.
createRoot(document.getElementById('root')).render(<App />)
