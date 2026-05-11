# 🔍 Diagnostic - Les mots clés ne sont pas pris en compte

## Problème rapporté
La recherche Business Intelligence n'inclut pas les mots clés personnalisés dans les résultats.

## Cause probable
Le paramètre `keywords` n'est pas envoyé au serveur, soit parce que:
1. **Cache navigateur** - Les fichiers JS en cache ne contiennent pas le nouveau code
2. **Mots clés non ajoutés** - L'utilisateur n'appuie pas sur Entrée/Tab pour les valider
3. **localStorage désactivé** - Les mots clés ne sont pas persistés
4. **Bug dans le code** - Il y a une erreur JavaScript

## Protocole de test (10 minutes)

### Phase 1: Préparation
```bash
# Sur votre serveur Django:
$ source venv/bin/activate
$ python manage.py runserver
# Attendez: "Starting development server..."
```

### Phase 2: Hard refresh (CRITIQUE!)
1. Allez à: `http://localhost:8000/foodtrucks/cucina-di-pastaz/dashboard/bi/`
2. **Mac**: Appuyez `Cmd + Shift + R` (hard refresh)
3. **Windows/Linux**: Appuyez `Ctrl + Shift + R`
4. **Attendez 3 secondes** que la page se recharge

### Phase 3: Ouvrir la console
1. Appuyez `F12` (ou `Cmd + Option + J` sur Mac)
2. Allez à l'onglet **Console**
3. Vous devriez voir un log: `🚀 BI page initializing...`
   - Si vous NE le voyez PAS → Erreur JavaScript grave!

### Phase 4: Ajouter manuellement des mots clés pour le test

Copiez-collez ceci **EXACTEMENT** dans la console (pas dans le navigateur!):

```javascript
// 1. Ajouter les mots-clés
document.getElementById('bi-custom-keywords').value = 'vegan, pizzeria, bio';

// 2. Déclencher le blur event
document.getElementById('bi-custom-keywords').dispatchEvent(new Event('blur'));

// 3. Attendre 1 seconde pour que le localStorage soit populé
setTimeout(() => {
    // 4. Vérifier que les mots-clés sont stockés
    const stored = localStorage.getItem('bi-targeting-custom-keywords');
    console.log('Stored in localStorage:', stored);
    
    // 5. Vérifier qu'ils vont être inclus dans les params
    const form = document.getElementById('dashboard-bi-target-form');
    const formData = new FormData(form);
    const selectedKeywords = formData.getAll('keywords');
    const customKeywords = JSON.parse(stored || '[]');
    console.log('Keywords to send:', [...selectedKeywords, ...customKeywords]);
}, 1000);
```

### Phase 5: Observer les logs

Regardez la console. Vous devriez voir:

**Succès** ✓:
```
✏️ Blur - Processing keywords: vegan, pizzeria, bio
✅ Keyword added and saved: vegan Total stored: ["vegan"]
✅ Keyword added and saved: pizzeria Total stored: ["vegan","pizzeria"]
✅ Keyword added and saved: bio Total stored: ["vegan","pizzeria","bio"]
Stored in localStorage: ["vegan","pizzeria","bio"]
Keywords to send: ["vegan","pizzeria","bio"]
```

**Erreur** ✗:
```
// Aucun log → JavaScript ne s'exécute pas du tout
// TypeError → Erreur dans le code
```

### Phase 6: Cliquer Apply targeting

1. Dans la console, regardez pour ces logs:
```
🔗 buildUrl called with params: {
    horizon_days: "90",
    ...
    keywords: "vegan,pizzeria,bio"  ← DOIT être présent
}
   ✓ Added keywords=vegan,pizzeria,bio
📍 Final URL: http://localhost:8000/...?...&keywords=vegan%2Cpizzeria%2Cbio
```

2. Si vous voyez `Skipped keywords` au lieu de `Added keywords` → **PROBLÈME GRAVE!**

### Phase 7: Vérifier l'URL

Dans DevTools, onglet **Network**:
1. Cherchez la requête vers `/dashboard/bi/` (ou cherchez "bi" dans Filter)
2. Cliquez dessus
3. Regardez l'URL complète dans la colonne "Request"
4. Vérifiez que `keywords=vegan%2Cpizzeria%2Cbio` est présent

Si c'est absent → **Les keywords ne sont jamais envoyés!**

### Phase 8: Vérifier les résultats

Si tout fonctionne:
- Les événements affichés doivent contenir "vegan" ou "pizzeria" ou "bio"  
- Les événements sans ces mots ne doivent pas s'afficher

## Rapporter le problème

Si ça ne fonctionne pas, collectez:

1. **Screenshot de la console** avec tous les logs
2. **Screenshot de l'onglet Network** montrant l'URL complète
3. **Message d'erreur exact** (s'il y en a un)
4. **Navigateur utilisé** (Chrome, Firefox, Safari, etc.)
5. **OS** (Mac, Windows, Linux)

## Cas possibles et solutions

| Symptôme | Cause | Solution |
|----------|-------|----------|
| Pas de log "🚀 BI page initializing" | JS ne charge pas | Hard refresh + vérifier console pour erreurs |
| "✏️ Blur" mais pas "✅ Keyword added" | Error dans addCustomKeyword() | Vérifier les erreurs rouges dans console |
| Pas de "Targeted params" log | getTargetingParams() ne s'exécute pas | Vérifier fetch de l'API |
| "buildUrl called" mais "keywords" pas "Added" | buildUrl filtre les keywords | Vérifier que keywords n'est pas vide |
| URLs sans keywords | Pas de mots clés dans params | Vérifier localStorage n'a pas les données |
| Résultats ne changent pas | Backend n'utilise pas keywords | Vérifier Django logs du serveur |

## Tests rapides du backend

```bash
# En cas de doute, tester le serveur directement:
python manage.py shell

# Vérifier qu'il y a des événements
>>> from analytics.models import Event
>>> Event.objects.count()  # Doit être > 0

# Vérifier qu'il y a des événements avec les keywords  
>>> Event.objects.filter(name__icontains='vegan').count()
>>> Event.objects.filter(name__icontains='pizzeria').count()
```

## Fichiers de référence

- **Implementation**: `/static/js/dashboard/business_intelligence.js`
- **Template**: `/foodtrucks/templates/foodtrucks/business_intelligence.html`
- **Backend**: `/foodtrucks/views.py` (fonction `DashboardTargetingAPIView.get()`)
- **API builder**: `/static/js/dashboard/api.js` (fonction `buildUrl()`)

## Aide rapide

- Vous oubliez toujours d'appuyer sur Entrée? → Les mots clés ne sont jamais ajoutés
- Format d'entrée: `keyword1, keyword2, keyword3` (virgule + espace)
- Les tags doivent tous apparaître en **bleu** avec un **×** pour supprimer
- Chaque refresh de page restaure les précédents mots clés

## Debug final

Si vous êtes bloqué, lancez ceci dans la console pour un rapport complet:

```javascript
console.log('=== KEYWORDS DIAGNOSTIC ===');
console.log('localStorage:', localStorage.getItem('bi-targeting-custom-keywords'));
console.log('Form exists:', !!document.getElementById('dashboard-bi-target-form'));
console.log('Input exists:', !!document.getElementById('bi-custom-keywords'));  
console.log('Tags container exists:', !!document.getElementById('bi-custom-keywords-tags'));
console.log('Tags HTML:', document.getElementById('bi-custom-keywords-tags').innerHTML);
```

Partagez la sortie de cela avec le support!
