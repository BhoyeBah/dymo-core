# API ROUTES

Ce document liste l'intégralité des points d'accès (endpoints) de l'API REST de **Dymo SaaS Core**, structurés selon les deux espaces officiels : `/api/v1/platform` (Super Admin Dymo) et `/api/v1/app` (Espace Client).

---

## 1. Routes Plateforme (`/api/v1/platform`)

Ces points d'accès sont exclusivement réservés aux utilisateurs possédant le statut de Super Administrateur de la plateforme Dymo. La sécurité est assurée par la dépendance backend `require_super_admin()`.

*   **`GET /api/v1/platform/dashboard`** : Statistiques globales de la plateforme (MRR, ARR, nouveaux locataires).
*   **`GET /api/v1/platform/tenants`** : Lister l'ensemble des tenants enregistrés.
*   **`POST /api/v1/platform/tenants`** : Provisionner et créer manuellement un nouveau tenant.
*   **`GET /api/v1/platform/tenants/{tenant_id}`** : Consulter les détails d'un tenant.
*   **`PATCH /api/v1/platform/tenants/{tenant_id}`** : Mettre à jour les informations d'un tenant.
*   **`POST /api/v1/platform/tenants/{tenant_id}/suspend`** : Suspendre immédiatement l'accès d'un tenant.
*   **`POST /api/v1/platform/tenants/{tenant_id}/reactivate`** : Réactiver l'accès d'un tenant suspendu.
*   **`GET /api/v1/platform/plans`** : Lister les forfaits d'abonnements disponibles.
*   **`POST /api/v1/platform/plans`** : Créer un nouveau plan tarifaire (avec ses quotas et features).
*   **`PATCH /api/v1/platform/plans/{plan_id}`** : Mettre à jour les caractéristiques d'un plan.
*   **`DELETE /api/v1/platform/plans/{plan_id}`** : Supprimer logiquement un plan d'abonnement.
*   **`GET /api/v1/platform/subscriptions`** : Lister les abonnements actifs de tous les tenants.
*   **`GET /api/v1/platform/payments`** : Historique global de toutes les transactions financières de la plateforme.
*   **`GET /api/v1/platform/payments/{payment_id}`** : Consulter une transaction financière spécifique.
*   **`POST /api/v1/platform/payments/{payment_id}/retry`** : Relancer une transaction en échec.
*   **`POST /api/v1/platform/payments/{payment_id}/refund`** : Rembourser une transaction réussie.
*   **`GET /api/v1/platform/invoices`** : Lister les factures globales de la plateforme.
*   **`GET /api/v1/platform/invoices/{invoice_id}`** : Consulter une facture spécifique.
*   **`GET /api/v1/platform/providers`** : Lister les configurations techniques des providers tiers (SMTP, SMS, Passerelles de paiement).
*   **`POST /api/v1/platform/providers`** : Créer ou mettre à jour la configuration d'un provider tiers.
*   **`GET /api/v1/platform/providers/{provider_id}`** : Consulter une configuration provider masquée.
*   **`PATCH /api/v1/platform/providers/{provider_id}`** : Mettre à jour une configuration provider.
*   **`POST /api/v1/platform/providers/{provider_id}/test`** : Déclencher un appel de test pour valider les identifiants d'un provider.
*   **`POST /api/v1/platform/providers/{provider_id}/activate`** : Activer une configuration provider.
*   **`POST /api/v1/platform/providers/{provider_id}/deactivate`** : Désactiver une configuration provider.
*   **`GET /api/v1/platform/provider-logs`** : Consulter l'historique des requêtes et réponses vers les APIs de tiers.
*   **`GET /api/v1/platform/webhooks`** : Logs et configuration des webhooks plateforme (entrant/sortant).
*   **`GET /api/v1/platform/dashboard`** : Vue synthétique du cockpit Super Admin.
*   **`GET /api/v1/platform/analytics/overview`** : Données synthétiques de performance de la plateforme.
*   **`GET /api/v1/platform/analytics/revenue`** : Détail du chiffre d'affaires (MRR, ARR, churn).
*   **`GET /api/v1/platform/analytics/tenants`** : Statistiques d'acquisition et de rétention locataires.
*   **`GET /api/v1/platform/analytics/providers`** : Taux de réussite et latence par provider tiers.
*   **`GET /api/v1/platform/analytics/usage`** : Agrégats de consommation globaux.
*   **`GET /api/v1/platform/audit-logs`** : Journal d'audit complet de toutes les actions d'administration globales.
*   **`GET /api/v1/platform/settings`** : Configurations système transverses.

---

## 2. Routes Client / Métier (`/api/v1/app`)

Ces routes servent l'application de chaque locataire (Tenant). L'authentification y est obligatoire et le contexte d'isolation du locataire est injecté via le middleware d'analyse d'en-tête de requête (`X-Tenant-Slug`).

### Authentification & Profil (`/api/v1/app/auth`)
*   **`POST /api/v1/app/auth/register`** : Auto-inscription d'un nouveau tenant avec compte propriétaire.
*   **`POST /api/v1/app/auth/login`** : Connexion à l'espace de son organisation (retourne les JWT et injecte les cookies HTTPOnly).
*   **`POST /api/v1/app/auth/logout`** : Déconnexion et invalidation de la session courante.
*   **`POST /api/v1/app/auth/refresh`** : Rafraîchir un jeton d'accès expiré en utilisant le refresh token.
*   **`GET /api/v1/app/auth/me`** (ou `/api/v1/app/me`) : Obtenir les informations de l'utilisateur connecté et son profil membre.

### Gestion de l'Entreprise et Équipe
*   **`GET /api/v1/app/company`** : Récupérer les informations administratives de son organisation.
*   **`PATCH /api/v1/app/company`** : Modifier les informations de son organisation.
*   **`GET /api/v1/app/users`** : Lister les collaborateurs actifs de l'organisation.
*   **`GET /api/v1/app/invitations`** : Lister les invitations envoyées et en attente.
*   **`POST /api/v1/app/invitations`** : Inviter un nouveau collaborateur par email.
*   **`POST /api/v1/app/invitations/{id}/revoke`** : Révoquer une invitation en attente.

### Gouvernance & Rôles
*   **`GET /api/v1/app/roles`** : Lister les rôles disponibles (système et personnalisés) du tenant.
*   **`POST /api/v1/app/roles`** : Créer un rôle personnalisé.
*   **`GET /api/v1/app/roles/{id}`** : Récupérer les détails d'un rôle spécifique.
*   **`PATCH /api/v1/app/roles/{id}`** : Modifier un rôle personnalisé.
*   **`DELETE /api/v1/app/roles/{id}`** : Supprimer un rôle personnalisé.
*   **`POST /api/v1/app/roles/{id}/permissions`** : Associer des permissions à un rôle.
*   **`DELETE /api/v1/app/roles/{id}/permissions/{permission_id}`** : Retirer une permission d'un rôle.
*   **`GET /api/v1/app/permissions`** : Lister les codes de permissions fines disponibles.

### Facturation et Cycle de Vie (Upgrade / Downgrade)
*   **`GET /api/v1/app/subscription`** : Obtenir le statut actuel de l'abonnement du tenant.
*   **`POST /api/v1/app/subscription/upgrade`** : Lancer une procédure d'upgrade immédiat avec calcul de prorata.
*   **`POST /api/v1/app/subscription/downgrade`** : Programmer un downgrade pour la fin de la période active.
*   **`POST /api/v1/app/subscription/cancel-downgrade`** : Annuler un downgrade en attente de validation.
*   **`GET /api/v1/app/billing`** : Coordonnées de facturation et cartes de paiement enregistrées.
*   **`GET /api/v1/app/invoices`** : Récupérer l'historique des factures de son abonnement.
*   **`GET /api/v1/app/usage`** : Consulter les compteurs de consommation courante face aux quotas du plan.

### Intégration & Diagnostics
*   **`GET /api/v1/app/api-keys`** : Lister les clés API d'intégration machine créées.
*   **`POST /api/v1/app/api-keys`** : Générer une nouvelle clé API machine.
*   **`DELETE /api/v1/app/api-keys/{id}`** : Supprimer définitivement une clé API.
*   **`GET /api/v1/app/audit-logs`** : Consulter le journal d'audit restreint aux actions de ce tenant.
*   **`GET /api/v1/app/settings`** : Gérer les paramètres et préférences simples de l'organisation.

### Important
Les routes suivantes n'existent pas côté tenant et doivent retourner `404` :
*   `/api/v1/app/providers`
*   `/api/v1/console`
*   `/api/v1/tenant-console`
*   `/api/v1/tenant-app`
    
