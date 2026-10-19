import type { NextConfig } from "next";

// Where the Flask API lives. Locally that's `flask run`; on Vercel it's the Render URL.
// Read at BUILD time for the rewrite below, so set it on Vercel before the first deploy.
const backendUrl = (process.env.BACKEND_URL ?? "http://localhost:5000").replace(/\/$/, "");

// Content Security Policy: which sources the browser may load each kind of resource from.
// 'unsafe-inline' scripts are needed because Next.js puts small inline scripts in every page
// (a nonce would avoid that, but forces every page to render per request, which would lose the
// prerendered static shell). Everything else is locked to our own origin.
const contentSecurityPolicy = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'", // next/font and inline style attributes
  "img-src 'self' data: blob: https:", // data: blur placeholders; https: image URLs admins paste
  "font-src 'self'", // next/font serves the fonts from our own domain
  "connect-src 'self'", // the browser only calls /api on this origin (rewritten to Flask)
  "frame-ancestors 'none'", // nobody may put this site in an <iframe> (clickjacking)
  "form-action 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" }, // older browsers' version of frame-ancestors
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), browsing-topics=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  // Only in production builds: the dev server needs eval() for fast refresh.
  ...(process.env.NODE_ENV === "production" ? [{ key: "Content-Security-Policy", value: contentSecurityPolicy }] : []),
];

const nextConfig: NextConfig = {
  poweredByHeader: false, // don't advertise "X-Powered-By: Next.js"
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
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // The browser only ever talks to this site. Anything under /api is forwarded to Flask,
  // so cookies stay first-party and we never need CORS (see CLAUDE.md, Architecture rules).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
