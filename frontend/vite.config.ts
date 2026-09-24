import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
    plugins: [
        react(),
        tailwindcss(),
    ],
    server: {
        host: "0.0.0.0",
        watch: {
            usePolling: true,
        },
        proxy: {
            "/api": {
                target: "http://backend:8000",
                changeOrigin: true,
            },
        },
    },
});