# Plan de test: Feature mots clés personnalisés - Business Intelligence

## Objectif
Vérifier que la page Business Intelligence implémente correctement:
1. Les traductions des mots clés (Festival, Marché, Concert, Sports, Famille)
2. L'ajout de mots clés personnalisés
3. La persistance des choix de l'utilisateur

## Prérequis
- Accès à une food truck (ou créer une pour tester)
- Navigateur avec support localStorage
- Langue définie sur Français

## Procédure de test

### Test 1: Affichage des traductions
1. Aller à `/foodtrucks/<slug>/dashboard/business-intelligence/`
2. Vérifier que les mots clés affichés sont:
   - [ ] Festival (au lieu de "festival")
   - [ ] Marché (au lieu de "market")
   - [ ] Concert (au lieu de "concert")
   - [ ] Sports (au lieu de "sports")
   - [ ] Famille (au lieu de "family")

### Test 2: Interface mots clés personnalisés
1. Sur la même page, vérifier qu'on voit:
   - [ ] Label "Ajouter des mots clés personnalisés"
   - [ ] Champ input avec placeholder "Entrez les mots clés séparés par des virgules..."
   - [ ] Texte d'aide: "Les mots clés personnalisés seront ajoutés à la recherche"
   - [ ] Zone pour afficher les tags (vide initialement)

### Test 3: Ajouter des mots clés personnalisés
1. Dans le champ input, taper: `vegan, bio`
2. Appuyer sur Entrée après le dernier mot clé
3. Vérifier que:
   - [ ] Un tag "vegan" apparaît avec bouton ✕
   - [ ] Un tag "bio" apparaît avec bouton ✕
   - [ ] Le champ input est vidé

### Test 4: Suppression de mots clés
1. Cliquer sur le ✕ d'un des tags
2. Vérifier que:
   - [ ] Le tag est supprimé
   - [ ] L'autre tag reste

### Test 5: Persistance localStorage
1. Ajouter des mots clés: `pizzeria, vegan`
2. Cocher quelques checkboxes (ex. Festival, Sports)
3. Changer d'autres paramètres (horizon, radius, etc.)
4. Rafraîchir la page (F5)
5. Vérifier que:
   - [ ] Les checkboxes cochées sont toujours cochées
   - [ ] Les mots clés personnalisés sont toujours affichés
   - [ ] Les autres paramètres sont mémorisés

### Test 6: Recherche avec mots clés personnalisés
1. Ajouter des mots clés personnalisés: `street art`
2. Sélectionner quelques mots clés prédéfinis
3. Cliquer sur "Apply targeting"
4. Vérifier qu'en inspectant le réseau (DevTools):
   - [ ] La requête inclut tous les mots clés (prédéfinis + personnalisés)
   - [ ] Les résultats reflètent la recherche combinée

### Test 7: Interaction clavier (bonus)
1. Dans le champ input, taper: `tag1, tag2, tag3,`
2. Appuyer sur Tab pour quitter le champ
3. Vérifier que tous les tags sont créés

### Test 8: Cas limites
1. Taper "   " (espaces) → ne doit pas créer de tag vide
2. Taper un mot déjà existant → ne doit pas créer de doublon
3. Taper "VEGAN" → doit être converti en "vegan" (lowercase)

## Résultats attendus
- ✅ Toutes les traductions affichées correctement
- ✅ Interface intuitive pour ajouter/supprimer des mots clés
- ✅ Persistance fonctionnelle entre sessions
- ✅ Intégration avec la recherche BI

## Notes techniques
- localStorage key: `bi-targeting-custom-keywords` (JSON array)
- localStorage key: `bi-targeting-form-state` (JSON object with all form values)
- Tags affichés avec classe Bootstrap: badge, bg-info, text-dark
- Suppression via onclick handler: `removeCustomKeyword(keyword, event)`
