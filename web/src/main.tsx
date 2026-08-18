import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Bundled, not fetched: the CSS has always asked for Inter and always fallen back to the
// system face, so weights and metrics drifted between machines. A variable font ships one
// file and gives us the whole weight axis.
import '@fontsource-variable/inter'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
