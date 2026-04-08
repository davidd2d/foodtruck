# FoodTruck SaaS — Frontend Guide

## 1️⃣ Objectives

- Dynamic navbar per food truck
- Branding (colors, logo, cover)
- Interactive, responsive menu
- Free / Pro plan handling
- Translation-ready templates

---

## 2️⃣ Navbar

- **Partial template:** `_foodtruck_navbar.html`
- **Contents:**
  - Left: FoodTruck logo
  - FoodTruck name (click → toggle description + cover)
  - Category buttons (secondary color)
  - Right: user menu hamburger (profile, orders, admin if allowed)
- **JS:**
  - Toggle description/cover
  - Menu always loaded; ordering UI gated separately
- **CSS:**
  - Sticky-top navbar
  - Horizontal scroll for categories
  - Colors applied from model (primary/secondary)

---

## 3️⃣ Menu

- Loaded via JS
- Free plan: menu visible, ordering message “unavailable”
- Pro plan: menu + ordering drawer
- Frontend tests:
  - Menu loads correctly
  - Ordering drawer visible according to plan
  - Categories scrollable

---

## 4️⃣ Branding

- `FoodTruck` model helpers:
  - `get_primary_color()`
  - `get_secondary_color()`
  - `get_logo_url()`
- Colors and logo applied dynamically
- Cover + description toggle on name click

---

## 5️⃣ Media & Fallback

- Media structure per main README
- Placeholders for missing logo/cover
- Menu always visible even if JS fails (SSR fallback)

---

## 6️⃣ Translations

- Templates marked for i18n (`{% trans %}`)
- `.po` files can be auto-translated
- Always verify placeholders

---

## 7️⃣ Frontend Tests

- Navbar branding applied
- Menu visibility Free / Pro
- JS toggle description
- Responsive design
- Colors applied correctly

---

## 8️⃣ Documentation / Notes

- Any frontend modification must be documented in `README_frontend`
- Clearly indicate which components or JS scripts are impacted by branding or plan gating