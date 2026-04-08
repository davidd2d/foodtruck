# FoodTruck SaaS — Project Overview

## 1️⃣ Project

A SaaS platform for food trucks allowing:

- Browse food trucks
- Filter by dietary preferences
- Display menu and ordering (Pro plan only)
- Dynamic branding per food truck
- AI-powered onboarding for fast FoodTruck + Menu + Branding creation

---

## 2️⃣ Architecture

- **Backend:** Django + Django REST Framework  
- **Frontend MVP:** Django Templates + Bootstrap CDN + Vanilla JS  
- **Database:** PostgreSQL  
- **Main apps:**
  - `accounts` — user management
  - `foodtrucks` — foodtruck & branding
  - `menu` — categories, items, options
  - `orders` — order management
  - `payments` — payment states, plans
  - `preferences` — dietary preferences
  - `onboarding` — AI-powered onboarding

---

## 3️⃣ AI Onboarding

- **User input only:** raw text, images (menu, logo), optional URL
- **AI analysis:**
  - Text → extract structured information
  - Images → extract menu items, prices, colors, logo
- **Colors:** converted to RGB/HEX for branding use
- **Logo:** always requested for future reuse
- **Validation:**
  - Correct price parsing (decimal/comma handling)
  - Logs and graceful fallback
- **Entity creation:**
  - Transactional (`atomic`)
  - Partial creation allowed
- **Frontend preview:** editable before final creation
- **Services only:** all business logic inside `services` modules
- **Tests required:**
  - Full image parsing
  - Entity creation
  - Price / color / logo validation

---

## 4️⃣ Media / Files

- **Structure:**

/media/foodtrucks/<slug>/covers/
/media/foodtrucks/<slug>/logos/
/media/foodtrucks/<slug>/menus/

- **Fallbacks:** missing logo/cover → placeholder
- **Templates:** use `{{ logo.url }}`, `{{ cover_image.url }}`

---

## 5️⃣ Menu & Plans

- **Menu visibility:** always shown (Free + Pro)
- **Ordering UI:** visible only for active Pro plan
- **Frontend JS:** separates menu loading from ordering UI
- **Tests:**
- Menu HTML and JS rendering
- Ordering gated by plan

---

## 6️⃣ Dynamic Navbar & Branding

- **Contents:**
- Left: FoodTruck logo
- Clickable FoodTruck name → toggles description + cover
- Category buttons (secondary color)
- Right: user menu hamburger (profile, orders, admin if authorized)
- **Colors:**
- Primary → navbar
- Secondary → category buttons, menu sections
- **Fallbacks:** default colors, placeholder logo/cover
- **Responsive:** mobile + desktop, scrollable categories

---

## 7️⃣ Translations

- All template text marked for translation
- `.po` files can be auto-translated (Codex possible)
- Instructions present in `README_frontend`

---

## 8️⃣ Tests & QA

- **Backend:** models, services, AI onboarding, plan gating, image parsing
- **Frontend:** menu loading, navbar branding, JS interactivity
- **End-to-end:**
- Menu always visible
- Ordering gated
- Description toggle
- Colors applied correctly
- **Logging:** all critical errors

---

## 9️⃣ Documentation

- README should include:
- AI Onboarding
- Media structure
- Dynamic Navbar / Branding
- Free vs Pro plan
- Frontend + backend tests
- Feature gating guarantees