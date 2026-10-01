import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // tldraw is most of the bundle and changes only when we bump it. Its own chunk
        // means an app-code deploy doesn't re-download it. The editor route is already
        // lazy (App.tsx), so landing/auth visitors never fetch it at all.
        manualChunks(id) {
          if (id.includes('node_modules/tldraw') || id.includes('node_modules/@tldraw')) return 'tldraw'
        },
      },
    },
    // tldraw alone is ~1.9 MB min; the warning is expected for that one chunk. Raised just
    // past it so a *new* oversized chunk still warns.
    chunkSizeWarningLimit: 2000,
  },
})
