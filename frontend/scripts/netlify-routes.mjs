import { writeFileSync } from 'node:fs';

const raw = process.env.ADF_BACKEND_URL?.trim();
if (!raw) throw new Error('Set ADF_BACKEND_URL in Netlify to your deployed Python backend HTTPS origin, then redeploy.');
const url = new URL(raw);
if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
  throw new Error('ADF_BACKEND_URL must be an HTTPS origin only, with no credentials, path, query or fragment.');
}
writeFileSync(new URL('../dist/_redirects', import.meta.url),
  `/api/* ${url.origin}/api/:splat 200!\n/* /index.html 200\n`);
console.log('Netlify API proxy and frontend routes generated.');
