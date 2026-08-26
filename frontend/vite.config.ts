/// <reference types="vitest/config" />
import {defineConfig} from 'vite'; import react from '@vitejs/plugin-react';
const apiTarget=process.env.V061_API_URL||'http://localhost:8000';
export default defineConfig({plugins:[react()],build:{rollupOptions:{output:{manualChunks(id){if(id.includes('node_modules/@tiptap')||id.includes('node_modules/prosemirror'))return 'editor-vendor';if(id.includes('node_modules/@tanstack'))return 'query-vendor';if(id.includes('node_modules/react')||id.includes('node_modules/scheduler'))return 'react-vendor';}}}},test:{exclude:['tests/e2e/**','tests/visual/**','node_modules/**','dist/**']},server:{port:5173,proxy:{'/api':apiTarget}},preview:{port:4173,proxy:{'/api':apiTarget}}});
