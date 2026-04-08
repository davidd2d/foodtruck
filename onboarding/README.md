## AI Onboarding Frontend

### Overview
A production-ready AI-powered onboarding frontend that allows users to create a FoodTruck in under 2 minutes. The system processes user-provided text and images through AI to generate complete foodtruck profiles with menus and branding.

## File Storage System

### Overview
The onboarding system uses a robust, production-ready media storage system to handle uploaded images securely and efficiently.

### Folder Structure
```
media/
└── onboarding/
    └── user_<user_id>/
        └── import_<import_id>/
            └── raw/
                ├── menu1.jpg
                ├── menu2.png
                └── ...
```

### Upload Strategy
- **Dynamic Paths**: Files are stored using `onboarding/user_{user_id}/import_{import_id}/raw/{filename}`
- **Instance-Based**: Upload path is generated after import instance creation (to get database ID)
- **User Isolation**: Each user's files are stored in separate directories
- **Import Grouping**: All images for one import are grouped together

### Why Not Using foodtruck_id
- **Early Stage**: Foodtruck doesn't exist yet during onboarding
- **Flexibility**: Allows imports to be processed before foodtruck creation
- **Data Integrity**: Prevents orphaned files if foodtruck creation fails
- **Future S3 Compatibility**: Easy migration to cloud storage with same structure

### Database Models
- **OnboardingImport**: Main import record (no direct file references)
- **OnboardingImage**: Individual image files with foreign key to import
- **Many-to-Many**: Import can have multiple images, images linked to one import

### Processing Flow
1. **Save Import**: Create OnboardingImport instance first (gets ID)
2. **Save Images**: Create OnboardingImage instances with proper upload paths
3. **AI Processing**: Use stored file paths for OpenAI Vision API
4. **Base64 Encoding**: Convert images to base64 for API transmission
5. **Cleanup**: Remove files if import fails or is deleted

### Security & Performance
- **File Validation**: Images only, size limits enforced
- **Path Sanitization**: Safe filename handling
- **Storage Backend**: Django's default storage (easily configurable for S3)
- **Cleanup Strategy**: Automatic file deletion on import failure

### Future S3 Compatibility
```python
# settings.py for S3
AWS_STORAGE_BUCKET_NAME = 'my-bucket'
AWS_S3_REGION_NAME = 'us-east-1'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

The same folder structure works seamlessly with S3, maintaining all existing functionality.

### UX Flow
1. **Import Page** (`/onboarding/import/`): User pastes content and uploads images
2. **AI Processing**: Backend processes data and extracts structured information
3. **Preview Page** (`/onboarding/preview/{id}/`): User reviews and edits AI-generated content
4. **Creation**: Final foodtruck creation with complete menu structure

### Pages Created

#### `/onboarding/import/`
- **Template**: `templates/onboarding/import.html`
- **Features**:
  - Text input for content (required)
  - Multiple image upload (optional)
  - Source URL field (optional)
  - Real-time image preview with removal
  - Form validation
  - Loading states during AI processing

#### `/onboarding/preview/{import_id}/`
- **Template**: `templates/onboarding/preview.html`
- **Features**:
  - Editable foodtruck details (name, description, cuisine)
  - Dynamic preference tags with add/remove
  - Complete menu editor with categories and items
  - Color picker for branding
  - Add/remove menu categories and items
  - Real-time editing with contenteditable fields

### File Structure

```
templates/onboarding/
├── import.html                 # Main import form
├── preview.html               # Preview and editing interface
└── partials/
    ├── _form.html            # Reusable form components
    ├── _preview_foodtruck.html # Foodtruck details partial
    ├── _preview_menu.html    # Menu editing partial
    └── _preview_branding.html # Branding partial

static/onboarding/js/
├── api.js                    # API communication module
├── onboarding.js             # Import page logic
└── preview.js                # Preview page logic
```

### JavaScript Architecture

#### `api.js`
- `createImport(formData)`: Creates new onboarding import
- `pollImportStatus(importId)`: Polls processing status
- `getImportPreview(importId)`: Gets structured preview data
- `createFromImport(importId)`: Creates final foodtruck

#### `onboarding.js`
- Form validation and submission
- Image preview handling
- Loading state management
- Error handling and user feedback

#### `preview.js`
- Dynamic content rendering
- Inline editing functionality
- Menu/category management
- Color picker integration
- Final creation workflow

### API Integration

**POST** `/api/onboarding/imports/`
```json
{
  "raw_text": "User pasted content...",
  "images": ["file1.jpg", "file2.jpg"],
  "source_url": "https://instagram.com/example"
}
```

**GET** `/api/onboarding/imports/{id}/preview/`
```json
{
  "foodtruck": {...},
  "menu": [...],
  "branding": {...},
  "can_create": true
}
```

**POST** `/api/onboarding/imports/{id}/create/`
```json
{
  "status": "success",
  "foodtruck_id": 123,
  "message": "Successfully created FoodTruck \"Example\" with menu"
}
```

### Key Features

- **Ultra-fast onboarding**: < 2 minutes from start to finish
- **AI-powered generation**: Complete foodtruck profiles from text/images
- **Full editing capability**: Every field is editable before creation
- **Robust error handling**: Graceful fallbacks for API failures
- **Mobile-first design**: Responsive Bootstrap interface
- **Real-time feedback**: Loading states and progress indicators
- **Modular architecture**: React-migration ready JavaScript

### Security Features

- CSRF protection on all forms
- User isolation (only access own imports)
- File type validation (images only)
- Input sanitization
- Rate limiting ready

## Serializer Fix

### Issue: ManyRelatedManager Not Iterable

**Problem**: Django REST Framework was attempting to iterate over a `ManyRelatedManager` object directly, causing `TypeError: 'ManyRelatedManager' object is not iterable`.

**Root Cause**: Incorrect serialization of ManyToMany relationships. DRF's ModelSerializer automatically creates fields for model relationships, but ManyToMany fields require special handling.

### Solution: Proper DRF Nested Serialization

**Correct Pattern**:
```python
class OnboardingImportSerializer(serializers.ModelSerializer):
    images = OnboardingImageSerializer(many=True, read_only=True, source="image_files")

    class Meta:
        model = OnboardingImport
        fields = ['id', 'raw_text', 'images', 'source_url', 'status', 'parsed_data', 'created_at']
```

**Key Elements**:
- `many=True`: Required for serializing multiple related objects
- `read_only=True`: Prevents write operations on nested serializer
- `source="image_files"`: Uses the reverse relation from OnboardingImage's `related_name`

### Why This Works

- **DRF Handles Iteration**: DRF automatically calls `.all()` on the relationship and iterates properly
- **No Manual Iteration**: Avoids `for img in instance.images:` which passes ManyRelatedManager directly
- **Performance**: Uses `prefetch_related("image_files")` in ViewSet for efficient queries
- **Type Safety**: DRF ensures proper queryset handling

### Testing

Added comprehensive tests in `test_serializers.py`:
- Image serialization correctness
- Empty images handling
- No crashes with ManyRelatedManager access

### Performance

ViewSet includes `prefetch_related("image_files")` to prevent N+1 queries when serializing related images.

### Known Limitations

- Image processing currently synchronous (can be slow for large images)
- No drag-and-drop for file uploads (can be added)
- Limited branding options (colors only)
- No menu item options/choices editing
- No undo/redo functionality

### Next Steps (React Migration Ready)

1. **Component Extraction**: Convert partials to React components
2. **State Management**: Implement Redux/Zustand for complex state
3. **File Upload**: Add drag-and-drop with progress indicators
4. **Real-time Collaboration**: Multiple users editing simultaneously
5. **Advanced Branding**: Logo upload, style templates
6. **Menu Options**: Add item customization options
7. **Undo/Redo**: Full editing history
8. **Offline Support**: Service worker for offline editing

### Performance Optimizations

- Image lazy loading
- Debounced API calls during editing
- Optimistic UI updates
- Caching of preview data
- Progressive enhancement

### Testing Strategy

- Unit tests for API functions
- Integration tests for full workflows
- E2E tests with Cypress/Playwright
- Performance testing for AI processing
- Accessibility testing (WCAG compliance)

## Logo-based Branding

- **Logo over Text**: Text extraction proved unreliable for color detection; uploading a logo lets the AI focus on the most reliable brand signal.
- **Dedicated Upload & Tagging**: The import form now exposes a separate logo field and marks those uploads with `image_type="logo"` so the backend processes them differently from menu photos.
- **Specialized Prompt**: Logo images trigger a new OpenAI prompt that explicitly asks for one or two dominant colors in HEX format only.
- **Priority Pipeline**: Colors flow through the pipeline in this order: logo colors (highest priority), menu image colors, then text-based guesses as a last resort.
- **Normalization**: `AIOnboardingService.normalize_colors` enforces valid HEX strings, maps friendly names to HEX, and defaults to safe swatches, guaranteeing CSS-ready output.

## Price Validation System

- **Problem**: OCR often returns values like `8,90€` or `890`, which previously became `890€` or `150€`.
- **Parsing Rules**: `_parse_price_value` now understands commas as decimal separators, strips currency symbols, and keeps the data as precise `Decimal` values.
- **Guardrails**: `validate_price` enforces business rules—menu items stay below €100, suspicious values (>€50) are logged, and values ≥100 that look like missing decimals (890, 120 etc.) are auto-corrected by dividing by 100.
- **Correction Flag**: Corrected entries include `"corrected": true` so downstream workflows or UI components can highlight them for review.
- **Tests**: Regression coverage ensures comma parsing, missing-decimal correction, and logo-priority color selection keep working after future changes.

## AI Image Analysis Fix

The image analysis pipeline has been improved to correctly extract menu items, prices, categories, and branding colors from uploaded menu images.

What was fixed:
- Added a dedicated `analyze_images(images)` method in `onboarding/services/ai_onboarding.py`
- Rebuilt the image prompt to require strict JSON only, no hallucinations, and use `null` for missing prices
- Ensured currency detection for €,$,£ and grouped items by visible category
- Added fallback behavior when image analysis fails, preserving text-only results instead of crashing
- Added merging logic so image data wins for prices and menu items while text still provides descriptions and cuisine type
- Added normalization for messy price formats and default categories
- Added tests covering image analysis, merge logic, normalization, full pipeline flow, and edge cases

This fix ensures image-only imports can still produce usable FoodTruck menu data with correct pricing and better branding extraction.

---

## AI Onboarding System - Example API Flow

This document demonstrates how to use the AI-powered onboarding system to create a FoodTruck from user-provided data.

## Overview

The system processes raw text and images to extract structured data about food trucks, menus, and branding, then creates the corresponding database entities.

## API Endpoints

### 1. Create Onboarding Import

**POST** `/api/onboarding/imports/`

Creates a new import and automatically processes it with AI.

**Request Body:**
```json
{
  "raw_text": "Welcome to Joe's Pizza Truck! We serve authentic New York style pizza with fresh ingredients. Our menu includes: Margherita $12, Pepperoni $14, Veggie $13. Located downtown.",
  "images": ["/path/to/menu_image.jpg"],
  "source_url": "https://instagram.com/joespizzatruck"
}
```

**Response:**
```json
{
  "id": 1,
  "raw_text": "Welcome to Joe's Pizza Truck!...",
  "images": ["/path/to/menu_image.jpg"],
  "source_url": "https://instagram.com/joespizzatruck",
  "status": "completed",
  "parsed_data": {
    "foodtruck": {
      "name": "Joe's Pizza Truck",
      "description": "Authentic New York style pizza with fresh ingredients",
      "cuisine_type": "Italian",
      "possible_location": "downtown",
      "preferences": ["Vegetarian Options"]
    },
    "menu": [
      {
        "category": "Pizza",
        "items": [
          {
            "name": "Margherita",
            "description": "Classic margherita pizza",
            "price": 12.0,
            "options": []
          },
          {
            "name": "Pepperoni",
            "description": "Pepperoni pizza",
            "price": 14.0,
            "options": []
          }
        ]
      }
    ],
    "branding": {
      "primary_color": "#FF0000",
      "secondary_color": "#FFFFFF",
      "style": "classic"
    }
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 2. Get Import Preview

**GET** `/api/onboarding/imports/{id}/preview/`

Returns structured preview of parsed data before creating entities.

**Response:**
```json
{
  "foodtruck": {
    "name": "Joe's Pizza Truck",
    "description": "Authentic New York style pizza",
    "cuisine_type": "Italian",
    "possible_location": "downtown",
    "preferences": ["Vegetarian Options"]
  },
  "menu": [...],
  "branding": {...},
  "can_create": true
}
```

### 3. Create FoodTruck from Import

**POST** `/api/onboarding/imports/{id}/create/`

Creates actual database entities from the processed import data identified by `{id}`.

**Response:**
```json
{
  "status": "success",
  "foodtruck_id": 123,
  "message": "Successfully created FoodTruck \"Joe's Pizza Truck\" with menu"
}
```

## OpenAI Prompts

### Text Extraction Prompt

```
You are an AI assistant helping users set up their food truck business. Extract structured information from the provided text.

IMPORTANT RULES:
- Return ONLY valid JSON
- Do NOT hallucinate or add information not in the text
- If data is missing, use empty strings or empty arrays
- Be conservative - only extract what's clearly present

Input text: [user text]

Return JSON in this exact format: [expected structure]
```

### Image Analysis Prompt

```
Analyze this food truck related image and extract relevant information.

Return JSON in the same format as text extraction, focusing on:
- Menu items visible in the image
- Any branding elements (colors, style)
- Food truck name if visible

If no relevant information is found, return empty structure.
```

## Data Flow

1. **User Input** → OnboardingImport model
2. **AI Processing** → Clean text + OpenAI calls → Structured JSON
3. **Data Normalization** → Map preferences, clean prices

## Branding Colors Fix

- **Problem**: The AI previously returned descriptive color names (e.g. "dark red") which cannot be used directly in CSS.
- **Prompt Update**: The prompts now ask for both a `name` and `hex` value for `primary_color`/`secondary_color`, ensuring the AI provides structured color data.
- **Normalization**: `AIOnboardingService.normalize_colors` validates HEX values (regex check), maps known names like `red` → `#FF0000`, and nullifies invalid values so the frontend always receives safe, consistent data.
- **Front-End Ready**: The normalized `branding` block now looks like `{ "primary_color": "#8B0000", "secondary_color": "#F5F5DC", "style": "vintage" }`, making it ready for CSS and Bootstrap helpers.

## API Fix

- **Endpoint Change**: Replaced the old `/api/onboarding/create_from_import/` with the RESTful `/api/onboarding/imports/{id}/create/` (detail action on the `OnboardingImportViewSet`).
- **Clean Flow**: The new action guarantees the import is `completed` before creation, delegates the workflow to `AIOnboardingService.create_foodtruck_from_import`, and returns HTTP 201 with the created `foodtruck_id`.
- **Front-End Alignment**: Client calls now hit `imports/{id}/create/`, so there is no need to send the import ID in the request body; the URL encodes the resource being operated on.
4. **Entity Creation** → FoodTruck + Menu + Categories + Items
5. **Branding Application** → Apply colors/styles (future feature)

## Error Handling

- Invalid JSON from OpenAI → Fallback to empty structure
- Empty responses from OpenAI → Graceful degradation
- Markdown-wrapped JSON responses → Automatic cleaning
- Missing preferences → Skip gracefully
- Database errors → Transaction rollback
- Network timeouts → Retry logic (future)

## Security

- User isolation: Only access own imports
- Input validation: Sanitize text and URLs
- Rate limiting: Prevent abuse (future)
- No external scraping: Only user-provided data
