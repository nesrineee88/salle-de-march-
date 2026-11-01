import type { NextConfig } from "next";

// L'interface appelle /api/... ; Next.js transmet ces appels au serveur Python (pas de CORS à configurer).
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default config;
