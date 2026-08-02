import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import topLevelAwait from "vite-plugin-top-level-await";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [
    vue(),
    topLevelAwait({
      promiseExportName: "__tla",
      promiseImportName: (i) => `__tla_${i}`,
    }),
  ],
  resolve: {
    alias: [
      { find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
      // Exact match only — a bare "three" → "three/webgpu" rewrite would turn
      // `import … from "three/webgpu"` into the non-exported `three/webgpu/webgpu`.
      { find: /^three$/, replacement: "three/webgpu" },
    ],
  },
  server: {
    port: 9101,
    strictPort: true,
    proxy: {
      "/proxy/control": {
        target: process.env.CONTROL_PLANE_PROXY || "http://127.0.0.1:9100",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/control/, ""),
      },
      "/proxy/activation": {
        target: process.env.ACTIVATION_PROXY || "http://127.0.0.1:9103",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/activation/, ""),
      },
      "/proxy/copilot": {
        target: process.env.COPILOT_PROXY || "http://127.0.0.1:9104",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/proxy\/copilot/, ""),
      },
    },
  },
});
