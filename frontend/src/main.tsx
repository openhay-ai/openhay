import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { ensureToken } from './lib/auth'

async function bootstrap() {
  try {
    await ensureToken();
  } catch {
    // Non-blocking: continue rendering even if auth fails
  } finally {
    createRoot(document.getElementById("root")!).render(<App />);
  }
}

bootstrap();
