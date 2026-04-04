# Internationalization Implementation Checklist

## Quick Reference for Implementing i18n in Your Django Project

Use this checklist to systematically add internationalization support to your codebase.

---

## Phase 1: Foundation (✅ COMPLETE)

- [x] **Django i18n Settings Configured**
  - [x] LANGUAGE_CODE = 'en'
  - [x] LANGUAGES = [('en', 'English'), ('fr', 'French'), ('es', 'Spanish')]
  - [x] USE_I18N = True
  - [x] LOCALE_PATHS configured
  - [x] LocaleMiddleware added to MIDDLEWARE

- [x] **Tools Installed**
  - [x] django-parler 2.3 installed (optional, for future)
  - [x] django-rest-framework 3.15.2
  - [x] drf-spectacular (optional, for API docs)

- [x] **Directory Structure Created**
  - [x] `/locale/` directory created
  - [x] `config/utils/` package created
  - [x] `config/utils/i18n.py` utilities implemented

---

## Phase 2: Mark Strings for Translation (🔄 IN PROGRESS)

### For Each App (foodtrucks, menu, orders, payments, preferences, users):

#### 2.1 Models (e.g., `foodtrucks/models/__init__.py`)

- [ ] **Mark model field labels**
  ```python
  from django.utils.translation import gettext_lazy as _
  
  class FoodTruck(models.Model):
      name = models.CharField(
          max_length=255,
          help_text=_("Name of the food truck")  # Add this
      )
  ```

- [ ] **Mark Meta class strings**
  ```python
  class Meta:
      verbose_name = _("Food Truck")        # Add this
      verbose_name_plural = _("Food Trucks")  # Add this
  ```

#### 2.2 AdminPanel (e.g., `foodtrucks/admin.py`)

- [ ] **Mark list_display labels**
  ```python
  class FoodTruckAdmin(admin.ModelAdmin):
      list_display = (_('Name'), _('Status'), _('Owner'))
  ```

- [ ] **Mark search_fields descriptions**
  ```python
  search_fields = (_('Name'), _('Description'))
  ```

#### 2.3 Serializers (e.g., `foodtrucks/api/serializers.py`)

- [ ] **Mark serializer field help texts**
  ```python
  from django.utils.translation import gettext_lazy as _
  
  class FoodTruckSerializer(serializers.ModelSerializer):
      name = serializers.CharField(
          help_text=_("Name of the food truck")
      )
  ```

- [ ] **Mark validation error messages**
  ```python
  raise serializers.ValidationError(_("This field is required"))
  ```

#### 2.4 Views & Viewsets (e.g., `foodtrucks/views.py`)

- [ ] **Mark response messages**
  ```python
  from django.utils.translation import gettext_lazy as _
  
  return Response({'message': _("Successfully created")})
  ```

#### 2.5 Forms (if using Django forms)

- [ ] **Mark form field labels**
  ```python
  from django import forms
  from django.utils.translation import gettext_lazy as _
  
  class MyForm(forms.Form):
      name = forms.CharField(label=_("Name"))
  ```

---

## Phase 3: Extract Translatable Strings (⏳ TODO)

### Run these commands:

```bash
# Step 1: Extract strings for French
python manage.py makemessages -l fr

# Step 2: Extract strings for Spanish  
python manage.py makemessages -l es

# Both create:
# - locale/fr/LC_MESSAGES/django.po
# - locale/es/LC_MESSAGES/django.po
```

### Verify files were created:
```bash
find locale -name "django.po" | wc -l
# Should output: 2
```

### Check your app for translatable strings:

- [ ] `foodtrucks` app: Mark strings used in models, admin, views
- [ ] `menu` app: Mark Menu, Category, Item, OptionGroup, Option fields
- [ ] `orders` app: Mark order-related strings
- [ ] `payments` app: Mark payment status strings
- [ ] `preferences` app: Mark preference name/description
- [ ] `users` app: Mark user-related strings

---

## Phase 4: Translate Content (⏳ TODO)

### For Each Language (.po file):

#### 4.1 French (locale/fr/LC_MESSAGES/django.po)

- [ ] Open file in text editor
- [ ] Find untranslated entries (msgstr = "")
- [ ] Add French translation

Example:
```
#: foodtrucks/models.py
msgid "Name of the food truck"
msgstr "Nom du camion à hot-dogs"
```

- [ ] Save file

#### 4.2 Spanish (locale/es/LC_MESSAGES/django.po)

- [ ] Open file in text editor
- [ ] Find untranslated entries (msgstr = "")
- [ ] Add Spanish translation

Example:
```
#: foodtrucks/models.py
msgid "Name of the food truck"
msgstr "Nombre del camión de comida"
```

- [ ] Save file

### Useful .po file tips:

- Lines starting with `#:` show where string is used
- Lines with `#, fuzzy` are auto-translated and need review
- `msgid` is the original English string
- `msgstr` is the translation (leave empty for untranslated)
- Use `%s`, `%d` for variable replacements in both msgid and msgstr

---

## Phase 5: Compile Translations (⏳ TODO)

```bash
# Compile .po → .mo (binary format)
python manage.py compilemessages

# Verify compilation:
find locale -name "*.mo" | wc -l
# Should output: 2 (one for each language)

# Check for errors:
python manage.py compilemessages --check
```

---

## Phase 6: Update Serializers (⏳ TODO)

### Add i18n Support to Existing Serializers:

```python
# In foodtrucks/api/serializers.py

from config.utils import LanguageAwareSerializerMixin, LanguageResponseMixin

class FoodTruckSerializer(LanguageAwareSerializerMixin,
                          LanguageResponseMixin,
                          serializers.ModelSerializer):
    class Meta:
        model = FoodTruck
        fields = ['id', 'name', 'description', 'language']
```

### Repeat for:
- [ ] `foodtrucks/api/serializers.py`
- [ ] `menu/api/serializers.py`
- [ ] `orders/api/serializers.py`
- [ ] `payments/api/serializers.py`
- [ ] `preferences/api/serializers.py`
- [ ] `users/api/serializers.py`

---

## Phase 7: Test Translations (⏳ TODO)

### Manual Testing:

```bash
# Start server
python manage.py runserver

# Test with curl
curl -H "Accept-Language: fr" http://localhost:8000/api/foodtrucks/
curl -H "Accept-Language: es" http://localhost:8000/api/foodtrucks/
curl http://localhost:8000/api/foodtrucks/  # Default (English)

# Verify response contains "language" field:
# {"language": "fr", "results": [...]}
```

### Test in Django Shell:

```bash
python manage.py shell

from django.utils import translation
from django.utils.translation import gettext_lazy as _

# Switch to French
translation.activate('fr')
print(translation.get_language())  # Should show 'fr'

# Test translation
msg = _("Name of the food truck")
print(msg)  # Should show French if translated
```

### Run Unit Tests:

```bash
# If you have tests (create them in Phase 9)
python manage.py test --pattern="test_i18n*.py"
```

---

## Phase 8: Documentation (📝 IN PROGRESS)

- [x] `locale/I18N_GUIDE.md` created
- [x] `locale/API_TESTING.md` created  
- [x] `foodtrucks/api/i18n_example_serializers.py` created
- [ ] `TRANSLATIONS.md` - Translation workflow guide
- [ ] API Examples in README showing language usage
- [ ] Contributing guide for translations

---

## Phase 9: Advanced Features (🔮 OPTIONAL)

### 9.1 Admin Language Selector
- [ ] Verify Django admin shows language selector
- [ ] Test switching languages in admin panel

### 9.2 Full Model Translation (django-modeltranslation)
- [ ] Install: `pip install django-modeltranslation`
- [ ] Configure translation fields for models
- [ ] Create migrations for translation tables
- [ ] Implement TranslationAdmin for admin interface

### 9.3 Frontend Integration
- [ ] Create language selector component (if you have frontend)
- [ ] Store user language preference
- [ ] Send Accept-Language header in all API requests

### 9.4 Caching Translations
- [ ] Cache translation strings in Redis
- [ ] Implement cache warming for performance
- [ ] Add cache invalidation on translation update

---

## Phase 10: Maintenance (🔄 ONGOING)

### After Each Code Change:

1. **New translatable strings added?**
   ```bash
   python manage.py makemessages -l fr -l es
   ```
   This updates .po files with new strings

2. **Translate new strings**
   - Edit `locale/fr/LC_MESSAGES/django.po`
   - Edit `locale/es/LC_MESSAGES/django.po`

3. **Recompile translations**
   ```bash
   python manage.py compilemessages
   ```

4. **Commit to version control**
   ```bash
   git add locale/
   git commit -m "Update translations for [feature name]"
   ```

### Quarterly Review:
- [ ] Check for untranslated strings: `grep -n '^msgstr ""' locale/*/LC_MESSAGES/django.po`
- [ ] Review new features for i18n compliance
- [ ] Update translation guidelines if needed

---

## Quick Command Reference

```bash
# Extract new strings for translation
python manage.py makemessages -l fr -l es

# Check for translation syntax errors
python manage.py compilemessages --check

# Compile translations (required before deployment)
python manage.py compilemessages

# View a specific translation
grep -A 3 'msgid "Your String"' locale/fr/LC_MESSAGES/django.po

# Count untranslated strings
grep 'msgstr ""' locale/fr/LC_MESSAGES/django.po | wc -l

# Delete all .mo files (for testing)
find locale -name "*.mo" -delete

# Test language context
python manage.py shell -c "
from django.utils import translation
translation.activate('fr')
print(translation.get_language())
"
```

---

## Common Issues & Solutions

### Issue 1: Strings not translating after I added translations

**Solution:**
```bash
# Recompile translations
python manage.py compilemessages

# Remove old .mo files
find locale -name "*.mo" -delete

# Recompile
python manage.py compilemessages

# Restart server
python manage.py runserver
```

### Issue 2: New strings not appearing in .po files

**Solution:**
- Ensure string is marked with `_()` or `gettext_lazy()`
- Run: `python manage.py makemessages -l fr -l es --no-wrap`
- Check file: `locale/fr/LC_MESSAGES/django.po`

### Issue 3: Admin interface still in English

**Solution:**
```bash
# Recompile messages
python manage.py compilemessages

# Restart development server
# Admin should now show language selector
```

### Issue 4: Accept-Language header not being recognized

**Solution:**
- Verify LocaleMiddleware in MIDDLEWARE (should be after SessionMiddleware)
- Check browser is sending Accept-Language header: `curl -v http://localhost:8000/api/foodtrucks/ | grep -i accept-language`
- Use explicit header: `curl -H "Accept-Language: fr" http://localhost:8000/api/foodtrucks/`

---

## Checklist Status

| Phase | Task | Status |
|-------|------|--------|
| 1 | Django i18n settings | ✅ Complete |
| 2 | Mark translatable strings | 🔄 In Progress |
| 3 | Extract strings  | ⏳ Ready to Start |
| 4 | Translate content | ⏳ Waiting on Phase 3 |
| 5 | Compile translations | ⏳ Waiting on Phase 4 |
| 6 | Update serializers | ⏳ Ready to Start |
| 7 | Test translations | ⏳ Waiting on Phase 5 |
| 8 | Documentation | 📝 In Progress |
| 9 | Advanced features | 🔮 Optional |
| 10 | Maintenance | 🔄 Future |

---

## Next Immediate Steps

1. **Start Phase 2**: Mark strings in existing models/serializers/views
2. **Run Phase 3**: Extract strings with `makemessages`
3. **Complete Phase 4**: Translate .po files to French/Spanish
4. **Run Phase 5**: Compile with `compilemessages`
5. **Implement Phase 6**: Update serializers with i18n mixins
6. **Execute Phase 7**: Test with Accept-Language header

**Estimated Time: 2-4 hours for complete implementation**

---

## Support Resources

- **Django i18n Docs**: https://docs.djangoproject.com/en/4.2/topics/i18n/
- **DRF Translation**: https://www.django-rest-framework.org/topics/internationalization/
- **i18n_guide.md**: Implementation walkthrough with examples
- **api_testing.md**: Testing strategies and curl examples
- **example_serializers.py**: Real serializer examples with i18n
