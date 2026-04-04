# Frontend Architecture - FoodTruck SaaS

## Overview

This document describes the frontend foundation for the FoodTruck SaaS platform. The architecture is designed to be production-ready and compatible with a future migration to React + Tailwind + DRF API.

## Architecture Principles

- **No business logic in views**: Django views only render templates
- **Modular JavaScript**: ES6 modules with clear separation of concerns
- **Component-based**: Reusable UI components
- **API-first**: All data fetching through REST API
- **Future-proof**: Easy migration path to React

## File Structure

```
static/
├── js/
│   ├── api/
│   │   ├── client.js          # Centralized API client
│   │   └── foodtruck.js       # Foodtruck-specific API calls
│   ├── components/
│   │   └── foodtruckCard.js   # UI components
│   └── pages/
│       └── foodtruckList.js   # Page-specific logic
└── images/
    └── foodtruck-placeholder.jpg  # Placeholder images

templates/
├── base.html                  # Base template with Bootstrap
└── foodtrucks/
    └── list.html              # Foodtruck list page
```

## Components

### 1. Base Template (`templates/base.html`)

- Bootstrap 5 via CDN
- Responsive navbar with logo, navigation, cart placeholder
- CSRF token setup for AJAX
- Block structure for content and extra JS

### 2. API Client (`static/js/api/client.js`)

Centralized HTTP client with:
- JSON parsing and error handling
- CSRF token management
- Methods: `get()`, `post()`, `put()`, `patch()`, `delete()`

### 3. Foodtruck API (`static/js/api/foodtruck.js`)

Domain-specific API calls:
- `fetchFoodtrucks(params)` - Get all foodtrucks
- `fetchFoodtruck(id)` - Get single foodtruck
- `searchFoodtrucks(query)` - Search functionality

### 4. UI Components (`static/js/components/foodtruckCard.js`)

Reusable components:
- `createFoodtruckCard(foodtruck)` - Render foodtruck card
- `createEmptyState()` - No results state
- `createLoadingState()` - Loading spinner
- `createErrorState()` - Error display

### 5. Page Logic (`static/js/pages/foodtruckList.js`)

Page controllers that:
- Initialize on DOM load
- Fetch data via API
- Render components
- Handle user interactions

## Usage

### Adding a New Page

1. Create template in `templates/app_name/page.html`
2. Create page JS in `static/js/pages/pageName.js`
3. Create thin Django view
4. Add URL routing

### Adding a New Component

1. Create component in `static/js/components/componentName.js`
2. Export rendering functions
3. Import and use in page logic

### Adding API Calls

1. Add methods to appropriate API module in `static/js/api/`
2. Import and use in page logic or other components

## URLs

- `/foodtrucks/` - Foodtruck list page (renders template, JS loads data)
- `/api/foodtrucks/` - Foodtruck API endpoint

## Future Migration Path

The architecture is designed for easy migration to React:

1. Replace Django templates with React components
2. Move API calls to React hooks
3. Replace Django views with DRF API-only
4. Update routing to React Router
5. Migrate styling to Tailwind

## Development

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server
python manage.py runserver

# Access foodtruck list
# http://localhost:8000/foodtrucks/
```

### Testing

```bash
# Run all tests
python -m pytest

# Run foodtrucks tests
python -m pytest foodtrucks/tests
```

## Security

- CSRF tokens handled automatically for AJAX requests
- API authentication via JWT (configured in settings)
- Input validation on both frontend and backend

## Performance

- ES6 modules for better bundling
- Efficient API calls with proper error handling
- Lazy loading ready for future implementation
- CDN resources for Bootstrap