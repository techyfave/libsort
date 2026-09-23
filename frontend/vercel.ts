import type { VercelConfig } from '@vercel/config/v1';

const backend = process.env.BACKEND_URL?.replace(/\/$/, '');
if (!backend || !/^https:\/\/[^/]+$/.test(backend)) {
  throw new Error('Set BACKEND_URL to the HTTPS Render service origin, without a path.');
}

export const config: VercelConfig = {
  framework: 'vite',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    { source: '/api/:path*', destination: `${backend}/api/:path*` },
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
