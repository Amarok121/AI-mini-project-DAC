import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  optimizeDeps: {
    include: ["markdown-it", "markdown-it-footnote", "dompurify"]
  },
  server: {
    port: 5173,
    proxy: {
      "/verify": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/report": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});

