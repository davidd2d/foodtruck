#!/usr/bin/env python
"""List all foodtrucks in the database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from foodtrucks.models import FoodTruck
from menu.models import Menu

trucks = FoodTruck.objects.all()
print(f"Total foodtrucks: {trucks.count()}\n")

for truck in trucks:
    menu_exists = Menu.objects.filter(food_truck=truck, is_active=True).exists()
    print(f"Slug: '{truck.slug}'")
    print(f"  Name: {truck.name}")
    print(f"  Active: {truck.is_active}")
    print(f"  Has active menu: {menu_exists}")
    print()
