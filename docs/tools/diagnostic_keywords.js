// Diagnostic script pour vérifier les mots clés personnalisés
// À copier-coller dans la console du navigateur

(function() {
    console.clear();
    console.log('%c=== DIAGNOSTIC MOTS CLÉS PERSONNALISÉS ===', 'color: blue; font-size: 16px; font-weight: bold');
    
    // 1. Vérifier localStorage
    console.log('\n%c1. État du localStorage', 'color: green; font-weight: bold');
    const customKeywordsKey = 'bi-targeting-custom-keywords';
    const stored = localStorage.getItem(customKeywordsKey);
    console.log(`   Key: ${customKeywordsKey}`);
    console.log(`   Value:`, stored);
    
    if (stored) {
        try {
            const parsed = JSON.parse(stored);
            console.log('   ✓ Parsed successfully:', parsed);
            console.log('   Type:', Array.isArray(parsed) ? 'Array' : 'Not an array');
            console.log('   Length:', parsed.length);
        } catch (e) {
            console.log('   ✗ Parse error:', e.message);
        }
    } else {
        console.log('   ⚠️  Pas de mots clés personnalisés stockés');
    }
    
    // 2. Vérifier le formulaire
    console.log('\n%c2. État du formulaire', 'color: green; font-weight: bold');
    const form = document.getElementById('dashboard-bi-target-form');
    if (form) {
        console.log('   ✓ Form trouvée');
        const formData = new FormData(form);
        const selectedKeywords = formData.getAll('keywords');
        console.log('   Keywords prédéfinis sélectionnés:', selectedKeywords);
    } else {
        console.log('   ✗ Form NOT trouvée');
    }
    
    // 3. Simuler getTargetingParams
    console.log('\n%c3. Simulation de getTargetingParams()', 'color: green; font-weight: bold');
    if (form && stored) {
        try {
            const forData = new FormData(form);
            const selectedKeywords = forData.getAll('keywords');
            const customKeywords = JSON.parse(stored);
            const allKeywords = [...selectedKeywords, ...customKeywords];
            
            console.log('   Keywords sélectionnés:', selectedKeywords);
            console.log('   Keywords personnalisés:', customKeywords);
            console.log('   Tous les keywords:', allKeywords);
            console.log('   Joindre avec virgule:', allKeywords.join(','));
        } catch (e) {
            console.log('   ✗ Erreur:', e.message);
        }
    }
    
    // 4. L'interface pour ajouter un mot clé
    console.log('\n%c4. Interface d\'ajout de mots clés', 'color: green; font-weight: bold');
    const input = document.getElementById('bi-custom-keywords');
    if (input) {
        console.log('   ✓ Champ input trouvé');
        console.log('   Valeur actuelle:', input.value);
        console.log('   \n   💡 Pour tester, tapez dans la console:');
        console.log('      document.getElementById("bi-custom-keywords").value = "vegan, pizzeria"');
        console.log('      document.getElementById("bi-custom-keywords").dispatchEvent(new Event("blur"))');
    } else {
        console.log('   ✗ Champ input NOT trouvé');
    }
    
    // 5. Les tags affichés
    console.log('\n%c5. Tags affichés', 'color: green; font-weight: bold');
    const tagsContainer = document.getElementById('bi-custom-keywords-tags');
    if (tagsContainer) {
        console.log('   ✓ Container trouvé');
        const badges = tagsContainer.querySelectorAll('span.badge');
        console.log(`   Nombre de tags: ${badges.length}`);
        badges.forEach((badge, i) => {
            console.log(`   Tag ${i + 1}:`, badge.textContent.trim());
        });
    } else {
        console.log('   ✗ Container NOT trouvé');
    }
    
    console.log('\n%c=== FIN DIAGNOSTIC ===', 'color: blue; font-size: 16px; font-weight: bold');
})();
