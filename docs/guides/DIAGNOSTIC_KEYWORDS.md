# Guide de diagnostic - Mots clés personnalisés ne sont pas utilisés

## Symptôme
Les mots clés personnalisés ajoutés à la page Business Intelligence ne sont pas inclus dans la recherche.

## Checklist de test

### 1. ⚙️ Hard refresh du navigateur
D'abord, videz le cache du navigateur pour la page:
- **Mac**: Cmd + Shift + R
- **Windows/Linux**: Ctrl + Shift + R

C'est critique car les fichiers JavaScript peuvent être en cache.

### 2. 📝 Test d'ajout de mots clés

Naviguez vers `/foodtrucks/cucina-di-pastaz/dashboard/bi/` et:

1. Ouvrez la console du navigateur (F12 ou Cmd+Option+J)
2. Tapez ces commandes pour tester l'adding de mots clés:

```javascript
// Copier-coller ce script dans la console
document.getElementById('bi-custom-keywords').value = 'vegan, pizzeria';
document.getElementById('bi-custom-keywords').dispatchEvent(new Event('blur'));
console.log('localStorage:', localStorage.getItem('bi-targeting-custom-keywords'));
```

### 3. 🔍 Vérifier le stockage

Après avoir ajouté les mots clés, tapez dans la console:

```javascript
// Vérifier les mots clés stockés
const stored = localStorage.getItem('bi-targeting-custom-keywords');
console.log('Mots clés stockés:', stored);
console.log('Parsed:', JSON.parse(stored || '[]'));
```

Vous devriez voir:
```
Mots clés stockés: ["vegan","pizzeria"]
Parsed: ["vegan", "pizzeria"]
```

### 4. 🎯 Vérifier les paramètres envoyés

Avant de cliquer sur "Apply targeting":

```javascript
// Dans la console, vérifier les paramètres qui seront envoyés
// D'abord, copiez cette fonction:
function testGetTargetingParams() {
    const form = document.getElementById('dashboard-bi-target-form');
    const formData = new FormData(form);
    const selectedKeywords = formData.getAll('keywords');
    const customKeywords = JSON.parse(localStorage.getItem('bi-targeting-custom-keywords') || '[]');
    const allKeywords = [...selectedKeywords, ...customKeywords];
    
    const params = {
        horizon_days: formData.get('horizon_days'),
        min_attendance: formData.get('min_attendance'),
        min_score: formData.get('min_score'),
        period: formData.get('period'),
        limit: formData.get('limit'),
        radius_km: formData.get('radius_km'),
    };
    
    if (allKeywords.length > 0) {
        params.keywords = allKeywords.join(',');
    }
    
    return params;
}

// Ensuite, exécutez:
console.log('Targeting params:', testGetTargetingParams());
```

Vous devriez voir dans les logs:
```
Targeting params: {
    horizon_days: "90",
    min_attendance: "0",
    min_score: "0",
    period: "full_day",
    limit: "5",
    radius_km: "50",
    keywords: "vegan,pizzeria"     ← Ces mots clés DOIVENT être là
}
```

### 5. 📡 Vérifier la requête HTTP

1. Ouvrez l'onglet "Network" (Réseau) dans les DevTools (F12)
2. Cliquez sur "Apply targeting"
3. Observez la requête GET vers `/foodtrucks/cucina-di-pastaz/dashboard/bi/`
4. Vérifiez l'URL pour voir les paramètres envoyés (Query String)

Vous devriez voir dans l'URL:
```
?horizon_days=90&min_attendance=0&min_score=0&period=full_day&limit=5&radius_km=50&keywords=vegan%2Cpizzeria
```

Si `keywords=...` est absent, c'est que les mots clés ne sont pas envoyés au serveur.

### 6. 📊 Vérifier les console logs

En ouvrant les DevTools, vous devriez voir de logs comme:

```
🚀 BI page initializing...
📦 Stored custom keywords: ["vegan", "pizzeria"]
✏️ Adding custom keyword: vegan
✏️ Adding custom keyword: pizzeria
✅ Keyword added and saved: vegan Total stored: ["vegan"]
✅ Keyword added and saved: pizzeria Total stored: ["vegan", "pizzeria"]
Targeting params: {
    horizon_days: "90",
    ...
    keywords: "vegan,pizzeria"
}
```

## 🚨 Dépannage

### Les mots clés ne s'ajoutent pas du tout
- **Possible cause**: Le champ input `bi-custom-keywords` n'existe pas ou n'est pas trouvé
- **Solution**: Vérifier qu'il n'y a pas d'erreur JavaScript dans la console

### Les mots clés s'ajoutent mais ne persistent pas
- **Possible cause**: localStorage est désactivé ou l'erreur de parse
- **Solution**: Vérifier `localStorage.getItem(key)` dans la console

### Les mots clés persistent mais ne sont pas envoyés
- **Possible cause**: La fonction `getTargetingParams()` ne les inclut pas
- **Solution**: Vérifier les logs console lors du submit du formulaire

### Les keywords sont envoyés mais pas utilisés dans la recherche
- **Possible cause**: Le backend ne traite pas correctement le paramètre
- **Solution**: Vérifier les logs Django du serveur

## 📋 Commande diagnostic rapide

Copier-coller cela entièrement dans la console:

```javascript
// diagnostic_keywords.js - Copier du fichier /docs/tools/diagnostic_keywords.js
// (voir le contenu du fichier)
```

Ou ouvrir la page HTML de test:
```
Ouvrir le fichier local `docs/tools/test_keywords_localstorage.html`
```

## 🔗 Fichiers d'implémentation
- `/static/js/dashboard/business_intelligence.js` - Logique JS + localStorage
- `/foodtrucks/templates/foodtrucks/business_intelligence.html` - Template HTML
- `/foodtrucks/views.py` - Backend pagination des keywords

## ✅ Résumé des étapes pour valider

```
1. Cmd+Shift+R (hard refresh)
2. Ajouter un mot clé (vegan)
3. Vérifier localStorage → ['vegan']
4. Vérifier getTargetingParams() → keywords: "vegan"
5. Cliquer "Apply targeting"
6. Vérifier URL → ?...&keywords=vegan
7. Vérifier que les résultats changent
```

Si tout fonctionne, vous devriez voir des événements contenant le mot clé "vegan" s'afficher dans les résultats.
