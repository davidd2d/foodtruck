# 📜 README_COMPLIANCE.md

## 🎯 Objectif

Ce document définit les règles de conformité applicables au système de commande et de paiement du SaaS food truck.

La conformité repose sur 3 piliers :
- règles métier strictes
- implémentation backend (models/services)
- tests automatisés obligatoires

⚠️ Toute modification du système de paiement ou de commande DOIT respecter ce document.

---

# 1. 🧾 Scope

## Modèle actuel (MVP)

- Paiement via Stripe Checkout
- Les food trucks encaissent directement
- Aucune gestion de marketplace (pas de redistribution de fonds)
- Paiement en ligne et/ou sur place

---

# 2. 💳 Paiement

## Règles

- Aucune donnée de carte bancaire ne doit être stockée
- Le paiement est validé uniquement via webhook Stripe
- Le frontend n'est JAMAIS une source de vérité
- Chaque paiement doit être idempotent

## Implémentation requise

- Modèle `Payment`
- Champ `stripe_session_id`
- Champ `stripe_payment_intent`
- Statut (`pending`, `paid`, `failed`)
- Modèle `StripeEvent` pour idempotence

## Contraintes techniques

- Vérification de signature Stripe obligatoire
- Refus de traitement si signature invalide

## Tests obligatoires

- `test_payment_validated_only_by_webhook`
- `test_webhook_signature_verification`
- `test_webhook_idempotency`

---

# 3. 🧾 Commandes (Conformité fiscale - loi anti-fraude TVA)

## Règles

- Une commande payée est IMMUTABLE
- Une commande payée ne peut pas être supprimée
- Toute modification doit être historisée

## Implémentation requise

- Champ `paid_at`
- Méthode `can_be_modified()`
- Protection au niveau modèle (pas seulement vue)

## Interdictions

- Modifier une commande après paiement
- Supprimer une commande payée
- Modifier les montants après paiement

## Tests obligatoires

- `test_paid_order_cannot_be_modified`
- `test_paid_order_cannot_be_deleted`

---

# 4. 💰 TVA & montants

## Règles

- Les montants sont figés au moment de la commande
- Le taux de TVA est stocké avec chaque item
- Aucun recalcul après paiement

## Implémentation requise

- Champs :
  - `unit_price`
  - `tax_rate`
  - `tax_amount`
  - `total_price`

## Tests obligatoires

- `test_order_total_is_frozen_after_payment`
- `test_tax_amount_is_preserved`

---

# 5. 🧾 Tickets & facturation

## Règles

Chaque commande payée doit générer un ticket avec :
- nom du food truck
- date et heure
- détail des produits
- total TTC
- TVA

## Contraintes

- Numérotation unique et continue
- Données non modifiables

## Tests obligatoires

- `test_ticket_generated_on_payment`
- `test_ticket_is_immutable`

---

# 6. 🔁 Idempotence

## Règles

- Un événement Stripe ne doit être traité qu'une seule fois

## Implémentation requise

- Modèle `StripeEvent`
- Champ unique `stripe_event_id`

## Tests obligatoires

- `test_stripe_event_processed_once`

---

# 7. 🔐 Sécurité

## Obligations

- HTTPS obligatoire
- Protection CSRF activée
- Protection XSS
- Vérification signature Stripe

## Tests obligatoires

- `test_stripe_signature_required`

---

# 8. 🧠 Intégrité métier

## Order

- Statut cohérent (`pending`, `paid`, `cancelled`)
- Total figé
- Non modifiable après paiement

## Payment

- Relation OneToOne avec Order
- Source de vérité = Stripe webhook

## PickupSlot

- Ne doit jamais être surbooké

## Tests obligatoires

- `test_order_status_flow`
- `test_slot_capacity_not_exceeded`

---

# 9. 🔒 RGPD

## Données concernées

- nom
- email
- téléphone

## Règles

- minimisation des données
- possibilité d'anonymisation
- suppression sur demande

## Implémentation requise

- méthode `anonymize()`
- séparation snapshots client / données financières
- politique de rétention batchée
- anonymisation irréversible sans suppression des écritures financières

## Tests obligatoires

- `test_order_anonymization`

---

# 9.b 🗃️ Rétention des données

## Règles

- seules les commandes payées peuvent être anonymisées automatiquement
- aucune suppression physique des commandes, paiements, tickets ou montants
- l’anonymisation doit être batchable et idempotente

## Implémentation requise

- service `DataRetentionService`
- commande `anonymize_old_orders`
- script planifié `scripts/run_anonymize_old_orders.sh`
- template launchd macOS `ops/launchd/com.foodtruck.anonymize-old-orders.plist`

---

# 9.c 📤 Export comptable

## Règles

- export uniquement depuis les montants stockés
- aucune fuite de données personnelles dans l’export comptable
- journalisation de chaque export

## Implémentation requise

- service `AccountingExportService`
- format CSV UTF-8 compatible import comptable
- endpoint sécurisé `GET /api/payments/accounting-export/`
- filtrage strict par propriétaire ou food truck autorisé

---

# 9.d 🏦 Stripe Connect vendeur

## Règles

- chaque food truck peut disposer d’un compte Stripe Connect dédié
- l’onboarding vendeur doit être relançable sans créer plusieurs comptes
- l’état du compte vendeur doit être synchronisé par webhook Stripe

## Implémentation requise

- champs `stripe_connect_account_id`, `stripe_onboarding_completed`, `stripe_details_submitted`, `stripe_charges_enabled`, `stripe_payouts_enabled` sur `FoodTruck`
- service `StripeConnectService`
- endpoint sécurisé d’onboarding vendeur
- prise en charge du webhook `account.updated`

---

# 10. 📊 Logs & audit

## Obligations

- logs sur :
  - paiements
  - erreurs
  - modifications critiques
  - anonymisation RGPD
  - export comptable

## Implémentation recommandée

- modèle `AuditLog` ou équivalent

## Tests obligatoires

- `test_audit_log_created_on_payment`

---

# 11. 🚫 Interdictions globales

- Modifier une commande payée
- Supprimer une commande payée
- Recalculer un montant après paiement
- Valider un paiement sans webhook Stripe
- Ignorer l’idempotence

---

# 12. 🧪 Politique de tests

## Règle

Toute règle de conformité DOIT avoir un test associé.

## CI/CD

- Aucun merge si un test de conformité échoue

---

# 13. 🧱 Architecture obligatoire

## Business logic

- DOIT être dans :
  - modèles
  - services

- NE DOIT PAS être dans :
  - vues
  - templates
  - JavaScript

---

# 14. 📌 Responsabilité

## SaaS

- responsable de :
  - la logique métier
  - la sécurité
  - la conformité des données

## Food truck

- responsable de :
  - la déclaration fiscale
  - la TVA
  - l'encaissement final

---

# 15. 🚀 Évolutions futures

Si passage à marketplace :
- Stripe Connect obligatoire
- KYC des vendeurs
- réglementation financière renforcée

---

# ✅ Conclusion

La conformité n'est pas uniquement documentaire.

Elle est garantie par :
- des règles strictes
- du code qui empêche les violations
- des tests automatisés

👉 Toute contribution doit respecter ces principes.