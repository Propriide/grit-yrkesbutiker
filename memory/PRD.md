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
