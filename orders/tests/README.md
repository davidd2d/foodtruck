# Orders Test Suite

This folder contains the production-grade test suite for the order subsystem.

## Structure

- `factories.py` — reusable factories for `User`, `FoodTruck`, `Item`, `PickupSlot`, `Order`, etc.
- `test_models.py` — model-level coverage for order business rules and pickup slot behavior
- `test_api.py` — API endpoint coverage for order creation, item addition, submission, and permissions
- `test_services.py` — placeholder for future service-level tests when business logic is extracted

## Key goals

- Keep tests isolated and readable
- Avoid duplicated setup with factories
- Verify all order lifecycle rules in models, concurrency, and API layers
- Use descriptive names like `test_cannot_submit_empty_order`

## Run tests

```bash
python manage.py test orders --verbosity=1 --noinput
```
