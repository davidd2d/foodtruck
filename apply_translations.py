#!/usr/bin/env python3
"""Apply translations to .po files"""

import os
import sys

# French translations
translations_fr = {
    "Plan": "Plan",
    "Display name of the plan": "Nom d'affichage du plan",
    "Food Truck": "Camion à hot-dogs", 
    "Name of the food truck": "Nom du camion à hot-dogs",
    "Detailed description of the food truck": "Description détaillée du camion",
    "Menu": "Menu",
    "Category": "Catégorie",
    "Item": "Article",
    "Item name in the current language": "Nom de l'article dans la langue actuelle",
    "Item description": "Description de l'article",
    "Option": "Option",
    "Option Group": "Groupe d'options",
    "Order": "Commande",
    "Order Item": "Article de commande",
    "Pickup Slot": "Créneau de retrait",
    "Payment": "Paiement",
    "Preference": "Préférence",
    "Dietary preference or restriction": "Préférence ou restriction alimentaire",
    "Slot start time": "Heure de début du créneau",
    "Slot end time": "Heure de fin du créneau",
    "Max orders": "Commandes max",
}

# Spanish translations
translations_es = {
    "Plan": "Plan",
    "Display name of the plan": "Nombre mostrado del plan",
    "Food Truck": "Camión de Comida",
    "Name of the food truck": "Nombre del camión de comida",
    "Detailed description of the food truck": "Descripción detallada del camión",
    "Menu": "Menú",
    "Category": "Categoría",
    "Item": "Artículo",
    "Item name in the current language": "Nombre del artículo en idioma actual",
    "Item description": "Descripción del artículo",
    "Option": "Opción",
    "Option Group": "Grupo de Opciones",
    "Order": "Pedido",
    "Order Item": "Artículo del Pedido",
    "Pickup Slot": "Espacio de Recogida",
    "Payment": "Pago",
    "Preference": "Preferencia",
    "Dietary preference or restriction": "Preferencia o restricción dietética",
    "Slot start time": "Hora de inicio del espacio",
    "Slot end time": "Hora de finalización del espacio",
    "Max orders": "Pedidos máximos",
}

def apply_translations(po_file, translations):
    """Apply translations to a .po file"""
    with open(po_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    replaced = 0
    
    while i < len(lines):
        # Look for msgid
        if lines[i].startswith('msgid "') and not lines[i].startswith('msgid ""'):
            msgid_line = lines[i]
            # Extract the text between quotes
            msgid_text = msgid_line[7:-2]  # Remove 'msgid "' and '"\n'
            
            # Check if we have a translation for this
            if msgid_text in translations:
                # Next line should be msgstr
                if i + 1 < len(lines) and lines[i+1].startswith('msgstr "'):
                    old_msgstr = lines[i+1]
                    # Only replace if msgstr is empty
                    if old_msgstr.strip() == 'msgstr ""':
                        translation = translations[msgid_text]
                        lines[i+1] = f'msgstr "{translation}"\n'
                        replaced += 1
        i += 1
    
    with open(po_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    return replaced

# Apply to French file
fr_file = '/Users/david/Documents/foodtruck/locale/fr/LC_MESSAGES/django.po'
fr_count = apply_translations(fr_file, translations_fr)
print(f"✓ French: {fr_count} translations applied")

# Apply to Spanish file
es_file = '/Users/david/Documents/foodtruck/locale/es/LC_MESSAGES/django.po'
es_count = apply_translations(es_file, translations_es)
print(f"✓ Spanish: {es_count} translations applied")

print(f"\nTotal: {fr_count + es_count} translations applied")
