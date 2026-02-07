import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // ── Build optimizations ─────────────────────────────────────────
  build: {
    // Target modern browsers for smaller/faster output
    target: 'esnext',

    // Enable CSS code splitting
    cssCodeSplit: true,

    // Inline assets < 8kb as base64
    assetsInlineLimit: 8192,

    // Rollup chunk splitting
    rollupOptions: {
      output: {
        manualChunks: {
          // Separate React runtime into its own cacheable chunk
          'vendor-react': ['react', 'react-dom'],
        },
        // Clean chunk filenames with content hash for long-term caching
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },

    // Minification
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,   // Strip console.log in production
        drop_debugger: true,
        pure_funcs: ['console.log', 'console.debug', 'console.info'],
        passes: 2,            // Two-pass compression for better results
      },
      mangle: {
        safari10: true,
      },
      format: {
        comments: false,
      },
    },

    // Generate source maps for debugging (hidden from browser)
    sourcemap: false,

    // Chunk size warning threshold
    chunkSizeWarningLimit: 600,
  },

  // ── Dev server optimizations ────────────────────────────────────
  server: {
    // Pre-bundle dependencies for faster cold starts
    warmup: {
      clientFiles: [
        './src/App.jsx',
        './src/components/ChatArea.jsx',
        './src/components/Sidebar.jsx',
        './src/components/Header.jsx',
        './src/components/InputArea.jsx',
      ],
    },
  },

  // ── Dependency pre-bundling ─────────────────────────────────────
  optimizeDeps: {
    include: ['react', 'react-dom'],
  },
})
