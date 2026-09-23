# Netlify frontend and Python backend

The Netlify site serves React. A separate Python service processes documents and
stores accounts. Both must be deployed before signup works.

## 1. Push deployment files

```powershell
git add api.py test_api.py netlify.toml frontend/scripts/netlify-routes.mjs Dockerfile .dockerignore render.yaml DEPLOYMENT.md
git commit -m "Prepare persistent Python backend and Netlify API proxy"
git push origin main
```

The Netlify build now requires ADF_BACKEND_URL. A build without this variable
fails intentionally instead of publishing another disconnected frontend.

## 2. Create the backend in Render

Sign in at https://dashboard.render.com and choose New > Blueprint. Connect
the syedjawadshah2001/ADF-CHECK repository and main branch. Render reads
render.yaml. Review the paid service and disk costs before creating it.
The disk preserves SQLite accounts, saved formatting profiles and the JWT key
across deployments. Do not remove the disk or increase worker count.

Wait for deployment to succeed, then copy the actual HTTPS service URL Render
assigns. Open that URL followed by /api/health; it should return status ok and
version 2.0. Opening the backend root is not a frontend test.

The Docker layout deliberately keeps code in /app/utilities to support the
existing Python package imports regardless of the repository checkout name.
Only root Python files and requirements are copied into the image.

## 3. Connect Netlify

In the Netlify site's environment variables, add ADF_BACKEND_URL with the
actual backend HTTPS origin (no /api suffix). Make it available to builds.
Trigger a new production deployment. The build generates an /api/* proxy rule
before the React fallback. Cookies stay on the frontend domain.

Netlify settings: base frontend, build command from netlify.toml, publish dist.
Keep the repository-root netlify.toml active; do not override its build command.

The backend's ADF_ALLOWED_ORIGINS is configured for
https://autodocu.netlify.app. Update it to an exact comma-separated list if you
add a custom domain. Do not use a wildcard. ADF_SECURE_COOKIES stays 1 on HTTPS.

## 4. Verify live

Open https://autodocu.netlify.app/api/health and confirm the backend JSON.
Create an account, log out, log back in, upload a small DOCX, preview and approve
corrections, then download a report. Test a fresh browser session too.
Redeploy the backend and confirm the account still works. Temporary document
reviews disappear after backend restarts; download them first.

Local accounts are not automatically copied to the new server. Create a new
account online. Never commit the local database or signing key.

AI credentials are optional backend-only environment variables. Formatting,
signup and local document assistance do not need an AI key.

Prepared configuration and local tests do not prove live deployment. Render
account access and the assigned backend URL are required to finish activation.

References: https://render.com/docs/blueprint-spec and
https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/
