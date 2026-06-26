# BACKEND ARCHITECTURE

## Vue d'ensemble

Dymo SaaS Core est un backend modulaire FastAPI qui encapsule les fondations communes d'un produit SaaS B2B :

- auth ;
- tenants ;
- users ;
- RBAC ;
- plans ;
- subscriptions ;
- billing ;
- payments ;
- providers ;
- notifications ;
- usage ;
- audit logs ;
- analytics ;
- modules métiers.

## Couches logiques

### 1. API layer

- routes FastAPI ;
- dépendances ;
- schémas Pydantic ;
- handlers d'erreurs ;
- middlewares.

### 2. Application layer

- services métier ;
- orchestration des cas d'usage ;
- règles d'abonnement ;
- règles de permissions ;
- règles de quota.

### 3. Domain layer

- entités conceptuelles ;
- enums ;
- statuts ;
- règles de transition ;
- événements.

### 4. Infrastructure layer

- SQLAlchemy ;
- Alembic ;
- PostgreSQL ;
- Redis optionnel ;
- providers externes ;
- chiffrement ;
- jobs asynchrones.

## Découpage par domaines

- `auth`
- `tenants`
- `users`
- `roles`
- `permissions`
- `plans`
- `subscriptions`
- `billing`
- `payments`
- `providers`
- `notifications`
- `webhooks`
- `api_keys`
- `audit`
- `analytics`
- `usage`
- `settings`
- `security`
- `modules`
- `cli`

## Multi-tenant

Principe :

- chaque donnée métier appartient à un tenant ;
- toute requête est filtrée par contexte tenant ;
- les routes globales Super Admin sont séparées des routes tenant ;
- les modules métiers ne doivent jamais accéder aux données d'un autre tenant.

## Sécurité

- JWT court ;
- refresh token sécurisé ;
- cookies HTTPOnly ;
- CSRF si cookies actifs ;
- chiffrement des credentials ;
- validation stricte des entrées ;
- logs d'audit ;
- vérification des webhooks ;
- masquage des secrets.

## Extension

Le core doit exposer :

- `setup_saas_core(app)` ;
- `register_module(...)` ;
- helpers de tenant scope ;
- helpers de permissions ;
- helpers d'usage ;
- helpers d'événements.

