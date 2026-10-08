import vue from '@vitejs/plugin-vue'
import { URL, fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const apiPaths = ['/auth', '/upload', '/status', '/chunks', '/download', '/files']

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: fileURLToPath(new URL('../static/app', import.meta.url)),
    emptyOutDir: true,
  },
  server: {
    proxy: Object.fromEntries(apiPaths.map((path) => [path, 'http://localhost:7800'])),
  },
  test: {
    environment: 'jsdom',
  },
})
