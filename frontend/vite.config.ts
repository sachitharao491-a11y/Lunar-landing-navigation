import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "src",
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const file = id.replaceAll("\\", "/");
          if (file.includes("/node_modules/three/")) return "three-core";
          if (file.includes("/node_modules/three-stdlib/")) return "three-loaders";
          if (file.includes("/node_modules/@react-three/drei/")) return "three-drei";
          if (file.includes("/node_modules/@react-three/fiber/")) return "three-fiber";
          if (file.includes("/node_modules/recharts/") || /\/node_modules\/d3-/.test(file)) return "charts";
          if (file.includes("/node_modules/framer-motion/") || /\/node_modules\/motion-/.test(file)) return "motion";
          if (/\/node_modules\/(react|react-dom|scheduler)\//.test(file)) return "react-core";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["test/setup.ts"],
    restoreMocks: true,
    clearMocks: true,
  },
});
