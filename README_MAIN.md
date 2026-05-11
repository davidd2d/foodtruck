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

  ## 1️⃣3️⃣ AI Business Engine (Production Layer)

  The project now includes a structured AI Business Intelligence layer designed for deterministic reliability first, with optional AI refinement.

  ### Scope

  - Spot scoring (location intelligence)
  - Pricing suggestions
  - Event opportunity detection
  - Revenue prediction

  ### Persisted models

  - `foodtrucks.LocationScore`
    - fields: `foodtruck`, `latitude`, `longitude`, `score`, `demand_score`, `competition_score`, `event_score`, `created_at`
  - `menu.PricingSuggestion`
    - fields: `item`, `suggested_price`, `current_price`, `confidence_score`, `reason`, `created_at`
  - `analytics.Event`
    - fields: `name`, `latitude`, `longitude`, `start_date`, `end_date`, `expected_attendance`, `created_at`
  - `analytics.EventOpportunity`
    - fields: `foodtruck`, `event`, `opportunity_score`, `predicted_revenue`, `created_at`
  - `analytics.RevenuePrediction`
    - fields: `foodtruck`, `date`, `predicted_revenue`, `confidence_score`, `created_at`

  ### Services (business logic only)

  - `analytics.services.location_ai_service.LocationAIService`
    - `compute_score(lat, lng)`
    - `find_best_spots(foodtruck)`
  - `menu.services.pricing_ai_service.PricingAIService`
    - `suggest_price(item)`
  - `analytics.services.event_ai_service.EventAIService`
    - `evaluate_event(foodtruck, event)`
  - `analytics.services.revenue_prediction_service.RevenuePredictionService`
    - `predict_day(foodtruck, date)`

  ### Guarantees

  - Deterministic baseline always computed first
  - AI adjustment is optional, bounded, and non-blocking
  - Errors in AI never break business flow (safe fallback)
  - Explainability returned via `reason` and `breakdown`
  - Results persisted and cache-backed
  - No automatic override of owner choices (suggestions only)

  ### Owner dashboard exposure

  - New owner BI endpoint: `/foodtrucks/<slug>/dashboard/bi/`
  - Returns:
    - best location spots
    - top item pricing suggestions
    - upcoming event opportunities
    - next-day revenue prediction

  ### Tests

  - New file: `analytics/tests/test_ai_services.py`
    - `test_location_score_computation`
    - `test_pricing_suggestion_valid`
    - `test_event_opportunity_scoring`
    - `test_revenue_prediction_fallback`
  - Owner endpoint coverage added in `foodtrucks/tests/test_dashboard_views.py`

### Event database population (production)

- Django admin now exposes `analytics.Event` for manual creation and edits.
- Automatic sync command: `python manage.py sync_events`
  - `--mode fetch --source-url https://...` to ingest events from a JSON feed
  - `--mode seed` to generate synthetic events around active food trucks (fallback)
  - `--dry-run` to validate without DB writes

Expected JSON format for `--mode fetch`:

```json
[
  {
    "name": "City Festival",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "start_date": "2026-05-10",
    "end_date": "2026-05-10",
    "expected_attendance": 7000
  }
]
```

Production scheduler example (cron, every 2 hours):

```bash
0 */2 * * * ANALYTICS_EVENTS_SOURCE_URL="https://example.com/events.json" /opt/foodtruck/scripts/sync_events_cron.sh >> /var/log/foodtruck-sync-events.log 2>&1
```

---

## 1️⃣4️⃣ AI Event Evaluation System

A dedicated system that analyses whether an upcoming event represents a strong business opportunity for food trucks, using a combination of deterministic feature extraction and AI-powered signal extraction.

### Design principles

- The AI **never produces the final score** — it only extracts calibrated signals.
- The final score is **100 % deterministic**: same inputs always yield the same result.
- Every factor is named, weighted, and stored for full explainability.
- All analyses are **persisted** and are **replayable** (prompt versioning ensures comparability).
- Business logic lives exclusively in service modules — zero logic in views or tasks.

### Architecture

```
OpenAI API (structured JSON output, temperature=0)
    ↓
EventAIAnalysisService    — validates & normalises AI response
    ↓ NormalizedAISignals (frozen dataclass)
EventScoringService       — combines AI signals + deterministic features
    ↓ ScoringResult (final_score 0-100 + full breakdown)
analyze_event_task        — Celery task, idempotent, retry-safe
```

### New model: `analytics.EventAIAnalysis`

Stored for every analysed event:

| Field | Description |
|---|---|
| `event` | OneToOne FK to `analytics.Event` |
| `provider` | AI provider (`openai`) |
| `model_name` | Model used (e.g. `gpt-4o-mini`) |
| `prompt_version` | Semver tag of the prompt (e.g. `1.0`) |
| `raw_response` | Verbatim JSON returned by the AI |
| `normalized_data` | Validated, typed signals stored as JSON |
| `confidence_score` | AI self-reported confidence (0.0–1.0) |
| `analyzed_at` | Timestamp of analysis |
| `processing_time_ms` | End-to-end latency |
| `token_usage_input` / `token_usage_output` | Token cost tracking |
| `created_at` / `updated_at` | Audit timestamps |

### New services (`analytics/services/`)

| Module | Class / function | Responsibility |
|---|---|---|
| `schemas.py` | `validate_and_normalize()`, `NormalizedAISignals` | Strict JSON schema, enum validation, typed dataclass |
| `prompts.py` | `PromptBuilder` | Versioned, deterministic prompt construction |
| `feature_extraction.py` | `EventFeatureExtractor` | Pure feature computation: weekend, meal overlaps, duration, summer, timezone-safe |
| `ai_analysis.py` | `EventAIAnalysisService` | OpenAI call (structured output), validation, DB persistence, idempotency |
| `scoring.py` | `EventScoringService` | Weighted scoring (7 factors), full `ScoreBreakdown`, score range 0–100 |

### AI signals extracted (10 fields)

`attendance_estimation` · `foodtruck_compatibility` · `audience_type` · `family_friendly` · `outdoor_event` · `weather_dependency` · `estimated_visit_duration` · `peak_meal_relevance` · `confidence` · `reasoning`

All enum-constrained; validated before any DB write.

### Scoring factors

| Factor | Weight | Source |
|---|---|---|
| Attendance estimation | 25 % | AI signal |
| Food truck compatibility | 25 % | AI signal |
| Meal time overlap | 15 % | Deterministic |
| Weekend | 10 % | Deterministic |
| Duration | 10 % | Deterministic |
| Outdoor event | 8 % | AI signal |
| Summer period | 7 % | Deterministic |

### Celery task (`analytics/tasks/analyze_event.py`)

```python
analyze_event_task.delay(event_id)            # standard enqueue
analyze_event_task.delay(event_id, force=True) # force re-analysis
```

- Idempotent: skips events already analysed at the current prompt version.
- Retry-safe: up to 3 retries with exponential back-off on transient errors.
- `acks_late=True`: message requeued if the worker crashes mid-execution.

### Prompt versioning

- Current version: `1.0` (`analytics/services/prompts.py::CURRENT_PROMPT_VERSION`)
- Bump the constant whenever the prompt wording changes materially.
- Old `EventAIAnalysis` records are preserved; `force=True` creates a fresh analysis.

### Tests (43 tests, all passing)

| File | Coverage |
|---|---|
| `analytics/tests/test_ai_analysis.py` | Schema validation, enum ranges, boundary values, immutability |
| `analytics/tests/test_scoring.py` | Determinism, factor isolation, breakdown integrity, JSON serialisability |
| `analytics/tests/test_feature_extraction.py` | Weekend detection, summer months, meal overlaps, multi-day, timezone safety |

Run with:
```bash
DJANGO_SETTINGS_MODULE=config.settings python -m pytest analytics/tests/test_ai_analysis.py analytics/tests/test_scoring.py analytics/tests/test_feature_extraction.py -v
```

### Environment variables required

```
OPENAI_API_KEY=sk-...
CELERY_BROKER_URL=redis://localhost:6379/0   # default
CELERY_RESULT_BACKEND=redis://localhost:6379/0  # default
```

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
- AI Event Evaluation System

