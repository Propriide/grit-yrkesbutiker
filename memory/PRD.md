# PRD – Arbetskläder Order (Blåkläder B2B-beställningsapp)

## Original problem statement
Bygg en mobilapp för Android och iPhone. Vid registrering måste användaren ange mejladress, lösenord, telefonnummer och vilket företag de tillhör. Företag är obligatoriskt, organisationsnummer frivilligt. Inloggning med mejladress. Efter inloggning: bläddra i Blåkläders sortiment, öppna produkter, välja storlek och antal, varukorg, utcheckning med kommentarsfält (t.ex. önskat leveransdatum). Beställningen skickas via mejl till förutbestämd adress med artikelnummer, storlek, antal och företag. Adminkonton: ställa in mottagaradress, vilken ort konton hör till, administrera kundkonton.

## User choices
- Catalog: scrape blaklader.se (user accepted ToS risk)
- Email: Emergent-managed Resend
- Seeded admin: admin@blaklader.local / Admin123!
- Cities: admin-managed list, chosen at registration
- Design: Blåkläder identity – dark, orange/yellow, rugged

## Architecture
- Backend FastAPI (`server.py`, `scraper.py`, `emailer.py`), MongoDB (users, cities, products, orders, settings, counters)
- JWT bearer auth (bcrypt), roles customer/admin; token in SecureStore
- Scraper parses Next.js `__NEXT_DATA__` from 12 categories (≤4 pages each, ~595 products) + product pages for sizes; runs on first startup and via admin “Uppdatera sortiment”
- Frontend Expo Router: login, register, (tabs) Sortiment/Varukorg/Ordrar/Profil, product/[id], checkout, admin/{settings,cities,users,user/[id],orders}

## Implemented (2026-10-29)
- Registration/login, city picker, account blocking
- Catalog grid, search, category chips, PDP with colors/sizes/quantity, persistent cart, checkout with comment, order email (art.nr + color, size, qty, company, org nr, city, contact)
- Admin: recipient email, catalog sync, cities CRUD, customers edit/admin/disable/delete, all orders
- Validation: size/color per product, atomic order numbers, comment safety check

## Backlog
- P1: Customer-specific price lists / hide prices option
- P1: Order confirmation email copy to the customer
- P2: Scheduled automatic catalog refresh, favorites/reorder, CSV export of orders

## Update (2026-10-29)
- Added second seeded admin patrik.degerstam@yp.se (env SECOND_ADMIN_EMAIL/PASSWORD, insert-only seed, also runs in production on startup)
- Catalog now scraped from all 1236 products with Blåkläder category tree (8 groups + subcategories); shop has group + subcategory chip rows
- Login text "Inget konto? registrera dig här"
- Order email "Bekräfta order" button → web page /api/order-reply/{token}; free-text reply emailed to orderer, order marked Bekräftad, reply shown in app
- Email failure on checkout returns saved order with warning (no duplicate orders)
- Prices hidden everywhere (not stored/returned)
- Filter panel matching Blåkläder: Funktion, Kollektioner, Typ av plagg, Storlek, Färg, Certifiering, Varsel klassificering, Varsel samcertifiering, Material, Tvätt, Kollektion flamskydd, Miljömärkning (I lager not available from public site)
- Start screen (Hem tab) with YP Yrkesbutiker logo + store info per city (admin editable, default fallback); Orders moved to Profil → Mina ordrar
- Security: login lockout (5 fails/15 min), order-confirm link host allowlist (PUBLIC_HOST_SUFFIXES)
- Admin can create accounts (email/password/company/role) at /admin/user/new; admin toggle makes others admin
- Categories removed from Hem start screen; Färg filter available in filter sheet
- Forgot password (6-digit emailed code, 15 min, 5 attempts, 3 requests/15 min, neutral response), change password, edit own profile (/account/edit, /account/password)
- Shop: Herr/Dam picker after "Till sortimentet" + Herr/Dam/Alla toggle (gender from Blåkläder GenderSection; unisex + ungendered items in both)
- Colour filter shows matching colour image on cards and opens PDP in that colour
- Admin confirms orders in app (Alla ordrar → Bekräfta order sheet) – POST /api/admin/orders/{id}/reply, same email as web link
- Admin sets new password for any user (PUT /api/admin/users/{id}/password)
- In-app notifications (bell on Hem/Sortiment/Varukorg/Profil, /notifications) – orderer notified on confirm/decline, admins on new order; tap opens /order/[id]
- Order timeline (Skickad → Bekräftad/Nekad with messages); admin can decline (app sheet + email page "Neka")
- Colour filter ranking: solid colour first, combos later; card image + PDP colour use best match (src/color-match.ts)

## Refactor (fork 2)
- server.py (~1000 lines) split into: core.py (db, auth helpers, notify), routes/auth.py, routes/catalog.py (cities, start page, products), routes/orders.py (orders, notifications, email reply), routes/admin.py (settings, cities, users). server.py only wires routers + startup.
- All 48 routes unchanged; 135/136 backend tests pass (1 blocked by email-service rate limit).

## Iteration 10 (fork 2)
- Favourites (product + colour) per customer: /api/favorites, heart on product page, Profil → Mina favoriter.
- "Beställ igen" on own order detail adds all items to existing cart.
- Companies: grouped case/space-insensitively (/api/admin/companies, /api/admin/company-users); admin Kunder has Konton/Företag view + company page; CompanyInput (type or dropdown) on admin create/edit; company names snap to existing spelling on save/register.
- Shop: vertical category dropdown (accordion of sub-categories, closes on choice).

## Iteration 11 (fork 2)
- Admin company page: Personer/Ordrar tabs (/api/admin/company-orders); user page lists that person's orders (/api/admin/users/{id}/orders).
- Header home button (ScreenHeader) returns to last visited tab via router.dismissTo (src/navigation.ts). Tab jumps from stack screens use dismissTo (no duplicate tab stacks).
- Sortiment: heart button next to bell opens favourites, with count badge.

## Iteration 12 (fork 2)
- Prices scraped again (SEK excl. VAT, never exposed to customers); order_value stored on orders (hidden for customers).
- Credits: per user (credits_enabled, credits), company toggle (db.companies, inherited by new users), 1 credit/100 kr awarded once on admin confirm; admin add/remove; /api/credits; header CreditsBadge + /credits screen. No spending yet.
- Checkout: mandatory delivery (store / parcel_box / ship + address).
- Home: favourites strip + 3 latest orders.
- Shop: purchased products first (newest, colour-filter aware) with "Köpt tidigare"; admin eye button hides products per city (hidden_city_ids) – customers never see them (list, detail, favourites, ordering).
- Admin broadcast (/admin/broadcast) → in-app notifications to customers (all or one city). Real push postponed by user.
- Theme: navy (Blåkläder) + logo red #D0102E. Custom font: waiting for user to re-upload (first file was empty).

## Iteration 13 (fork 2)
- Custom fonts: United Sans Cond (Bold/Black) headings, Gotham (Book/Medium) body.
- Order status flow: Inväntar bekräftelse → Bekräftad / Nekad → Klar (POST /api/admin/orders/{id}/ready, in-app notification "Ordern är klar"; push postponed by user).
- "Beställ igen" in expanded order card; home sections collapsible; checkout address row aligned.

## Iteration 14 (fork 2)
- Order card layout fixed (number + badge row, date below). Reply sheet extracted (src/components/reply-sheet.tsx) and usable on order detail for admins (notification → order → confirm/decline directly).
- Home sections collapsed by default.
- Saved shipping addresses (users.addresses, GET /api/addresses) with dropdown in checkout.

## Iteration 15 (fork 2)
- Credits badge compact (icon + number), shop title row no longer overflows.
- Shipping: recipient, address, postal code, city all required. Saved addresses can be removed (POST /api/addresses/remove).
- Confirm message optional (default "Din order är bekräftad."), decline still requires a reason (app + email form).

## Iteration 15 (fork 2, part 2)
- Users have `name` (required at registration, editable in profile/admin; admin search matches name).
- Start page: "Välkommen <namn>", store pill "Du handlar nu från butiken i <ort>", centered layout. Registration has "Din butik" section with city picker.
- Cart: credits estimate (POST /api/credits/estimate, only credit total returned) + tap product to open product page.
- Note: older backend test files register without `name` and will now get 422.

## Iteration 16 (fork 2)
- Admin card label "Dold i Borås, Göteborg"; admin-only HiddenFilter in Sortiment (GET /api/products?hidden_in=any|<city_id>).
- Cart: change size via SizeSheet (sizes from product), merges identical lines.
- App identifiers: iOS bundleIdentifier & Android package = se.yp.yrkesbutiker (app.json)

## Iteration 17 (fork 2) – Push + branding
- Emergent managed push (SuprSend relay): backend routes/push.py (/api/register-push auth-bound, send_push, push_safe); every notify() also pushes (order new/confirmed/declined/ready → /order/{id}); broadcast pushes in chunks of 100 → /notifications. EMERGENT_PUSH_KEY=placeholder (set by deployer).
- Frontend: expo-notifications plugin, module-scope handler/channel, tap handlers + weekly denied nudge in app/_layout.tsx; src/push.ts registers on login/app open.
- google-services.json + GoogleService-Info.plist in frontend root (package/bundle se.yp.yrkesbutiker).
- App name "Grit" (app.json name; src/brand.ts APP_NAME used on login). Icon/adaptive/splash/favicon generated from YP logo on white.

## Iteration 18 (fork 2) – PWA + Web Push
- PWA: frontend/public/{index.html (manifest, apple meta, viewport-fit=cover), manifest.json, sw.js (network-first HTML, no /api caching, skipWaiting+claim → auto update, push + notificationclick), icons/}. SW registered in app/_layout (src/webpush.ts), reload on controllerchange, update check on foreground.
- Web Push (VAPID, pywebpush): backend routes/webpush.py (/api/webpush/public-key, /subscribe, /unsubscribe, /notification-prefs GET/PUT); keys in backend/.env (VAPID_*). push_safe sends native + web push, filtered by user prefs (orders/offers).
- Notification settings screen /account/notifications (prefs + enable on this device; iOS shows "add to home screen" hint).
- Broadcast can target selected companies (companies list) in addition to city.
- Hosting: frontend/netlify.toml (expo export web → dist, SPA redirect, no-cache sw). Emergent deploy does NOT host Expo web.

## Iteration 18 (refactor, no behavior change)
- Moved email/reply-page HTML templates from routes/orders.py to backend/order_emails.py
- Moved notification endpoints to backend/routes/notifications.py (registered in server.py)
- Regression tests: tests/test_iter18_refactor_regression.py, tests/test_iter18_order_emails_equivalence.py (HTML identical to before)
- Note: Emergent mobile deployment does not host a public web frontend; PWA install link needs a web deployment (Full Stack web agent). Native push needs EMERGENT_PUSH_KEY (set at publish) + native build.

## Iteration 19 – launch prep (web PWA)
- Renamed to GRIT (app.json, manifest, apple title, sw.js, brand.ts APP_NAME constant)
- Web build calls backend at relative "/api" (same build works on any domain, incl. future custom domain); native still uses EXPO_PUBLIC_BACKEND_URL
- `npx expo export -p web` verified (static PWA build OK)
- Security probe: all 28 /api/admin/* routes return 403 for customers and 401 without login
- Live test purchase B10089 (recipient temporarily delivered+grit-launch@resend.dev): email sent, confirmed, ready, customer notifications OK; recipient restored to prii_de@hotmail.com
- Decision: production = new Emergent "Full Stack App" (web) deployment with clean DB; seeds admin patrik.degerstam@yp.se via SECOND_ADMIN_* env; catalog auto-scrapes on empty DB. Add custom domain to PUBLIC_HOST_SUFFIXES when connected.
- Test data kept until user approves deletion.
- Admin seeds now optional per env pair (ADMIN_EMAIL/PASSWORD, SECOND_ADMIN_EMAIL/PASSWORD); production sets only SECOND_ADMIN_* (patrik).
- /app/DEPLOY_WEB.md: instructions for the new Full Stack web job (serve expo web export, env vars, launch checklist).
- .env files added to .gitignore so secrets are not pushed to GitHub.

## Iteration 20 – web PWA launch test (new job)
- Backend code unchanged. Preview DB clean: only admin patrik.degerstam@yp.se (admin@blaklader.local deleted; preview .env still has ADMIN_* so a backend restart re-seeds it here – production must not set ADMIN_*).
- Catalog auto-scraped on empty DB: 1236 products. Order recipient set to patrik.degerstam@yp.se.
- `expo export -p web` → frontend/dist; frontend/serve-dist.js = static SPA server with /api proxy (local test on :3001).
- DEPLOY_WEB checklist 1,2,3,4,6 tested OK (backend + browser on dist build). Remaining: 5 (install on real iPhone/Android) and real web push on device – need public URL.
- Launch blocked: this is an Expo job; its deployment has no public web URL. Launch via "Add Web App" / new Web App job after user approval. Production secrets still to set: new JWT_SECRET, new VAPID pair, remove ADMIN_* live slot.
- Iteration 20b: requirements.txt litellm URL '#sha256' fragment removed (resolver conflict); clean-venv install + pip check + server import OK; backend regression 30/30.
- New production secrets generated into backend/prod_secrets.env (gitignored via *.env, chmod 600): JWT_SECRET, VAPID pair, ADMIN_EMAIL=patrik (so the first seed pair points to patrik → no test admin). User enters them in the secrets card (live slot).
- Admin can change own password in Profil → Byt lösenord (min 6 chars).
