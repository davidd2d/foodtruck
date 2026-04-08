from foodtrucks.models import FoodTruck
from menu.models import Menu

# Check if cucina-di-pastaz exists
truck = FoodTruck.objects.filter(slug='cucina-di-pastaz').first()
if truck:
    print(f"Found foodtruck: {truck.name}")
    # Check if it has an active menu
    menu = Menu.objects.filter(food_truck=truck, is_active=True).first()
    if menu:
        print(f"Found active menu: {menu.id}")
        categories = menu.categories.all()
        print(f"Number of categories: {categories.count()}")
        for cat in categories:
            items = cat.items.all()
            print(f"  - {cat.name}: {items.count()} items")
    else:
        print("No active menu found for this foodtruck")
else:
    # List all foodtrucks
    trucks = FoodTruck.objects.all()
    print(f"Total foodtrucks: {trucks.count()}")
    for truck in trucks[:10]:
        print(f"  - {truck.slug}: {truck.name}")
