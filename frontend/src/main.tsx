import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
async function start() {
    const root = createRoot(document.getElementById('root')!);
    if (import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEMO === 'true' && window.location.pathname === '/demo') {
        const { default: DemoApp } = await import('./demo/DemoApp');
        root.render(<StrictMode><aside className="demo-banner">DEMONSTRAÇÃO — dados fictícios</aside><DemoApp /></StrictMode>);
    }
    else
        root.render(<StrictMode><App /></StrictMode>);
}
void start();
