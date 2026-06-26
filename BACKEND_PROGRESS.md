# Backend Progress — Dymo SaaS Core

## Validation actuelle

- Suite complète `pytest`: `73 passed`
- Couverture validée sur l’auth, multi-tenant, RBAC, plans, abonnements, upgrade/downgrade, billing, cache, cash register, outbox, webhooks, API keys, providers plateforme, analytics, payments et audit logs
- Les tests sont exécutés sur une base SQLite isolée par processus pour garantir l’indépendance locale et CI
- Les routes `/api/v1/app/roles/roles` et `/api/v1/app/roles/roles/{role_id}` ont été supprimées au profit de la structure canonique `/api/v1/app/roles/*`
- Les routes plateforme `/api/v1/platform/providers`, `/api/v1/platform/provider-logs`, `/api/v1/platform/payments`, `/api/v1/platform/invoices`, `/api/v1/platform/dashboard`, `/api/v1/platform/analytics/*` et `/api/v1/platform/audit-logs` sont en place

## Statut global

- [x] Phase 0 — Socle projet
- [x] Phase 1 — Fondation API
- [x] Phase 2 — Auth
- [x] Phase 3 — Multi-tenant et users
- [x] Phase 4 — RBAC
- [x] Phase 4.5 — Access Control / Feature Blocking
- [x] Phase 5 — Plans / Features / Quotas
- [x] Phase 6 — Subscriptions
- [x] Phase 6.5 — Upgrade / Downgrade
- [x] Phase 7 — Billing / Payments
- [x] Phase 8 — Providers globaux
- [x] Phase 9 — Notifications / Usage
- [x] Phase 10 — Audit / Analytics
- [x] Phase 11 — CLI / Migrations / Tests
- [x] Phase 12 — Documentation finale

---

## Détail par fonctionnalité

| Module | Fonctionnalité | Statut | Fichiers | Tests | Notes |
|---|---|---|---|---|---|
| Fondation API | setup_saas_core | DONE | `app.py`, `routers.py` | `test_saas.py` | Initialisé et prêt |
| Fondation API | Routage /platform | DONE | `main.py` | `test_saas.py` | Routes Super Admin sécurisées |
| Fondation API | Routage /app | DONE | `main.py` | `test_saas.py` | Fusion des routes métier & admin |
| Fondation API | Supprimer /console | DONE | `main.py`, frontend | `test_saas.py` | Supprimé de toutes les couches |
| Fondation API | Supprimer les doublons `/app/roles/*` | DONE | `app.py` | `test_route_namespacing.py` | Une seule source de vérité pour les routes tenant |
| Auth & Identité | Inscription tenant | DONE | `tenant_app/auth.py` | `test_saas.py` | Initialise le tenant et le membre propriétaire |
| Auth & Identité | Connexion & JWT | DONE | `tenant_app/auth.py` | `test_saas.py` | Support des cookies HTTPOnly et en-tête Bearer |
| Auth & Identité | Session & Révocation | DONE | `tenant_app/auth.py` | `test_saas.py` | Invalidation des jetons de rafraîchissement |
| Multi-tenant | Isolation contextuelle | DONE | `tenant_app/auth.py` | `test_saas.py` | Résolution via X-Tenant-Slug header |
| Multi-tenant | Invitations membres | DONE | `tenant_app/invitations.py` | `test_saas.py` | Envoi d'invitation avec code d'acceptation |
| RBAC | Rôles système | DONE | `tenant_app/roles.py` | `test_roles_dynamic.py` | Rôles owner, admin, user prédéfinis |
| RBAC | Permissions métier | DONE | `tenant_app/roles.py` | `test_roles_dynamic.py` | Rôles customs éditables par tenant |
| Access Control | require_permission | DONE | `core/permissions.py` | `test_roles_dynamic.py` | Dépendance de restriction par code permission |
| Access Control | require_active_subscription | DONE | `core/permissions.py` | `test_access_control.py` | Bloquer si l'abonnement du tenant n'est pas actif |
| Access Control | require_feature_access | DONE | `core/permissions.py` | `test_access_control.py` | Vérifier la disponibilité de la feature dans le plan |
| Access Control | require_usage_limit | DONE | `core/permissions.py` | `test_access_control.py` | Bloquer en cas de dépassement de quota de plan |
| Plans & Abonnements | Quotas de plan | DONE | `tenant_app/billing.py` | `test_saas.py` | Limites max et décompte |
| Upgrade/Downgrade | core_subscription_changes | DONE | `models.py` | `test_billing_transitions.py` | Table d'historique des changements |
| Upgrade/Downgrade | Upgrade immédiat | DONE | `tenant_app/billing.py` | `test_billing_transitions.py` | Prorata et activation immédiate |
| Upgrade/Downgrade | Downgrade programmé | DONE | `tenant_app/billing.py`, `jobs/cleanup.py` | `test_billing_transitions.py` | Exécution à la fin de la période active |
| Providers Globaux | Super Admin uniquement | DONE | `platform/providers.py`, `platform/provider_logs.py` | `test_platform_routes.py` | Configuration cryptée inaccessible aux tenants |
| Payments Plateforme | Listing / retry / refund | DONE | `platform/payments.py` | `test_platform_routes.py` | Vue globale Super Admin sur paiements et factures |
| Analytics Plateforme | Dashboard / revenue / usage | DONE | `platform/analytics.py` | `test_platform_routes.py` | KPI globaux calculés depuis les données actuelles |
| Audit Logs Plateforme | Journal global | DONE | `platform/audit_logs.py` | `test_platform_routes.py` | Fusion platform + tenant avec pagination |
| Webhooks & Audit | Idempotence webhook | DONE | `platform/webhooks.py` | `test_webhooks.py` | Déduplication par signature / ID unique |
| API Keys | Clés API Machine | DONE | `tenant_app/api_keys.py` | `test_api_keys.py` | Authentification machine isolée par tenant |
| Documentation finale | Guide d'intégration et modules | DONE | `MODULE_DEVELOPMENT_GUIDE.md`, `API_ROUTES.md`, `BACKEND_IMPLEMENTATION_PLAN.md` | revue documentaire | Brancher le core dans chaque projet et implémenter un module métier |
