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
