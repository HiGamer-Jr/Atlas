/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
const cert = process.env.HIATLAS_TLS_CERT;
const key = process.env.HIATLAS_TLS_KEY;
if (!!cert !== !!key)
    throw new Error('Configure both HIATLAS_TLS_CERT and HIATLAS_TLS_KEY');
export default defineConfig({
    base: './',
    plugins: [react()],
    server: {
        host: '127.0.0.1',
        port: 5174,
        https: cert && key ? { cert: readFileSync(cert), key: readFileSync(key) } : undefined,
        proxy: { '/api': { target: process.env.HIATLAS_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
    },
    test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
});
