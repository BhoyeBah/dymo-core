# DATABASE SCHEMA PLAN

Ce document présente la structure complète et détaillée de la base de données relationnelle pour **Dymo SaaS Core**. 

Toutes les tables métiers associées à un tenant spécifique possèdent un champ `tenant_id` indexé et des contraintes de clés étrangères pour garantir l'isolation logique multi-tenant. Le soft delete (`deleted_at`) est utilisé pour les entités sensibles afin d'éviter la perte de données accidentelle.

---

## Liste des 28 tables du Core

### 1. `core_tenants`
- **Objectif** : Gérer les entreprises/locataires (tenants) sur la plateforme.
- **Colonnes principales** : `id` (UUID, PK), `name` (VARCHAR), `slug` (VARCHAR, Unique), `status` (VARCHAR, ex: 'active', 'suspended'), `country` (VARCHAR), `currency` (VARCHAR), `created_at`, `updated_at`, `deleted_at`.
- **Relations** : Relation un-à-plusieurs avec `core_tenant_members` et `core_subscriptions`.
- **Index** : Index sur `slug`.
- **Contraintes** : `slug` unique non nul.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Oui.

### 2. `core_users`
- **Objectif** : Gérer l'identité des utilisateurs globaux.
- **Colonnes principales** : `id` (UUID, PK), `email` (VARCHAR, Unique), `password_hash` (VARCHAR), `first_name` (VARCHAR), `last_name` (VARCHAR), `is_super_admin` (BOOLEAN, default False), `status` (VARCHAR), `last_login_at` (TIMESTAMP), `created_at`, `updated_at`, `deleted_at`.
- **Relations** : Relation un-à-plusieurs avec `core_tenant_members` et `core_sessions`.
- **Index** : Index sur `email`.
- **Contraintes** : `email` unique non nul.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Oui.

### 3. `core_sessions`
- **Objectif** : Gérer les sessions d'authentification utilisateur actives.
- **Colonnes principales** : `id` (UUID, PK), `user_id` (UUID, FK `core_users.id`), `refresh_token` (VARCHAR, Unique), `user_agent` (VARCHAR), `ip_address` (VARCHAR), `expires_at` (TIMESTAMP), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_users`.
- **Index** : Index sur `refresh_token`, `user_id`.
- **Contraintes** : Clé étrangère vers `core_users` en cascade.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Non.

### 4. `core_tenant_members`
- **Objectif** : Associer un utilisateur global à un tenant avec son profil interne.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `user_id` (UUID, FK `core_users.id`), `is_owner` (BOOLEAN, default False), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_tenants` et `core_users`. Un-à-plusieurs avec `core_user_roles`.
- **Index** : Index composite (`tenant_id`, `user_id`).
- **Contraintes** : Unicité sur le couple (`tenant_id`, `user_id`).
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 5. `core_invitations`
- **Objectif** : Gérer le cycle des invitations envoyées aux collaborateurs potentiels.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `email` (VARCHAR), `token` (VARCHAR, Unique), `role_id` (UUID, FK `core_roles.id`), `status` (VARCHAR, ex: 'pending', 'accepted', 'revoked'), `expires_at` (TIMESTAMP), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_tenants` et `core_roles`.
- **Index** : Index sur `token`.
- **Contraintes** : Clé étrangère vers `core_tenants`, token unique.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 6. `core_roles`
- **Objectif** : Définir les rôles d'utilisateurs (système et personnalisés) par tenant.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`, nullable pour les rôles système), `name` (VARCHAR), `code` (VARCHAR), `description` (VARCHAR), `is_system` (BOOLEAN, default False), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_tenants`. Un-à-plusieurs avec `core_role_permissions` et `core_user_roles`.
- **Index** : Index sur `code`, `tenant_id`.
- **Contraintes** : Unicité sur (`tenant_id`, `code`).
- **Tenant ID** : Oui (nullable pour rôles globaux).
- **Soft Delete** : Non.

### 7. `core_permissions`
- **Objectif** : Répertoire complet des permissions fines existant dans le système (ex: `users.create`, `billing.view`).
- **Colonnes principales** : `id` (UUID, PK), `code` (VARCHAR, Unique), `name` (VARCHAR), `description` (VARCHAR), `module` (VARCHAR), `created_at`.
- **Relations** : Un-à-plusieurs avec `core_role_permissions`.
- **Index** : Index sur `code`.
- **Contraintes** : `code` unique.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Non.

### 8. `core_role_permissions`
- **Objectif** : Table d'association entre rôles et permissions fines.
- **Colonnes principales** : `role_id` (UUID, FK `core_roles.id`, PK), `permission_id` (UUID, FK `core_permissions.id`, PK), `created_at`.
- **Relations** : Jointure plusieurs-à-plusieurs entre `core_roles` et `core_permissions`.
- **Index** : Index sur `role_id`, `permission_id`.
- **Contraintes** : Clés étrangères correspondantes.
- **Tenant ID** : Non (hérité via le rôle).
- **Soft Delete** : Non.

### 9. `core_user_roles`
- **Objectif** : Associer un membre du tenant à un ou plusieurs rôles.
- **Colonnes principales** : `member_id` (UUID, FK `core_tenant_members.id`, PK), `role_id` (UUID, FK `core_roles.id`, PK), `created_at`.
- **Relations** : Jointure plusieurs-à-plusieurs entre `core_tenant_members` et `core_roles`.
- **Index** : Index sur `member_id`, `role_id`.
- **Contraintes** : Clés étrangères correspondantes.
- **Tenant ID** : Non (hérité via le membre).
- **Soft Delete** : Non.

### 10. `core_plans`
- **Objectif** : Définir les forfaits d'abonnement SaaS proposés aux tenants.
- **Colonnes principales** : `id` (UUID, PK), `name` (VARCHAR), `code` (VARCHAR, Unique), `price_monthly` (DECIMAL), `price_yearly` (DECIMAL), `currency` (VARCHAR), `trial_days` (INTEGER, default 0), `is_visible` (BOOLEAN, default True), `created_at`, `updated_at`.
- **Relations** : Un-à-plusieurs avec `core_plan_features` et `core_plan_quotas`.
- **Index** : Index sur `code`.
- **Contraintes** : `code` unique.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Oui.

### 11. `core_plan_features`
- **Objectif** : Associer des fonctionnalités déblocables (features) à un plan spécifique.
- **Colonnes principales** : `id` (UUID, PK), `plan_id` (UUID, FK `core_plans.id`), `feature_code` (VARCHAR), `is_enabled` (BOOLEAN, default True), `created_at`.
- **Relations** : Appartient à `core_plans`.
- **Index** : Index composite (`plan_id`, `feature_code`).
- **Contraintes** : Unicité sur (`plan_id`, `feature_code`).
- **Tenant ID** : Non.
- **Soft Delete** : Non.

### 12. `core_plan_quotas`
- **Objectif** : Spécifier les quotas limites d'usage pour chaque plan d'abonnement.
- **Colonnes principales** : `id` (UUID, PK), `plan_id` (UUID, FK `core_plans.id`), `resource_code` (VARCHAR), `max_limit` (INTEGER), `created_at`.
- **Relations** : Appartient à `core_plans`.
- **Index** : Index composite (`plan_id`, `resource_code`).
- **Contraintes** : Unicité sur (`plan_id`, `resource_code`).
- **Tenant ID** : Non.
- **Soft Delete** : Non.

### 13. `core_subscriptions`
- **Objectif** : Gérer l'abonnement en cours d'un tenant.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `plan_id` (UUID, FK `core_plans.id`), `status` (VARCHAR, ex: 'trialing', 'active', 'expired', 'suspended'), `billing_cycle` (VARCHAR, ex: 'monthly', 'yearly'), `starts_at` (TIMESTAMP), `ends_at` (TIMESTAMP), `trial_ends_at` (TIMESTAMP), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_tenants` et `core_plans`. Un-à-plusieurs avec `core_subscription_changes`.
- **Index** : Index sur `tenant_id`, `plan_id`.
- **Contraintes** : Unicité facultative ou logique de clé étrangère stricte.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 14. `core_subscription_changes`
- **Objectif** : Historiser et planifier les changements d'abonnement (Upgrades/Downgrades).
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `subscription_id` (UUID, FK `core_subscriptions.id`), `old_plan_id` (UUID, FK `core_plans.id`), `new_plan_id` (UUID, FK `core_plans.id`), `change_type` (VARCHAR, ex: 'upgrade', 'downgrade'), `status` (VARCHAR, ex: 'pending', 'applied', 'cancelled'), `effective_date` (TIMESTAMP), `prorated_amount` (DECIMAL), `payment_id` (UUID), `requested_by_user_id` (UUID, FK `core_users.id`), `applied_at` (TIMESTAMP), `cancelled_at` (TIMESTAMP), `metadata` (JSONB), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_tenants`, `core_subscriptions` et `core_plans`.
- **Index** : Index sur `tenant_id`, `subscription_id`, `status`.
- **Contraintes** : Clés étrangères correspondantes.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 15. `core_invoices`
- **Objectif** : Stocker les factures d'abonnement ou de services générées pour les tenants.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `number` (VARCHAR, Unique), `amount` (DECIMAL), `tax` (DECIMAL), `discount` (DECIMAL), `status` (VARCHAR, ex: 'draft', 'open', 'paid', 'uncollectible'), `due_date` (TIMESTAMP), `pdf_url` (VARCHAR), `created_at`, `updated_at`.
- **Relations** : Appartient à `core_tenants`. Un-à-plusieurs avec `core_payments`.
- **Index** : Index sur `number`, `tenant_id`.
- **Contraintes** : `number` unique non nul.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 16. `core_payments`
- **Objectif** : Enregistrer chaque transaction financière de paiement.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `invoice_id` (UUID, FK `core_invoices.id`), `amount` (DECIMAL), `currency` (VARCHAR), `provider` (VARCHAR), `provider_reference` (VARCHAR), `status` (VARCHAR, ex: 'pending', 'succeeded', 'failed', 'refunded'), `error_message` (VARCHAR), `created_at`, `updated_at`.
- **Relations** : Jointure avec `core_tenants` et `core_invoices`.
- **Index** : Index sur `provider_reference`, `tenant_id`.
- **Contraintes** : Clés étrangères correspondantes.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 17. `core_provider_configs`
- **Objectif** : Configurer les secrets d'accès des fournisseurs système tiers (SMTP, SMS, WhatsApp, paiement, stockage, webhook). Configurable uniquement par le Super Admin.
- **Colonnes principales** : `id` (UUID, PK), `provider_type` (VARCHAR), `provider_name` (VARCHAR), `environment` (VARCHAR), `encrypted_credentials` (VARCHAR, chiffré), `is_active` (BOOLEAN), `is_default` (BOOLEAN), `supported_countries` (JSON), `supported_currencies` (JSON), `last_test_status` (VARCHAR), `last_tested_at` (TIMESTAMP), `created_by_user_id` (UUID, FK `platform_admins.id`), `updated_by_user_id` (UUID, FK `platform_admins.id`), `created_at`, `updated_at`.
- **Relations** : Un-à-plusieurs avec `core_provider_logs`.
- **Index** : Index sur `provider_type`, `is_active`, `is_default`.
- **Contraintes** : Secrets jamais stockés en clair.
- **Tenant ID** : Non applicable (Global / Super Admin).
- **Soft Delete** : Non.

### 18. `core_provider_logs`
- **Objectif** : Enregistrer l'historique des requêtes et réponses vers les APIs des providers techniques.
- **Colonnes principales** : `id` (UUID, PK), `provider_config_id` (UUID, FK `core_provider_configs.id`), `provider_type` (VARCHAR), `provider_name` (VARCHAR), `operation` (VARCHAR), `status` (VARCHAR), `request_payload_masked` (JSON), `response_payload_masked` (JSON), `error_message` (VARCHAR), `duration_ms` (INTEGER), `created_at`.
- **Relations** : Appartient à `core_provider_configs`.
- **Index** : Index sur `provider_config_id`, `created_at`.
- **Contraintes** : La payload est toujours masquée avant persistence.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Non.

### 19. `core_notification_templates`
- **Objectif** : Templates globaux pour l'envoi de messages système (ex: bienvenue, rappel facture, code d'authentification).
- **Colonnes principales** : `id` (UUID, PK), `code` (VARCHAR, Unique), `channel` (VARCHAR, ex: 'email', 'sms', 'whatsapp'), `subject` (VARCHAR), `body` (TEXT), `created_at`, `updated_at`.
- **Relations** : Un-à-plusieurs avec `core_notifications`.
- **Index** : Index sur `code`.
- **Contraintes** : `code` unique.
- **Tenant ID** : Non applicable.
- **Soft Delete** : Non.

### 20. `core_notifications`
- **Objectif** : Tracer chaque notification expédiée à un utilisateur ou client de tenant.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `template_id` (UUID, FK `core_notification_templates.id`, nullable), `recipient` (VARCHAR), `channel` (VARCHAR), `subject` (VARCHAR), `body` (TEXT), `status` (VARCHAR, ex: 'pending', 'sent', 'failed'), `error_message` (VARCHAR), `created_at`.
- **Relations** : Jointure avec `core_tenants` et `core_notification_templates`.
- **Index** : Index sur `tenant_id`, `status`.
- **Contraintes** : Clés étrangères correspondantes.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 21. `core_webhook_events`
- **Objectif** : Gérer la déduplication et l'historique des événements de webhook reçus ou émis (outbox pattern).
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `event_type` (VARCHAR), `payload` (JSONB), `signature` (VARCHAR), `status` (VARCHAR, ex: 'pending', 'dispatched', 'failed'), `attempts` (INTEGER, default 0), `created_at`, `updated_at`.
- **Relations** : Jointure avec `core_tenants`.
- **Index** : Index sur `tenant_id`, `event_type`, `status`.
- **Contraintes** : Clé étrangère correspondante.
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 22. `core_api_keys`
- **Objectif** : Stocker les métadonnées et hashes des clés API d'intégration machine générées par le tenant.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `name` (VARCHAR), `key_hash` (VARCHAR, Unique), `prefix` (VARCHAR), `is_active` (BOOLEAN, default True), `expires_at` (TIMESTAMP), `created_at`, `updated_at`, `revoked_at` (TIMESTAMP).
- **Relations** : Appartient à `core_tenants`. Un-à-plusieurs avec `core_api_key_logs`.
- **Index** : Index sur `key_hash`, `tenant_id`.
- **Contraintes** : `key_hash` unique.
- **Tenant ID** : Oui.
- **Soft Delete** : Oui.

### 23. `core_api_key_logs`
- **Objectif** : Journaliser l'activité et l'utilisation de chaque clé API par les systèmes externes.
- **Colonnes principales** : `id` (UUID, PK), `api_key_id` (UUID, FK `core_api_keys.id`), `request_path` (VARCHAR), `request_method` (VARCHAR), `ip_address` (VARCHAR), `status_code` (INTEGER), `created_at`.
- **Relations** : Appartient à `core_api_keys`.
- **Index** : Index sur `api_key_id`, `created_at`.
- **Contraintes** : Clé étrangère correspondante.
- **Tenant ID** : Non (hérité via la clé API).
- **Soft Delete** : Non.

### 24. `core_audit_logs`
- **Objectif** : Registre d'audit pour assurer la traçabilité des modifications sensibles.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`, nullable pour actions plateforme), `user_id` (UUID, FK `core_users.id`, nullable), `action` (VARCHAR), `resource` (VARCHAR), `resource_id` (VARCHAR), `old_values` (JSONB), `new_values` (JSONB), `ip_address` (VARCHAR), `user_agent` (VARCHAR), `created_at`.
- **Relations** : Jointure avec `core_tenants` et `core_users`.
- **Index** : Index sur `tenant_id`, `user_id`, `action`.
- **Contraintes** : Clés étrangères correspondantes.
- **Tenant ID** : Oui (nullable).
- **Soft Delete** : Non.

### 25. `core_usage_counters`
- **Objectif** : Suivre l'utilisation des ressources et volumes par tenant pour la validation des limites de plan.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `resource_code` (VARCHAR), `period_start` (TIMESTAMP), `period_end` (TIMESTAMP), `current_usage` (INTEGER, default 0), `created_at`, `updated_at`.
- **Relations** : Jointure avec `core_tenants`.
- **Index** : Index composite (`tenant_id`, `resource_code`, `period_start`).
- **Contraintes** : Unicité sur (`tenant_id`, `resource_code`, `period_start`).
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 26. `core_settings`
- **Objectif** : Configurations clés/valeurs spécifiques au fonctionnement interne de chaque tenant.
- **Colonnes principales** : `id` (UUID, PK), `tenant_id` (UUID, FK `core_tenants.id`), `key` (VARCHAR), `value` (VARCHAR, chiffré si sensible), `is_encrypted` (BOOLEAN, default False), `created_at`, `updated_at`.
- **Relations** : Jointure avec `core_tenants`.
- **Index** : Index composite (`tenant_id`, `key`).
- **Contraintes** : Unicité sur (`tenant_id`, `key`).
- **Tenant ID** : Oui.
- **Soft Delete** : Non.

### 27. `core_password_reset_tokens`
- **Objectif** : Gérer le cycle de vie des demandes de réinitialisation de mot de passe.
- **Colonnes principales** : `id` (UUID, PK), `user_id` (UUID, FK `core_users.id`), `token` (VARCHAR, Unique), `is_used` (BOOLEAN, default False), `expires_at` (TIMESTAMP), `created_at`.
- **Relations** : Appartient à `core_users`.
- **Index** : Index sur `token`.
- **Contraintes** : Token unique.
- **Tenant ID** : Non.
- **Soft Delete** : Non.

### 28. `core_email_verification_tokens`
- **Objectif** : Gérer le cycle de vie de la vérification de l'adresse email des utilisateurs.
- **Colonnes principales** : `id` (UUID, PK), `user_id` (UUID, FK `core_users.id`), `token` (VARCHAR, Unique), `is_used` (BOOLEAN, default False), `expires_at` (TIMESTAMP), `created_at`.
- **Relations** : Appartient à `core_users`.
- **Index** : Index sur `token`.
- **Contraintes** : Token unique.
- **Tenant ID** : Non.
- **Soft Delete** : Non.
