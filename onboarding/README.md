# AI Onboarding System - Example API Flow

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
      "primary_color": "red",
      "secondary_color": "white",
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

**POST** `/api/onboarding/create_from_import/`

Creates actual database entities from processed import data.

**Request Body:**
```json
{
  "import_id": 1
}
```

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
4. **Entity Creation** → FoodTruck + Menu + Categories + Items
5. **Branding Application** → Apply colors/styles (future feature)

## Error Handling

- Invalid JSON from OpenAI → Fallback to empty structure
- Missing preferences → Skip gracefully
- Database errors → Transaction rollback
- Network timeouts → Retry logic (future)

## Security

- User isolation: Only access own imports
- Input validation: Sanitize text and URLs
- Rate limiting: Prevent abuse (future)
- No external scraping: Only user-provided data