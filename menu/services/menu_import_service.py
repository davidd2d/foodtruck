from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from pypdf import PdfReader

from onboarding.models import OnboardingImage, OnboardingImport
from onboarding.services.ai_onboarding import AIOnboardingService
from menu.models import Category, Item, Menu, Option, OptionGroup


class MenuImportService:
    def import_for_foodtruck(self, foodtruck, user, raw_text='', images=None, pdf_files=None, source_url=''):
        images = images or []
        pdf_files = pdf_files or []

        pdf_text = self._extract_pdf_text(pdf_files)
        merged_text = self._merge_text_sources(raw_text, pdf_text)

        import_instance = OnboardingImport.objects.create(
            user=user,
            raw_text=merged_text,
            source_url=source_url or None,
        )
        for image in images:
            OnboardingImage.objects.create(
                import_instance=import_instance,
                image=image,
                image_type='menu',
            )

        AIOnboardingService().process_import(import_instance.id)
        import_instance.refresh_from_db()

        if import_instance.status != 'completed':
            raise ValidationError('The import could not be completed. Please review the source files and try again.')

        menu = self.apply_import_to_foodtruck(foodtruck, import_instance)
        return import_instance, menu

    def apply_import_to_foodtruck(self, foodtruck, import_instance):
        if import_instance.status != 'completed':
            raise ValidationError('Import must be completed before applying a menu.')

        menu_data = import_instance.parsed_data.get('menu') or []
        if not menu_data:
            raise ValidationError('No menu items were extracted from this import.')

        with transaction.atomic():
            foodtruck.menus.filter(is_active=True).update(is_active=False)
            menu = Menu.objects.create(
                food_truck=foodtruck,
                name=foodtruck.get_default_menu_name(),
                is_active=True,
            )

            for category_index, category_data in enumerate(menu_data):
                category = Category.objects.create(
                    menu=menu,
                    name=(category_data.get('category') or 'General').strip() or 'General',
                    display_order=category_index,
                )

                for item_index, item_data in enumerate(category_data.get('items', [])):
                    item = Item.objects.create(
                        category=category,
                        name=(item_data.get('name') or 'Unnamed item').strip() or 'Unnamed item',
                        description=(item_data.get('description') or '').strip(),
                        base_price=self._parse_price(item_data.get('price')),
                        display_order=item_index,
                        is_available=True,
                    )
                    self._create_options(item, item_data.get('options', []))

        return menu

    def _extract_pdf_text(self, pdf_files):
        extracted_chunks = []
        for pdf_file in pdf_files:
            try:
                pdf_file.seek(0)
                reader = PdfReader(pdf_file)
                text = '\n'.join((page.extract_text() or '').strip() for page in reader.pages)
            except Exception as exc:
                raise ValidationError(f'Unable to read PDF "{pdf_file.name}": {exc}')

            normalized = text.strip()
            if normalized:
                extracted_chunks.append(normalized)

        return '\n\n'.join(extracted_chunks)

    def _merge_text_sources(self, raw_text, pdf_text):
        text_blocks = [segment.strip() for segment in [raw_text or '', pdf_text or ''] if segment and segment.strip()]
        return '\n\n'.join(text_blocks)

    def _parse_price(self, value):
        if value in (None, ''):
            return Decimal('0.00')
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal('0.01'))

        cleaned = str(value).replace('€', '').replace('$', '').replace('EUR', '').replace(',', '.').strip()
        try:
            return Decimal(cleaned).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            return Decimal('0.00')

    def _create_options(self, item, raw_options):
        normalized_groups = self._normalize_option_groups(raw_options)
        for group_index, option_group_data in enumerate(normalized_groups):
            option_group, _ = OptionGroup.objects.get_or_create(
                category=item.category,
                name=option_group_data['group'],
                defaults={
                    'required': False,
                    'min_choices': 0,
                    'max_choices': None,
                },
            )
            for option_index, option_data in enumerate(option_group_data['options']):
                option, _ = Option.objects.get_or_create(
                    group=option_group,
                    name=option_data['name'],
                    defaults={
                        'price_modifier': self._parse_price(option_data.get('price')),
                        'is_available': True,
                    },
                )
                option.items.add(item)

    def _normalize_option_groups(self, raw_options):
        if not raw_options:
            return []

        if isinstance(raw_options, dict):
            raw_options = [raw_options]

        normalized = []
        fallback_options = []
        for option in raw_options:
            if isinstance(option, str):
                fallback_options.append({'name': option.strip(), 'price': None})
                continue

            if not isinstance(option, dict):
                continue

            if 'options' in option and isinstance(option['options'], list):
                group_name = (option.get('group') or option.get('name') or 'Options').strip() or 'Options'
                group_options = []
                for nested_option in option['options']:
                    if isinstance(nested_option, str):
                        group_options.append({'name': nested_option.strip(), 'price': None})
                    elif isinstance(nested_option, dict):
                        group_options.append({
                            'name': (nested_option.get('name') or '').strip(),
                            'price': nested_option.get('price'),
                        })
                group_options = [entry for entry in group_options if entry['name']]
                if group_options:
                    normalized.append({'group': group_name, 'options': group_options})
                continue

            option_name = (option.get('name') or '').strip()
            if option_name:
                fallback_options.append({'name': option_name, 'price': option.get('price')})

        if fallback_options:
            normalized.append({'group': 'Options', 'options': fallback_options})

        return normalized