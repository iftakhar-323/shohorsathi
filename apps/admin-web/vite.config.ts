import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const gateway = process.env.GATEWAY_URL ?? "http://localhost:8088";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5175,
    proxy: { "/api": { target: gateway, ws: true }, "/media": gateway },
  },
});
