import { type VercelConfig } from '@vercel/config/v1';

// Resolve the external origin at deployment time so the rewrite contains a real URL.
const value = process.env.BACKEND_URL?.trim();
if (!value) throw new Error('Set BACKEND_URL to the Render HTTPS origin before deploying.');
const backend = new URL(value);
if (backend.protocol !== 'https:' || backend.pathname !== '/' || backend.search || backend.hash || backend.username || backend.password) {
  throw new Error('BACKEND_URL must be an HTTPS origin only, without /api, query parameters, or credentials.');
}
const backendOrigin = backend.origin;

export const config: VercelConfig = {
  framework: 'vite',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    { source: '/api/:path*', destination: `${backendOrigin}/api/:path*` },
  ],
  headers: [
    { source: '/(.*)', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Permissions-Policy', value: 'camera=(self), microphone=(), geolocation=()' },
    ] },
    { source: '/api/:path*', headers: [{ key: 'Cache-Control', value: 'private, no-store' }] },
  ],
};
