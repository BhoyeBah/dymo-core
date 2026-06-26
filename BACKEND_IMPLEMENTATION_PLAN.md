# BACKEND IMPLEMENTATION PLAN

## 1. Vision

Créer un backend SaaS B2B multi-tenant, installable comme package Python, orienté FastAPI, PostgreSQL et SQLAlchemy, capable de servir de socle commun à plusieurs produits métiers.

Objectifs clés :
- Fournir une authentification robuste ;
- Isoler strictement chaque tenant ;
- Intégrer un RBAC extensible et dynamique ;
- Gérer les plans, quotas, features, abonnements, billing et paiements ;
- Gérer de manière robuste les Upgrades / Downgrades (prorata, downgrade planifié, restrictions de quota) ;
- Implémenter un système d'Access Control strict à 4 niveaux (Permission, Abonnement, Feature, Quota) ;
- Centraliser les configurations de providers techniques exclusivement côté Super Admin Dymo (aucun credentials dans l'espace client) ;
- Fournir notifications, webhooks, audit logs, analytics et API keys ;
- Permettre l'ajout de modules métiers sans modifier le core via un registre d'extension.

---

## 2. Principes d'architecture des espaces

Le projet est divisé en **uniquement deux espaces applicatifs** :

*   **`/platform`** : Espace réservé à Dymo (Super Admin). Permet de superviser les tenants, plans, configurations globales et logs techniques.
*   **`/app`** : Espace client complet (Tenant). Regroupe les fonctions d'administration d'entreprise (membres, rôles, facturation, settings) et les modules métiers (caisse, ventes, etc.).

Toutes les anciennes routes et références à `/console`, `/tenant-console` ou `/tenant-app` sont supprimées et consolidées sous ces deux espaces.

---

## 3. Phases d'exécution

### Phase 0 - Socle de projet
- Structurer le package Python `dymo_saas_core`.
- Définir les conventions de configuration et d'injection de dépendances.
- Préparer les points d'extension pour les modules métiers.
- Poser la base de logging, erreurs et settings.

### Phase 1 - Fondation API
- Créer la fonction `setup_saas_core(app)`.
- Brancher les routes du core sous les préfixes `/api/v1/platform` et `/api/v1/app`.
- Brancher les middlewares (CORS, Tenant Context resolution).
- Brancher les exception handlers standardisés.
- Mettre en place la résolution automatique du contexte tenant.

### Phase 2 - Auth et identité
- Inscription et initialisation de tenant.
- Connexion (génération de JWT court en HTTPOnly).
- Refresh token et mécanisme de rotation.
- Réinitialisation de mot de passe et vérification d'email par token crypté.
- Révocation de sessions.

### Phase 3 - Multi-tenant et utilisateurs
- Création et modification de tenants.
- Inviter des collaborateurs et gérer les statuts d'invitation.
- Profils utilisateurs et mise à jour de la dernière connexion.
- Isolation stricte des données en base (clé étrangère `tenant_id` sur toutes les tables client/métier).

### Phase 4 - RBAC
- Initialisation des rôles système par défaut (`owner`, `admin`, `user`).
- Gestion des permissions globales et création de permissions spécifiques.
- Scoping dynamique des droits par tenant.
- Guards de route basés sur les rôles et permissions.

### Phase 4.5 - Access Control et blocage des fonctionnalités
Implémenter la validation et le blocage à 4 niveaux distincts sur les routes sensibles :
1.  **Permission** : L'utilisateur connecté possède-t-il la permission requise ?
2.  **Abonnement** : Le tenant possède-t-il un abonnement actif et non suspendu ?
3.  **Feature** : Le plan actuel du tenant donne-t-il accès à cette fonctionnalité spécifique ?
4.  **Quota** : La limite d'usage sur la ressource n'est-elle pas dépassée ?

Création des dépendances FastAPI suivantes :
- `require_authenticated_user()`
- `require_super_admin()`
- `require_tenant_member()`
- `require_role(role_name: str)`
- `require_any_role(role_names: list[str])`
- `require_permission(permission_code: str)`
- `require_any_permission(permission_codes: list[str])`
- `require_all_permissions(permission_codes: list[str])`
- `require_active_subscription()`
- `require_feature_access(feature_code: str)`
- `require_usage_limit(resource_code: str)`

### Phase 5 - Plans et quotas
- Création et gestion des plans par le Super Admin.
- Déclaration des features associées à chaque plan.
- Définition des quotas et limites maximales par ressource (ex: nombre maximal de collaborateurs, de transactions, etc.).

### Phase 6 - Abonnements (Subscriptions)
- Cycle de vie de l'abonnement (période d'essai, actif, expiré, suspendu).
- Association d'un plan à un tenant.
- Événements d'activation et d'expiration d'abonnement.

### Phase 6.5 - Upgrade / Downgrade
Gérer les transitions de plans d'abonnement de manière automatisée :
-  **Upgrade immédiat** : Appliqué dès validation du paiement. Calcul du prorata sur la période restante de l'ancien plan, génération du paiement d'upgrade, application immédiate et audit log.
-  **Downgrade programmé** : Reste sur le plan actuel jusqu'à la fin de la période de facturation en cours. Statut passe à `pending_downgrade`. Possibilité d'annulation avant application. Transition automatique à la date d'échéance avec vérification des quotas actuels et application des blocages si dépassement.
-  **Downgrade forcé** : Déclenché par le Super Admin (par exemple pour non-paiement). Réduction immédiate de plan, vérification immédiate des limites et journalisation d'audit obligatoire.
-  **Table `core_subscription_changes`** : Historisation de tous les mouvements avec statuts d'application.

### Phase 7 - Billing et Payments
- Génération de factures (`core_invoices`) et de reçus de paiement (`core_payments`).
- Intégration de Stripe ou de providers de paiement tiers (DexPay).
- Webhooks provider sécurisés et idempotents.
- Suivi du statut des transactions et relance automatique pour impayés.

### Phase 8 - Providers globaux (Super Admin uniquement)
- Configuration des clés techniques API (SMTP, SMS, WhatsApp, passerelles de paiement).
- Chiffrement des secrets en base de données.
- Accès et tests de connectivité exclusifs au Super Admin (`/api/v1/platform/providers`).
- **Interdiction absolue** de gestion provider dans `/app` pour les locataires.
- Journalisation d'audit des modifications de configuration de providers.

### Phase 9 - Notifications et usage
- Envoi et routage des emails, SMS, WhatsApp et webhooks système.
- Compteurs d'usage (`core_usage_counters`) incrémentés en base de données.
- Mécanismes d'alerte à l'approche des limites de quota (ex: 80%, 100%).

### Phase 10 - Audit et analytics
- Journal d'audit centralisé (`core_audit_logs`) traçant les actions critiques (connexions, modifications RBAC, changements de plan, édition de secrets).
- KPIs Plateforme (MRR, ARR, LTV, churn, volume de transactions).
- KPIs Tenant (consommation, historique des actions).

### Phase 11 - CLI, migrations et tests
- CLI d'administration (seeding, création de super admin, diagnostics).
- Fichiers de migration Alembic.
- Suite de tests unitaires et d'intégration (`pytest`).

### Phase 12 - Documentation finale
- Guides d'intégration, guide de développement de modules métiers, et documentation des routes de l'API.

---

## 4. Ordre de priorité d'implémentation

1. Socle projet et fondation API (Phases 0-1)
2. Authentification et Isolation Tenant (Phases 2-3)
3. Rôles et Permissions (Phase 4)
4. Access Control Guards à 4 niveaux (Phase 4.5)
5. Configuration des Providers Globaux sécurisés (Phase 8)
6. Plans, Quotas et Subscriptions (Phases 5-6)
7. Logique d'Upgrade / Downgrade et proratisation (Phase 6.5)
8. Facturation, Paiements et Webhooks idempotents (Phase 7)
9. Notifications, Compteurs d'Usage et Audit Logs (Phases 9-10)
10. CLI, Tests et validation complète (Phase 11)
11. Finalisation de la documentation (Phase 12)
