import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Self-hosted variable fonts — no Google CDN at runtime.
import '@fontsource-variable/jetbrains-mono';
import '@fontsource-variable/geist';

import './styles/tokens.css';
import { App } from './app';

const root = document.getElementById('root');
if (!root) throw new Error('#root not found in index.html');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
