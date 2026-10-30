# GRIT – instructions for the new web (Full Stack) job

Goal: run GRIT (YP Yrkesbutiker) as a production PWA on a permanent Emergent HTTPS address,
using this repo's **existing backend unchanged** and the **existing Expo web build** as the frontend.
Do NOT rewrite the app in React – the Expo code already exports a complete PWA.

## Frontend (static PWA)
- Build: `cd frontend && npx expo export -p web --output-dir dist` (verified working).
- Output contains index.html, manifest.json (name GRIT, display standalone), sw.js (service worker + web push), icons/.
- Serve `frontend/dist` as a single-page app on port 3000 (all unknown paths -> index.html).
  `manifest.json`, `sw.js` and `/icons/*` must be served from the site root.
- The web build calls the backend on relative `/api` (same origin), so it works on any domain without rebuilding.
- Keep `frontend/app.json`, `google-services.json`, `GoogleService-Info.plist` – they are for later Android/iOS builds.

## Backend (FastAPI, unchanged) – `backend/server.py`, routes in `backend/routes/`
Environment variables for production:
- `MONGO_URL`, `DB_NAME` – provided by the platform (fresh, empty database).
- `JWT_SECRET` – NEW random value for production.
- `SECOND_ADMIN_EMAIL=patrik.degerstam@yp.se`, `SECOND_ADMIN_PASSWORD=12345` – the only admin seeded.
- Do NOT set `ADMIN_EMAIL` / `ADMIN_PASSWORD` (the test admin admin@blaklader.local must not exist in production).
- `EMERGENT_EMAIL_KEY`, `EMAIL_FROM_NAME="Arbetskläder Beställning"` – order emails.
- `PUBLIC_HOST_SUFFIXES` – must include the production host suffix, e.g. `.emergent.host,.emergentagent.com`
  (add the custom domain, e.g. `grit.yp.se`, when it is connected). Order email confirm links fail with "Ogiltig värd" otherwise.
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT=mailto:patrik.degerstam@yp.se` – web push.
  Generate a new pair for production (`vapid --gen` from py_vapid, or reuse preview keys).
- `EMERGENT_PUSH_KEY` – native push (managed, set at publish).

On first start with an empty database the backend automatically:
- creates indexes, the order counter and the admin account (insert-only, never resets passwords),
- creates default cities (Stockholm, Göteborg, Malmö – admin can edit),
- scrapes the full Blåkläder catalog in the background (takes several minutes; check `/api/products` total afterwards).

## Before launch – checklist
1. Log in as patrik.degerstam@yp.se, verify the admin panel; verify admin@blaklader.local does NOT exist.
2. Admin > Inställningar: set the order recipient email (required – orders are rejected without it).
3. Verify the catalog import finished (product count ~840+, categories present).
4. Full browser test: register customer, login, catalog, sizes, cart, checkout (store/parcel box/ship), order email
   (use delivered@resend.dev as a temporary recipient), confirm/decline link, mark ready, notifications, web push.
5. PWA: install on iPhone (Safari > Share > Add to Home Screen; web push needs iOS 16.4+ and the installed app)
   and Android (Chrome > menu > Install app).
6. Admin routes: all `/api/admin/*` must return 403 for customers.
7. Never drop collections; production data must survive redeploys.
