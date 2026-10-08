// Web application entry point.
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './styles.css';
import './map/styles.css';
import './market/styles.css';

const root = document.getElementById('root');
if (!root) throw new Error('No se encuentra el contenedor de la aplicación');

createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
