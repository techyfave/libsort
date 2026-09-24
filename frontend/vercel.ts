import { routes, deploymentEnv, type VercelConfig } from '@vercel/config/v1';

// Resolved at request time from the Vercel env var BACKEND_URL (Render origin only:
// https://your-service.onrender.com — no /api suffix). Set it in Vercel before deploy.
const backendOrigin = deploymentEnv('BACKEND_URL');

export const config: VercelConfig = {
  framework: 'vite',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    routes.rewrite('/api/:path*', `${backendOrigin}/api/:path*`),
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
