#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from foodtrucks.models import FoodTruck
from menu.models import Menu, Category, Item
from django.db.models import Count, Prefetch

# Check if cucina-di-pastaz exists
truck = FoodTruck.objects.filter(slug='cucina-di-pastaz').first()
print(f"Foodtruck found: {truck is not None}")

if truck:
    print(f"  Name: {truck.name}")
    print(f"  Slug: {truck.slug}")
    print(f"  Active: {truck.is_active}")
    
    # Check menus
    menus = Menu.objects.filter(food_truck=truck)
    print(f"\nTotal menus for this truck: {menus.count()}")
    
    for menu in menus:
        print(f"\n  Menu {menu.id}:")
        print(f"    Name: {menu.name}")
        print(f"    Active: {menu.is_active}")
        print(f"    Created: {menu.created_at}")
        
        categories = menu.categories.all()
        print(f"    Categories: {categories.count()}")
        
        for cat in categories:
            items = cat.items.all()
            print(f"      - {cat.name}: {items.count()} items")
            if items.count() > 0:
                for item in items[:2]:
                    print(f"        • {item.name} (€{item.price})")

    # Check active menu
    active_menu = Menu.objects.filter(food_truck=truck, is_active=True).first()
    print(f"\nActive menu: {active_menu is not None}")
    if active_menu:
        print(f"  Has categories: {active_menu.categories.count() > 0}")
else:
    # List all trucks
    trucks = FoodTruck.objects.all()
    print(f"\nTotal foodtrucks: {trucks.count()}")
    for truck in trucks[:5]:
        menu_count = Menu.objects.filter(food_truck=truck, is_active=True).count()
        print(f"  - {truck.slug}: {truck.name} (active menus: {menu_count})")
