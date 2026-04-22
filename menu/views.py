from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from ai_menu.views import _get_menu_categories
from common.models import Tax
from foodtrucks.models import FoodTruck
from menu.forms import ComboCatalogForm, ItemCatalogForm, MenuImportForm, OptionCatalogForm
from menu.models import Combo, Item, Option
from menu.services.menu_import_service import MenuImportService
from menu.services.menu_service import MenuService


def _get_owner_foodtruck(user, slug):
	return get_object_or_404(
		FoodTruck.objects.prefetch_related('supported_preferences'),
		slug=slug,
		owner=user,
		is_active=True,
	)


def _load_active_menu(foodtruck):
	try:
		return MenuService.get_active_menu_for_foodtruck(foodtruck.slug)
	except Http404:
		return None


def _get_tax_display(explicit_tax=None, country=None):
	if explicit_tax is not None:
		return str(explicit_tax)

	default_tax = Tax.objects.default(country=country)
	if default_tax is not None:
		return f'{default_tax.name} ({default_tax.rate * 100:.2f}%)'

	return 'Taxe par defaut'


def _build_catalog_sections(menu):
	if menu is None:
		return []

	sections = []
	foodtruck = getattr(menu, 'food_truck', None)
	country = None
	if foodtruck is not None:
		country = getattr(foodtruck, 'country', None) or getattr(foodtruck, 'billing_country', None)

	categories = menu.categories.prefetch_related('items__option_groups__options', 'combos').order_by('display_order', 'name')
	for category in categories:
		item_entries = []
		for item in category.items.all().order_by('display_order', 'name'):
			item_tax_label = _get_tax_display(item.tax, country=country)
			option_groups = []
			for option_group in item.option_groups.all():
				option_entries = []
				for option in option_group.options.all().order_by('name'):
					option_entries.append({
						'option': option,
						'form': OptionCatalogForm(instance=option, prefix=f'option-{option.id}', foodtruck=foodtruck),
						'assigned_item_name': item.name,
						'inherited_tax_label': item_tax_label,
					})
				option_groups.append({
					'group': option_group,
					'options': option_entries,
				})
			item_entries.append({
				'item': item,
				'form': ItemCatalogForm(instance=item, prefix=f'item-{item.id}', foodtruck=foodtruck),
				'option_groups': option_groups,
				'tax_label': item_tax_label,
			})

		combo_entries = []
		for combo in category.combos.all().order_by('display_order', 'name'):
			combo_entries.append({
				'combo': combo,
				'form': ComboCatalogForm(instance=combo, prefix=f'combo-{combo.id}', foodtruck=foodtruck),
				'tax_label': _get_tax_display(combo.tax, country=country),
			})

		sections.append({
			'category': category,
			'items': item_entries,
			'combos': combo_entries,
		})
	return sections


def _wants_json_response(request):
	accept = request.headers.get('Accept', '')
	requested_with = request.headers.get('X-Requested-With', '')
	return 'application/json' in accept or requested_with == 'XMLHttpRequest'


def _serialize_form_errors(form):
	return {
		field: [str(error) for error in errors]
		for field, errors in form.errors.items()
	}


@login_required
def owner_menu_dashboard(request, slug):
	foodtruck = _get_owner_foodtruck(request.user, slug)
	active_menu = _load_active_menu(foodtruck)
	categories = _get_menu_categories(foodtruck)

	items_count = 0
	combos_count = 0
	if active_menu is not None:
		items_count = Item.objects.filter(category__menu=active_menu).count()
		combos_count = Combo.objects.filter(category__menu=active_menu).count()

	return render(request, 'menu/dashboard.html', {
		'foodtruck': foodtruck,
		'categories': categories,
		'active_menu': active_menu,
		'items_count': items_count,
		'combos_count': combos_count,
	})


@login_required
def owner_menu_import(request, slug):
	foodtruck = _get_owner_foodtruck(request.user, slug)
	categories = _get_menu_categories(foodtruck)
	form = MenuImportForm(request.POST or None)

	if request.method == 'POST':
		images = request.FILES.getlist('images')
		documents = request.FILES.getlist('documents')
		if form.is_valid():
			if not form.cleaned_data['raw_text'].strip() and not images and not documents:
				form.add_error(None, _('Add text, photos, or at least one PDF to import a menu.'))
			else:
				service = MenuImportService()
				try:
					import_instance, menu = service.import_for_foodtruck(
						foodtruck=foodtruck,
						user=request.user,
						raw_text=form.cleaned_data['raw_text'],
						images=images,
						pdf_files=documents,
						source_url=form.cleaned_data.get('source_url', ''),
					)
				except ValidationError as exc:
					form.add_error(None, exc.message if hasattr(exc, 'message') else str(exc))
				else:
					imported_categories = menu.categories.count()
					imported_items = Item.objects.filter(category__menu=menu).count()
					messages.success(
						request,
						_('Menu imported successfully: %(categories)s categories and %(items)s items are now live.') % {
							'categories': imported_categories,
							'items': imported_items,
						}
					)
					return redirect('menu:catalog', slug=foodtruck.slug)

	return render(request, 'menu/import.html', {
		'foodtruck': foodtruck,
		'categories': categories,
		'form': form,
	})


@login_required
def owner_menu_catalog(request, slug):
	foodtruck = _get_owner_foodtruck(request.user, slug)
	active_menu = _load_active_menu(foodtruck)
	categories = _get_menu_categories(foodtruck)
	sections = _build_catalog_sections(active_menu)

	return render(request, 'menu/catalog.html', {
		'foodtruck': foodtruck,
		'categories': categories,
		'active_menu': active_menu,
		'sections': sections,
		'prices_include_tax': foodtruck.prices_include_tax(),
	})


@login_required
@require_POST
def owner_item_update(request, slug, item_id):
	foodtruck = _get_owner_foodtruck(request.user, slug)
	item = get_object_or_404(
		Item.objects.select_related('category__menu__food_truck'),
		pk=item_id,
		category__menu__food_truck=foodtruck,
	)
	form = ItemCatalogForm(request.POST, instance=item, prefix=f'item-{item.id}', foodtruck=foodtruck)
	if form.is_valid():
		updated_item = form.save()
		if _wants_json_response(request):
			return JsonResponse({
				'success': True,
				'item_id': updated_item.id,
				'name': updated_item.name,
				'base_price': str(foodtruck.get_display_price(updated_item.base_price, updated_item.get_tax_rate())),
				'is_available': updated_item.is_available,
				'tax_label': str(updated_item.tax) if updated_item.tax else '',
			})
		messages.success(request, _('Updated %(name)s.') % {'name': item.name})
	else:
		if _wants_json_response(request):
			return JsonResponse({
				'success': False,
				'errors': _serialize_form_errors(form),
			}, status=400)
		messages.error(request, '; '.join(error for errors in form.errors.values() for error in errors))
	return redirect('menu:catalog', slug=foodtruck.slug)


@login_required
@require_POST
def owner_combo_update(request, slug, combo_id):
	foodtruck = _get_owner_foodtruck(request.user, slug)
	combo = get_object_or_404(
		Combo.objects.select_related('category__menu__food_truck'),
		pk=combo_id,
		category__menu__food_truck=foodtruck,
	)
	form = ComboCatalogForm(request.POST, instance=combo, prefix=f'combo-{combo.id}', foodtruck=foodtruck)
	if form.is_valid():
		updated_combo = form.save()
		if _wants_json_response(request):
			return JsonResponse({
				'success': True,
				'combo_id': updated_combo.id,
				'name': updated_combo.name,
				'combo_price': (
					str(foodtruck.get_display_price(updated_combo.combo_price, updated_combo.get_tax_rate()))
					if updated_combo.combo_price is not None else ''
				),
				'is_available': updated_combo.is_available,
				'tax_label': str(updated_combo.tax) if updated_combo.tax else '',
			})
		messages.success(request, _('Updated %(name)s.') % {'name': combo.name})
	else:
		if _wants_json_response(request):
			return JsonResponse({
				'success': False,
				'errors': _serialize_form_errors(form),
			}, status=400)
		messages.error(request, '; '.join(error for errors in form.errors.values() for error in errors))
	return redirect('menu:catalog', slug=foodtruck.slug)


@login_required
@require_POST
def owner_option_update(request, slug, option_id):
	foodtruck = _get_owner_foodtruck(request.user, slug)
	option = get_object_or_404(
		Option.objects.select_related('group__item__category__menu__food_truck'),
		pk=option_id,
		group__item__category__menu__food_truck=foodtruck,
	)
	form = OptionCatalogForm(request.POST, instance=option, prefix=f'option-{option.id}', foodtruck=foodtruck)
	if form.is_valid():
		updated_option = form.save()
		if _wants_json_response(request):
			return JsonResponse({
				'success': True,
				'option_id': updated_option.id,
				'name': updated_option.name,
				'price_modifier': str(foodtruck.get_display_price(updated_option.price_modifier, updated_option.get_tax_rate())),
				'is_available': updated_option.is_available,
			})
		messages.success(request, _('Updated %(name)s.') % {'name': option.name})
	else:
		if _wants_json_response(request):
			return JsonResponse({
				'success': False,
				'errors': _serialize_form_errors(form),
			}, status=400)
		messages.error(request, '; '.join(error for errors in form.errors.values() for error in errors))
	return redirect('menu:catalog', slug=foodtruck.slug)
