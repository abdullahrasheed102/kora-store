import type { NextConfig } from "next";

// Where the Flask API lives. Locally that's `flask run`; on Vercel it's the Render URL.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:5000";

const nextConfig: NextConfig = {
  // Pages render a static "shell" at build time; data parts stream in per request (see docs/guide/02-catalog.md).
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only ever talks to this site. Anything under /api is forwarded to Flask,
  // so cookies stay first-party and we never need CORS (see CLAUDE.md, Architecture rules).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
