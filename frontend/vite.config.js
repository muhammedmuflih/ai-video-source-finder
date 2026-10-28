import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const djangoProxy = {
  target: "http://127.0.0.1:8000",
  changeOrigin: false,
  configure(proxy) {
    // Django allauth builds Google's redirect_uri from the incoming Host.
    // Preserve the browser's Vite origin so it matches the Google OAuth URI.
    proxy.on("proxyReq", (proxyRequest, request) => {
      if (request.headers.host) {
        proxyRequest.setHeader("host", request.headers.host);
      }
    });
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": djangoProxy,
      "/accounts": djangoProxy,
      "/auth": djangoProxy
    }
  }
});
