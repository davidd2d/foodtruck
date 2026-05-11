# ✅ Guide de test - Mots clés personnalisés BI

## 5 minutes de test rapide

### Étape 1: Hard refresh ⚡
```
Mac: Cmd + Shift + R
Windows: Ctrl + Shift + R
```
C'est **critique** - il faut videz le cache sinon les vieux fichiers JS s'exécutent.

### Étape  2: Ouvrir DevTools 🔧
-Appuyez sur **F12** (ou Cmd+Option+J sur Mac)
- Allez à l'onglet **Console**

### Étape 3: Ajouter un mot clé 📝

Tapez ceci dans la console (et appuyez sur Entrée):

```javascript
document.getElementById('bi-custom-keywords').value = 'vegan, pizzeria';
document.getElementById('bi-custom-keywords').dispatchEvent(new Event('blur'));
```

### Étape 4: Observer les logs 📡

Dans la console, vous devriez voir:
```
✏️ Blur - Processing keywords: vegan, pizzeria
✅ Keyword added and saved: vegan Total stored: ["vegan"]
✅ Keyword added and saved: pizzeria Total stored: ["vegan","pizzeria"]
```

### Étape 5: Cliquer Apply targeting 🎯

À cette étape, dans la console allez voir:
```
🔗 buildUrl called with params: {
	horizon_days: "90",
	min_attendance: "0",
	min_score: "0",
	period: "full_day",
	limit: "5",
	radius_km: "50",
	keywords: "vegan,pizzeria"  ← IMPORTANT: doit être présent!
}
   ✓ Added keywords=vegan,pizzeria
📍 Final URL: http://...?horizon_days=90&...&keywords=vegan%2Cpizzeria
```

### Étape 6: Vérifier l'onglet Network 🌐

Dans DevTools, onglet **Network**:
1. Cherchez la requête vers `/dashboard/bi/`
2. Vérifiez l'URL pour voir `?...&keywords=vegan%2Cpizzeria`
3. Si `keywords=...` est ABSENT → problème!

## 🚨 Tableau de diagnostic

| Observation | Cause | Solution |
|------------|-------|----------|
| Pas de logs "✏️ Blur" | Champ input pas trouvé | F12 → `document.getElementById('bi-custom-keywords')` doit retourner un élément |
| Logs "✏️" mais pas "✅" | addCustomKeyword crash | Vérifier les erreurs en rouge dans la console |
| Tags n'apparaissent pas | renderCustomKeywordTags() fail | Vérifier le container `#bi-custom-keywords-tags` existe |
| Tags apparaissent mais pas envoyés | localStorage pas lu | `localStorage.getItem('bi-targeting-custom-keywords')` doit retourner `["vegan","pizzeria"]` |
| URL n'a pas `keywords=` | buildUrl scrute | Vérifier que `buildUrl` reçoit bien les params |
| Résultats ne changent pas | Backend ne filtre pas | Le serveur reçoit les keywords? Vérifier Django logs |

## ⚙️ Pour les développeurs

```bash
# Test rapide du backend
python manage.py shell
>>> from analytics.models import Event
>>> Event.objects.filter(name__icontains='vegan').count()
# Doit retourner > 0 s'il y a des événements avec 'vegan'

# Ou tester directement:
curl 'http://localhost:8000/foodtrucks/cucina-di-pastaz/dashboard/bi/?keywords=vegan'
# Doit retourner du JSON avec status 200
```

## 📝 Si ça ne fonctionne toujours pas

Créez une screenshot de:
1. La zone Keywords (avec tags visibles)
2. La console après avoir cliqué "Apply targeting"
3. L'onglet Network montrant l'URL complète

Et rapportez le problème avec ces infos.

## ✅ À vérifier dans l'ordre

- [ ] Hard refresh fait
- [ ] Console ouverte
- [ ] Mots clés ajoutés et tags visibles
- [ ] Logs console à "Blur" affichés
- [ ] Logs "Keyword added" affichés  
- [ ] Apply targeting cliqué
- [ ] Logs "buildUrl" affichent les keywords
- [ ] URL finale contient `keywords=...`
- [ ] Résultats affichent des événements avec les keywords

Si tout ✓, la feature fonctionne!
