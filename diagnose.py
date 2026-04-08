#!/usr/bin/env python
"""Complete diagnostic for menu display issue"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from foodtrucks.models import FoodTruck
from menu.models import Menu, Category, Item
from django.db.models import Count, Prefetch

def diagnose(): 
    print("=" * 60)
    print("FOODTRUCK MENU DIAGNOSTIC REPORT")
    print("=" * 60)
    
    # Step 1: Check specific truck
    truck = FoodTruck.objects.filter(slug='cucina-di-pastaz').first()
    print(f"\n1. SPECIFIC FOODTRUCK 'cucina-di-pastaz':")
    print(f"   Exists: {truck is not None}")
    
    if truck:
        print(f"   ID: {truck.id}")
        print(f"   Name: {truck.name}")
        print(f"   Active: {truck.is_active}")
        
        # Step 2: Check ALL menus for this truck
        all_menus = Menu.objects.filter(food_truck=truck)
        print(f"\n2. ALL MENUS FOR THIS TRUCK: {all_menus.count()}")
        for menu in all_menus:
            print(f"   - Menu ID {menu.id}:")
            print(f"     Name: {menu.name}")
            print(f"     Active: {menu.is_active}")
            print(f"     Created: {menu.created_at}")
            categories = menu.categories.all()
            print(f"     Categories: {categories.count()}")
            total_items = Item.objects.filter(category__menu=menu).count()
            print(f"     Total Items: {total_items}")
            
        # Step 3: Check active menu specifically
        active_menu = Menu.objects.filter(food_truck=truck, is_active=True).first()
        print(f"\n3. ACTIVE MENU:")
        print(f"   Exists: {active_menu is not None}")
        
        if active_menu:
            print(f"   ID: {active_menu.id}")
            categories = active_menu.categories.all()
            print(f"   Category count: {categories.count()}")
            
            for cat in categories:
                items = cat.items.all()
                print(f"     - {cat.name}: {items.count()} items")
                for item in items[:3]:
                    print(f"       • {item.name} (€{item.base_price})")
        else:
            print("   ⚠️  NO ACTIVE MENU - This is the problem!")
            
    else:
        print("   ⚠️  TRUCK NOT FOUND - Check slug spelling")
        
    # Step 4: Show all foodtrucks
    print(f"\n4. ALL FOODTRUCKS IN DATABASE:")
    all_trucks = FoodTruck.objects.all()
    print(f"   Total: {all_trucks.count()}")
    for t in all_trucks[:10]:
        menu_status = Menu.objects.filter(food_truck=t, is_active=True).exists()
        print(f"   - {t.slug} ({t.name}): {'✓ has menu' if menu_status else '✗ NO menu'}")

if __name__ == '__main__':
    diagnose()
