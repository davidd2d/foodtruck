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
- **Pickup slot recommendation:** the foodtruck detail page now selects the best available pickup window automatically using immediate pickup first, then current schedule slots, then the next active schedule.
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

- UI language remains handled by Django i18n (`LocaleMiddleware`, `.po/.mo`, `gettext`)
- Business content now has a separate primary language at the foodtruck level via `FoodTruck.default_language`
- This content language drives:
  - AI onboarding generation output
  - active menu default naming
  - AI menu recommendation generation and fallback copy
- Phase 1 rule: one primary content language per foodtruck (`en`, `fr`, `es`)
- Phase 2 path: `django-parler` remains available for future per-field multi-translation of foodtruck/menu content
- `.po` files are still only for interface strings, not for foodtruck/menu business data
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
-- **Logging:** all critical errors

---

## 🔟 Location Management

- **Owner URLs:** `/orders/foodtruck/<slug>/locations/`, `/create/`, `/<id>/edit/`, `/<id>/delete/` expose location CRUD for owners tied to schedules.
- **Data:** each location stores address lines, city, postal code, country, GPS coordinates, notes, and an `is_active` flag for soft deletion while linking back to its `ServiceSchedule` for future slot scoring.
- **Fallback:** if no custom location exists for a given schedule, the food truck’s base latitude/longitude serve as the administrative fallback.
- **UI:** a “Locations” link now appears in the foodtruck owner dropdown; the list page hints at the base fallback and shows actions to edit/delete.
- **Tests:** backend coverage includes `orders.tests.test_locations` (model validation) and `orders.tests.test_location_views` (CRUD + permissions), ensuring owner-only access.

---

## 1️⃣1️⃣ Automatic Pickup Selection

- **Page:** `/foodtrucks/<slug>/` now recommends the best pickup window automatically.
- **Priority:** immediate pickup > remaining slots in the current service > first slot of the next available service.
- **Backend:** `FoodTruck.get_current_service_schedule()`, `FoodTruck.get_next_available_service_schedule()`, `FoodTruck.get_recommended_pickup_slots()`, and `FoodTruck.get_best_default_pickup_slot()` centralize the selection logic.
- **Frontend:** the cart pickup selector receives `default_pickup_slot_id` and preselects the recommended slot on load.
- **Fallback UX:** if no slot is available, the selector stays disabled and displays a clear unavailable message.

---

## 1️⃣1️⃣ Order Dashboard

- **Owner route:** `/orders/foodtruck/<slug>/dashboard/` exposes the operator kitchen board for the food truck owner.
- **Owner APIs:** `/orders/api/dashboard/` returns lightweight DRF JSON for polling, and `/orders/api/<order_id>/status/` applies owner-only status transitions.
- **Order lifecycle:** customer checkout still creates a `draft`, submission moves the order to `pending`, then the owner workflow becomes `confirmed -> preparing -> ready -> completed`, with `cancelled` only allowed from `pending` or `confirmed`.
- **Business rules:** transition validation lives in `Order.transition_to()` and `OrderService.update_status()`; views stay thin and only handle auth, validation, and serialization.
- **Payments:** payment state remains on `payments.Payment`; capturing payment no longer forces an operator status change on the order.
- **Performance:** dashboard queries use optimized queryset helpers and lightweight serializers to support AJAX polling every 10 seconds.
- **Logging:** rejected transitions and dashboard failures are logged with structured context (`order_id`, owner, target status).
- **Tests:** backend coverage includes transition rules, dashboard API filtering/permissions, and payment compatibility with the new lifecycle.

---

## 9️⃣ AI Menu Intelligence

**Phase 1: MVP Foundation (Rules-Based)**

- **Module:** `ai_menu` app — AI recommendation engine for menu items
- **Model:** `AIRecommendation` stores structured suggestions
  - Fields: `item` (FK), `recommendation_type` (free_option, paid_option, bundle, pricing), `payload` (JSON), `status` (pending, accepted, rejected)
  - Manager methods: `pending()`, `accepted()`, `for_foodtruck()`, `for_item()`
  - Business methods: `is_pending()`, `accept()`, `reject()`
- **Service:** `MenuAnalyzerService` — rules-based item analysis
  - Method: `analyze_item(item)` → returns structured suggestions
  - Rule engine detects item category (burger, bowl, taco, other)
  - Generates free & paid option suggestions + bundle recommendations
  - Extensible for future LLM integration (same interface)
- **Backend:**
  - Indexes: `(item, status)`, `(recommendation_type, status)`, `(status, -created_at)`
  - Admin interface with actions to accept/reject bulk recommendations
  - Full test suite: 21 tests (model, queryset, service)

**Phase 2: LLM Integration (OpenAI)**

- **Service:** `AIRecommendationGeneratorService` — intelligent recommendation generation
  - Main method: `generate_and_store_for_item(item)` — generates & persists recommendations
  - Workflow:
    1. Prepares item context (name, description, category, foodtruck cuisine type, foodtruck content language)
    2. Builds structured prompt asking OpenAI to generate:
       - Detected item category (burger, bowl, taco, salad, pizza, etc.)
       - 3-4 free options (enhance value perception)
       - 3-4 paid upsells (realistic pricing €0.50-€4.00)
       - 2-3 bundle suggestions (increase AOV)
    3. Calls OpenAI API via centralized `OpenAIService`
    4. Parses JSON response with robust error handling
    5. Validates response structure
    6. Persists recommendations as `AIRecommendation` records (status: pending)
    7. Falls back to `MenuAnalyzerService` if API fails/returns invalid JSON
  - Language behavior:
    - Prompt still uses stable English instructions for model steering where useful
    - Customer-facing suggestion content is requested in the foodtruck content language
    - Each recommendation stores its generation language in `AIRecommendation.language_code`
    - Rule-based fallback suggestions are localized too, avoiding English-only fallback text on French/Spanish trucks
  - Prompt constraints:
    - English prompt optimized for GPT-4o
    - Forces strict JSON output format
    - Requests realistic, actionable suggestions
    - Domain-aware (food truck pricing/operations)
  - Error handling:
    - API timeout/errors → automatic fallback to MVP rules
    - Invalid JSON → fallback (logged)
    - Database errors → caught and returned as error status
    - Empty descriptions → handled gracefully
  - Database management:
    - Clears old pending recommendations before creating new ones
    - Preserves accepted/rejected history
    - Uses atomic transactions for data consistency
  - Logging: DEBUG (calls), INFO (success), WARNING (API errors), ERROR (exceptions)

- **Backend:**
  - Full test suite: 20 tests covering:
    - Context preparation (with/without description)
    - OpenAI response parsing (JSON with/without markdown)
    - Response validation (structure, types, required fields)
    - Successful generation flow
    - Fallback scenarios (invalid JSON, API errors)
    - Database persistence (correct types, payloads)
    - Error handling (invalid items, database errors, cleanup)
    - Recommendation history preservation (accepted/rejected)
  - Uses mocking for OpenAI tests (no API calls in CI/CD)
  - RecommendationType payloads:
    - `free_option`: `{name, reason}`
    - `paid_option`: `{name, suggested_price, reason}`
    - `bundle`: `{name, items[], reason}`

- **Deployment:**
  - Requires: `OPENAI_API_KEY` environment variable
  - Uses OpenAI client from `config.services.openai_client`
  - Caching disabled for recommendations (always fresh)
  - Model: GPT-4o, max_tokens: 1500

- **Future Phases:**
  - Phase 3: Owner dashboard analysis workflow
  - Phase 4: Recommendation scoring + ranking
  - Phase 5: Owner review UI + auto-acceptance rules
  - Phase 6: A/B testing recommendations effectiveness

**Phase 3: Owner Dashboard Workflow (AJAX)**

- **Owner dashboard:** new route to review AI recommendations per menu item
  - Page: `/dashboard/foodtruck/<slug>/menu-ai/`
  - Uses existing owner navbar conventions
  - Lists active menu categories and items with a per-item AI action button
- **Secure endpoint:** `POST /dashboard/menu/items/<id>/analyze-ai/`
  - Authentication required
  - Strict tenant isolation via `item -> menu -> foodtruck -> owner`
  - CSRF protected
  - JSON response contains grouped recommendations plus rendered HTML partial
- **Thin views / service orchestration:**
  - `AIRecommendationDashboardService` handles:
    - active menu loading for dashboard display
    - per-item rate limiting (basic abuse protection)
    - orchestration of `AIRecommendationGeneratorService`
    - grouping recommendations into UI sections (`free_options`, `paid_options`, `bundles`)
  - Views only validate access, call service, and return HTML/JSON
- **UI integration:**
  - New reusable partial: `templates/ai_menu/partials/recommendations_panel.html`
  - New JS module: `static/js/ai_menu/item_ai_recommendations.js`
  - Loading state, error state, and fallback state handled without page reload
  - Owners can accept or reject pending recommendations directly from the dashboard
  - Accepted and rejected recommendations remain visible in dashboard history with an undo action
- **Menu linkage:**
  - Accepting a `free_option` recommendation auto-creates a `menu.Option` inside `AI Free Customizations`
  - Accepting a `paid_option` recommendation auto-creates a `menu.Option` inside `AI Paid Add-ons`
  - Accepting a `bundle` recommendation now auto-creates a real `menu.Combo` with `ComboItem` rows in a dedicated `Combos` category
  - Resetting an accepted recommendation back to pending removes the generated option and deletes the empty group if needed
  - Generated combos can be reviewed and edited from an owner-facing combo management screen
  - Combos with a confirmed effective price are now orderable through the cart and checkout flow

---

## 1️⃣2️⃣ Owner Profile

- **Canonical route:** `/accounts/foodtruck/<slug>/profile/`
- **Compatibility route:** `/accounts/profile/` redirects to the first foodtruck owned by the authenticated user
- **Scope:** owner-only page tied to a specific foodtruck slug
- **Purpose:** lets the foodtruck owner update their account details while keeping the page inside the foodtruck management context
- **Displayed context:** foodtruck name, slug, content language, owner email verification state
- **Backend tests:**
  - owner dashboard access
  - non-owner isolation
  - AJAX analysis success path
  - CSRF handling
  - rate limiting
  - accept / reject actions from dashboard
  - reset accepted/rejected recommendations to pending
  - automatic creation/removal of `OptionGroup` and `Option`
  - graceful AI error handling

---

## 🔟 Documentation

- README should include:
- AI Onboarding
- Media structure
- Dynamic Navbar / Branding
- Free vs Pro plan
- Frontend + backend tests
- Feature gating guarantees
- AI Menu Intelligence (Phase 1 & Phase 2)
- AI Menu dashboard workflow (Phase 3)
