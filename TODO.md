# Cahier de charge complet — Dymo SaaS Core

## Starter kit SaaS B2B multi-tenant pour le marché africain

---

## 1. Présentation du projet

**Dymo SaaS Core** est un socle SaaS B2B interne, réutilisable et avancé, destiné à accélérer la création de nouveaux SaaS professionnels.

L’objectif est de créer une base commune installable dans chaque nouveau projet afin de ne plus recoder à chaque fois :

* l’authentification ;
* la gestion des entreprises clientes ;
* le multi-tenant ;
* les utilisateurs ;
* les rôles ;
* les permissions ;
* les abonnements ;
* les paiements ;
* les plans ;
* les upgrades et downgrades ;
* les factures d’abonnement ;
* les providers SMS, WhatsApp, Email et paiement ;
* les logs ;
* les statistiques business ;
* la sécurité ;
* les webhooks ;
* les API keys ;
* les modules communs.

Le core doit servir de base pour créer rapidement plusieurs SaaS métiers :

* SaaS de gestion immobilière ;
* SaaS de facturation ;
* SaaS de gestion de colis ;
* SaaS de caisse ;
* SaaS restaurant ;
* SaaS pharmacie ;
* SaaS RH ;
* SaaS école ;
* SaaS logistique ;
* SaaS de gestion commerciale.

Le principe est simple :

```txt
Dymo SaaS Core = moteur commun
Nouveau SaaS = modules métiers uniquement
```

---

## 2. Objectif principal

Le projet doit permettre de lancer un nouveau SaaS rapidement en installant le core backend :

```bash
pip install dymo-saas-core
```

Puis dans une application FastAPI :

```python
from fastapi import FastAPI
from dymo_saas_core import setup_saas_core

app = FastAPI()

setup_saas_core(app)
```

Une fois installé, le core doit fournir automatiquement :

```txt
/api/auth
/api/tenants
/api/users
/api/roles
/api/permissions
/api/plans
/api/subscriptions
/api/billing
/api/payments
/api/providers
/api/notifications
/api/audit-logs
/api/webhooks
/api/settings
/api/analytics
/api/api-keys
```

Ensuite, chaque nouveau SaaS ajoute uniquement ses modules métiers.

Exemple pour un SaaS immobilier :

```txt
Modules déjà fournis par le core :
- Authentification
- Tenants
- Utilisateurs
- Permissions
- Abonnements
- Paiements
- Facturation SaaS
- Notifications
- Providers
- Dashboard business

Modules métiers à développer :
- Biens immobiliers
- Propriétaires
- Locataires
- Contrats de bail
- Loyers
- Quittances
- Maintenance
```

---

## 3. Clarification importante : qui est le tenant ?

Dans cette architecture, le **tenant** est le client B2B qui utilise le SaaS.

Exemple pour un SaaS immobilier :

```txt
Toi / Dymo = Propriétaire de la plateforme / Super Admin

Tenant 1 = Agence immobilière Dakar Immo
Tenant 2 = Cabinet Alpha Immobilier
Tenant 3 = Résidence Teranga Gestion
```

Exemple pour un SaaS de facturation :

```txt
Toi / Dymo = Propriétaire de la plateforme

Tenant 1 = Boutique A
Tenant 2 = PME B
Tenant 3 = Freelance C
```

Le tenant est donc une entreprise cliente.

Il ne configure pas les providers techniques.

---

## 4. Règle fondamentale du projet

Le client final ne configure aucun provider technique.

Toute la configuration sensible doit être gérée uniquement par le **Super Admin Dymo**.

Le client utilise simplement les fonctionnalités activées dans son plan.

### Ce que le Super Admin Dymo gère

Le Super Admin gère :

* DexPay ;
* Stripe ;
* Wave ;
* Orange Money ;
* Free Money ;
* PayDunya ;
* CinetPay ;
* Flutterwave ;
* Twilio ;
* Telnyx ;
* Meta WhatsApp Cloud API ;
* Brevo ;
* SMTP ;
* SendGrid ;
* Mailgun ;
* Resend ;
* les webhooks ;
* les clés API ;
* les tokens ;
* les secrets ;
* les templates globaux ;
* les frais ;
* les plans ;
* les abonnements ;
* les factures ;
* les paiements ;
* les règles d’usage.

### Ce que le tenant peut gérer

Le tenant peut seulement gérer :

* son profil entreprise ;
* son logo ;
* ses utilisateurs ;
* ses rôles internes ;
* ses permissions internes ;
* ses données métiers ;
* son abonnement ;
* ses factures ;
* son usage SMS / WhatsApp / Email ;
* ses préférences simples ;
* ses templates personnalisables si le plan le permet.

Le tenant ne doit jamais voir ni modifier :

* les clés DexPay ;
* les clés Twilio ;
* les clés WhatsApp ;
* les clés SMTP ;
* les secrets webhook ;
* les tokens API ;
* les paramètres techniques des providers.

---

## 5. Contexte africain à prendre en compte

Le projet doit être pensé pour le marché africain, notamment :

* Sénégal ;
* Guinée ;
* Côte d’Ivoire ;
* Mali ;
* Burkina Faso ;
* Cameroun ;
* Bénin ;
* Togo ;
* Maroc ;
* Afrique francophone en général.

Les réalités locales à intégrer :

* paiement Mobile Money très important ;
* WhatsApp comme canal principal de communication ;
* SMS encore indispensable ;
* connexion internet parfois instable ;
* utilisateurs parfois peu techniques ;
* besoin d’interfaces simples ;
* besoin de reçus PDF ;
* besoin de relances automatiques ;
* besoin de paiements en FCFA, GNF, MAD, etc. ;
* besoin de support multidevise ;
* besoin de facturation mensuelle simple ;
* besoin de plans accessibles.

Les providers prioritaires sont :

```txt
Paiement :
- DexPay
- Wave
- Orange Money
- Free Money
- PayDunya
- CinetPay
- Flutterwave
- Stripe pour carte bancaire

SMS :
- Twilio
- Telnyx
- Orange SMS
- Infobip
- Provider HTTP personnalisé

WhatsApp :
- Meta WhatsApp Cloud API
- Twilio WhatsApp
- 360Dialog
- Provider HTTP personnalisé

Email :
- SMTP
- Brevo
- Mailgun
- Resend
- SendGrid
```

---

## 6. Stack technique validée

### Backend

```txt
- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- JWT
- Cookies HTTPOnly
- Redis optionnel
- Celery ou RQ optionnel
- Docker
```

### Frontend Admin

```txt
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod
- Recharts
- Zustand ou store léger
```

### Infrastructure

```txt
- Docker
- Docker Compose
- Coolify compatible
- PostgreSQL
- Redis optionnel
- Cloudflare R2 ou S3 optionnel
- Variables d’environnement
- HTTPS en production
```

---

## 7. Architecture générale du projet

```txt
dymo-saas-core/
├── backend/
│   ├── dymo_saas_core/
│   │   ├── auth/
│   │   ├── tenants/
│   │   ├── users/
│   │   ├── roles/
│   │   ├── permissions/
│   │   ├── plans/
│   │   ├── subscriptions/
│   │   ├── billing/
│   │   ├── payments/
│   │   ├── providers/
│   │   ├── notifications/
│   │   ├── webhooks/
│   │   ├── api_keys/
│   │   ├── audit/
│   │   ├── analytics/
│   │   ├── usage/
│   │   ├── settings/
│   │   ├── security/
│   │   ├── modules/
│   │   └── cli/
│   │
│   ├── migrations/
│   ├── tests/
│   └── pyproject.toml
│
├── frontend/
│   ├── apps/admin/
│   ├── packages/ui/
│   ├── packages/sdk/
│   └── package.json
│
├── examples/
│   ├── real-estate-saas/
│   ├── invoice-saas/
│   ├── logistics-saas/
│   └── cashier-saas/
│
└── docs/
    ├── installation.md
    ├── architecture.md
    ├── billing.md
    ├── providers.md
    ├── permissions.md
    ├── upgrade-downgrade.md
    └── security.md
```

---

## 8. Types d’interfaces

Le projet doit contenir deux grands espaces.

---

# 8.1 Interface Super Admin Dymo

C’est l’interface propriétaire.

Elle est réservée à toi et à ton équipe.

Elle permet de gérer toute la plateforme.

### Dashboard global

Le dashboard Super Admin doit afficher :

* MRR ;
* ARR ;
* revenus du mois ;
* revenus de l’année ;
* nombre total de tenants ;
* tenants actifs ;
* tenants suspendus ;
* tenants en essai gratuit ;
* tenants payants ;
* tenants expirés ;
* abonnements actifs ;
* abonnements annulés ;
* paiements réussis ;
* paiements échoués ;
* chiffre d’affaires par plan ;
* chiffre d’affaires par pays ;
* chiffre d’affaires par provider ;
* usage SMS ;
* usage WhatsApp ;
* usage Email ;
* consommation par tenant ;
* derniers paiements ;
* dernières inscriptions ;
* alertes système ;
* webhooks échoués ;
* providers en erreur.

### Pages Super Admin

```txt
/dashboard
/tenants
/tenants/:id
/users
/plans
/subscriptions
/billing
/payments
/providers
/provider-logs
/webhooks
/notifications
/notification-templates
/audit-logs
/analytics
/settings
/system-health
/api-keys
```

### Actions Super Admin

Le Super Admin doit pouvoir :

* créer un tenant ;
* modifier un tenant ;
* suspendre un tenant ;
* réactiver un tenant ;
* supprimer un tenant ;
* voir les utilisateurs d’un tenant ;
* modifier le plan d’un tenant ;
* forcer un upgrade ;
* forcer un downgrade ;
* offrir une période gratuite ;
* appliquer une remise ;
* annuler un abonnement ;
* voir les factures ;
* voir les paiements ;
* relancer un paiement ;
* configurer les providers ;
* tester les providers ;
* voir les logs providers ;
* gérer les templates SMS ;
* gérer les templates WhatsApp ;
* gérer les templates Email ;
* gérer les webhooks ;
* voir les erreurs ;
* consulter les audit logs.

---

# 8.2 Interface Tenant Admin

C’est l’interface du client final.

Elle doit rester simple.

Le tenant ne configure pas les providers.

Il utilise uniquement les fonctionnalités disponibles selon son plan.

### Pages Tenant Admin

```txt
/dashboard
/company
/team
/roles
/permissions
/subscription
/billing
/invoices
/usage
/settings
/audit-logs
```

### Le tenant peut voir

* son entreprise ;
* son équipe ;
* ses rôles ;
* ses permissions ;
* son plan actuel ;
* son abonnement ;
* ses factures ;
* ses paiements ;
* sa consommation ;
* son usage SMS ;
* son usage WhatsApp ;
* son usage Email ;
* ses limites ;
* ses modules actifs.

### Le tenant ne peut pas voir

* les clés DexPay ;
* les clés Twilio ;
* les tokens WhatsApp ;
* les clés SMTP ;
* les secrets ;
* les paramètres providers ;
* les webhooks globaux ;
* les logs techniques globaux ;
* les autres tenants.

---

## 9. Authentification

Le core doit gérer :

* inscription ;
* connexion ;
* déconnexion ;
* refresh token ;
* mot de passe oublié ;
* réinitialisation mot de passe ;
* vérification email ;
* changement de mot de passe ;
* changement d’email ;
* gestion des sessions ;
* révocation de session.

### Auth initiale

```txt
- Email + mot de passe
- JWT access token
- Refresh token
- Cookies HTTPOnly
```

### Évolutions possibles

```txt
- Google OAuth
- Magic link
- 2FA
- Authenticator app
```

---

## 10. Multi-tenant

Chaque client est isolé dans son propre espace.

Chaque table métier doit contenir :

```txt
tenant_id
```

Le core doit empêcher tout accès croisé entre tenants.

Exemple :

```txt
Tenant A ne doit jamais voir les données du Tenant B.
```

Le core doit fournir :

```python
get_current_tenant()
require_tenant()
tenant_scoped_query()
require_permission()
```

---

## 11. Gestion des utilisateurs

Chaque tenant peut gérer ses utilisateurs internes.

Fonctionnalités :

* inviter un utilisateur ;
* accepter une invitation ;
* refuser une invitation ;
* désactiver un utilisateur ;
* réactiver un utilisateur ;
* supprimer un utilisateur du tenant ;
* attribuer un rôle ;
* modifier les permissions ;
* voir la dernière connexion ;
* voir les actions récentes.

### Statuts utilisateur

```txt
active
inactive
invited
suspended
deleted
```

---

## 12. Rôles et permissions

Le core doit intégrer un système RBAC avancé.

### Rôles système

```txt
Super Admin Dymo
Support Dymo
Finance Dymo
Tenant Owner
Tenant Admin
Manager
Agent
Viewer
```

### Permissions globales

```txt
tenants.read
tenants.create
tenants.update
tenants.suspend
tenants.delete

users.read
users.create
users.update
users.delete
users.invite

roles.read
roles.create
roles.update
roles.delete

permissions.read
permissions.assign

plans.read
plans.create
plans.update
plans.delete

subscriptions.read
subscriptions.manage
subscriptions.upgrade
subscriptions.downgrade
subscriptions.cancel

billing.read
billing.manage

payments.read
payments.refund
payments.retry

providers.read
providers.create
providers.update
providers.delete
providers.test

notifications.read
notifications.send
notifications.templates.manage

webhooks.read
webhooks.retry

analytics.read
audit_logs.read
settings.manage
api_keys.manage
```

### Permissions métiers extensibles

Chaque SaaS doit pouvoir déclarer ses propres permissions.

Exemple SaaS immobilier :

```python
register_permissions([
    "properties.read",
    "properties.create",
    "properties.update",
    "properties.delete",
    "owners.read",
    "tenants_real_estate.read",
    "leases.create",
    "rents.collect",
    "receipts.generate",
])
```

---

## 13. Plans d’abonnement

Le Super Admin doit pouvoir créer et gérer tous les plans.

Exemples :

```txt
Free
Starter
Pro
Business
Enterprise
```

Chaque plan doit avoir :

* nom ;
* description ;
* prix mensuel ;
* prix annuel ;
* devise ;
* période d’essai ;
* fonctionnalités incluses ;
* limites d’usage ;
* statut actif ou inactif ;
* visibilité publique ou privée ;
* ordre d’affichage.

### Exemples de limites

```txt
- Nombre maximum d’utilisateurs
- Nombre maximum de clients
- Nombre maximum de documents
- Nombre maximum de factures
- Nombre maximum de biens immobiliers
- Nombre maximum de colis
- Nombre maximum de boutiques
- Nombre maximum de SMS par mois
- Nombre maximum de WhatsApp par mois
- Nombre maximum d’emails par mois
- Accès API
- Export PDF
- Support prioritaire
- White label
```

---

## 14. Abonnements

Chaque tenant doit avoir un abonnement.

### Statuts

```txt
trialing
active
past_due
paused
cancelled
expired
suspended
pending_upgrade
pending_downgrade
```

### Données abonnement

* tenant ;
* plan actuel ;
* cycle mensuel ou annuel ;
* date de début ;
* date de fin de période ;
* date de prochain paiement ;
* montant ;
* devise ;
* statut ;
* renouvellement automatique ;
* période d’essai ;
* historique des changements.

---

## 15. Upgrade et downgrade des plans

Le core doit gérer complètement les changements de plan.

---

# 15.1 Upgrade

Un upgrade signifie passer à un plan supérieur.

Exemples :

```txt
Free → Starter
Starter → Pro
Pro → Business
Mensuel → Annuel
```

### Règle

L’upgrade doit être immédiat après paiement réussi.

Processus :

1. Le tenant choisit un plan supérieur.
2. Le système calcule le montant à payer.
3. Le système calcule le prorata si nécessaire.
4. Le paiement est créé via le provider configuré par Dymo.
5. Le tenant paie via Mobile Money, carte ou autre méthode.
6. Le webhook confirme le paiement.
7. Le nouveau plan devient actif immédiatement.
8. Les nouvelles limites sont appliquées.
9. Une facture est générée.
10. Une notification est envoyée.
11. L’action est enregistrée dans les audit logs.

### Exemple de prorata

```txt
Plan Starter : 10 000 FCFA/mois
Plan Pro : 25 000 FCFA/mois
Il reste 15 jours dans le mois
Différence : 15 000 FCFA
Montant proratisé : 7 500 FCFA
```

---

# 15.2 Downgrade

Un downgrade signifie passer à un plan inférieur.

Exemples :

```txt
Business → Pro
Pro → Starter
Annuel → Mensuel
```

### Règle recommandée

Le downgrade est programmé à la fin de la période déjà payée.

Exemple :

```txt
Le tenant est sur Pro jusqu’au 30 juin.
Il demande Starter le 15 juin.
Il garde Pro jusqu’au 30 juin.
Starter commence le 1er juillet.
```

### Statut

```txt
pending_downgrade
```

L’interface doit afficher :

```txt
Votre plan passera à Starter le 1er juillet.
```

Le tenant doit pouvoir annuler le downgrade avant la date prévue.

---

# 15.3 Downgrade forcé par Super Admin

Le Super Admin peut forcer un downgrade immédiat.

Avant cela, le système doit vérifier les quotas.

Exemple :

```txt
Plan Pro : 300 biens
Plan Starter : 50 biens
Le tenant possède 180 biens
```

Options possibles :

```txt
- Bloquer le downgrade
- Autoriser mais bloquer les nouvelles créations
- Autoriser seulement par décision Super Admin
```

---

## 16. Billing

Le module billing doit gérer :

* factures d’abonnement ;
* reçus ;
* paiements ;
* paiements échoués ;
* relances ;
* coupons ;
* remises ;
* taxes optionnelles ;
* historique de facturation.

### Statuts facture

```txt
draft
issued
paid
failed
void
refunded
overdue
```

### Facture

Une facture doit contenir :

* numéro ;
* tenant ;
* plan ;
* période ;
* montant ;
* remise ;
* taxes ;
* total ;
* devise ;
* statut ;
* date d’émission ;
* date d’échéance ;
* date de paiement ;
* provider utilisé ;
* référence paiement.

---

## 17. Paiements

Le core doit gérer les paiements d’abonnement.

Les paiements d’abonnement vont vers le compte Dymo.

Le tenant ne configure pas de compte paiement.

### Providers prioritaires

```txt
- DexPay
- Wave
- Orange Money
- Free Money
- PayDunya
- CinetPay
- Flutterwave
- Stripe
```

### Statuts paiement

```txt
pending
processing
successful
failed
cancelled
refunded
expired
```

### Webhooks

Le core doit :

* recevoir les webhooks ;
* vérifier la signature ;
* identifier le paiement ;
* mettre à jour le statut ;
* appliquer l’abonnement ;
* générer la facture ;
* envoyer la notification ;
* logger l’événement ;
* éviter les doublons.

---

## 18. Providers globaux

Tous les providers sont configurés par le Super Admin Dymo.

Il n’y a pas de configuration provider côté tenant.

### Page Super Admin

```txt
/settings/providers
```

### Types de providers

```txt
Paiement
SMS
WhatsApp
Email
Stockage
Webhook externe
```

---

# 18.1 Providers paiement

À gérer :

```txt
- DexPay
- Stripe
- Wave
- Orange Money
- Free Money
- PayDunya
- CinetPay
- Flutterwave
- Custom HTTP Provider
```

Champs :

* nom du provider ;
* mode sandbox / production ;
* clé publique ;
* clé secrète ;
* webhook secret ;
* URL webhook ;
* pays supportés ;
* devises supportées ;
* frais ;
* client paie les frais oui/non ;
* provider actif oui/non ;
* provider par défaut oui/non.

Actions :

* activer ;
* désactiver ;
* modifier ;
* tester la connexion ;
* voir les paiements ;
* voir les erreurs ;
* voir les webhooks.

---

# 18.2 Providers SMS

À gérer :

```txt
- Twilio
- Telnyx
- Orange SMS
- Infobip
- Custom HTTP Provider
```

Champs :

* API key ;
* API secret ;
* sender ID ;
* numéro expéditeur ;
* pays autorisés ;
* coût estimé ;
* URL API ;
* mode test / production.

Actions :

* envoyer un SMS test ;
* voir les logs ;
* voir les erreurs ;
* activer ;
* désactiver.

---

# 18.3 Providers WhatsApp

À gérer :

```txt
- Meta WhatsApp Cloud API
- Twilio WhatsApp
- 360Dialog
- Custom HTTP Provider
```

Champs :

* access token ;
* phone number ID ;
* business account ID ;
* webhook verify token ;
* templates WhatsApp ;
* langue par défaut ;
* mode test / production.

Actions :

* tester l’envoi WhatsApp ;
* synchroniser les templates ;
* voir les messages envoyés ;
* voir les erreurs.

---

# 18.4 Providers Email

À gérer :

```txt
- SMTP
- Brevo
- Mailgun
- Resend
- SendGrid
- Amazon SES
```

Champs :

* host ;
* port ;
* username ;
* password ;
* from email ;
* from name ;
* domaine d’envoi ;
* SSL/TLS.

Actions :

* envoyer un email test ;
* voir les logs ;
* activer ;
* désactiver.

---

## 19. Sécurité des providers

Les credentials doivent être protégés.

Obligations :

* chiffrer les clés en base ;
* masquer les clés dans l’interface ;
* ne jamais logger les secrets ;
* permettre la rotation des clés ;
* historiser les changements ;
* limiter l’accès aux admins autorisés.

Exemple affichage :

```txt
sk_live_************************8F2A
```

---

## 20. Notifications

Le core doit gérer les notifications globales.

Canaux :

```txt
- SMS
- WhatsApp
- Email
- Webhook
```

Les notifications utilisent toujours les providers configurés par Dymo.

### Templates

Le Super Admin peut gérer les templates globaux :

* bienvenue ;
* vérification email ;
* mot de passe oublié ;
* paiement réussi ;
* paiement échoué ;
* abonnement expiré ;
* upgrade confirmé ;
* downgrade programmé ;
* facture disponible ;
* relance paiement.

Variables :

```txt
{{tenant_name}}
{{user_name}}
{{plan_name}}
{{amount}}
{{currency}}
{{payment_link}}
{{invoice_number}}
{{due_date}}
```

---

## 21. Usage et quotas

Le core doit suivre la consommation de chaque tenant.

Exemples :

* nombre d’utilisateurs ;
* nombre de factures ;
* nombre de biens ;
* nombre de colis ;
* nombre de SMS envoyés ;
* nombre de WhatsApp envoyés ;
* nombre d’emails envoyés ;
* nombre d’appels API ;
* stockage utilisé.

Le core doit fournir :

```python
check_feature_access(tenant_id, "whatsapp_notifications")
check_usage_limit(tenant_id, "sms_sent")
increment_usage(tenant_id, "sms_sent")
```

---

## 22. API Keys

Chaque tenant peut créer des API keys uniquement si son plan l’autorise.

Fonctionnalités :

* créer une API key ;
* nommer la clé ;
* définir une expiration ;
* définir des permissions ;
* révoquer la clé ;
* voir la dernière utilisation ;
* voir les logs.

Le Super Admin peut voir et révoquer toutes les clés.

---

## 23. Audit logs

Le core doit enregistrer les actions sensibles.

Exemples :

* connexion ;
* échec connexion ;
* création tenant ;
* suspension tenant ;
* changement de plan ;
* upgrade ;
* downgrade ;
* paiement réussi ;
* paiement échoué ;
* modification provider ;
* test provider ;
* webhook reçu ;
* webhook échoué ;
* utilisateur invité ;
* rôle modifié ;
* permission modifiée ;
* clé API créée.

Chaque log doit contenir :

* tenant ;
* utilisateur ;
* action ;
* ressource ;
* IP ;
* user agent ;
* date ;
* ancienne valeur ;
* nouvelle valeur.

---

## 24. Analytics SaaS

Le Super Admin doit voir les indicateurs business.

### KPIs

```txt
MRR
ARR
ARPU
Churn rate
LTV estimée
Tenants actifs
Tenants payants
Tenants en essai
Taux conversion essai → payant
Paiements réussis
Paiements échoués
Revenus par provider
Revenus par pays
Revenus par plan
Revenus par mois
Usage SMS
Usage WhatsApp
Usage Email
```

### Graphiques

* évolution MRR ;
* évolution ARR ;
* revenus mensuels ;
* nouveaux tenants ;
* churn ;
* paiements par provider ;
* revenus par pays ;
* consommation SMS/WhatsApp/Email.

---

## 25. Système de modules métiers

Le core doit permettre d’ajouter des modules métiers sans modifier son cœur.

Exemple :

```python
register_module(
    name="real_estate",
    permissions=[
        "properties.read",
        "properties.create",
        "leases.read",
        "rents.collect",
    ],
    quotas=[
        "properties",
        "leases",
        "documents",
    ],
)
```

Un module métier doit pouvoir enregistrer :

* routes ;
* permissions ;
* menus ;
* quotas ;
* événements ;
* tâches planifiées ;
* webhooks internes.

---

## 26. CLI

Le core doit fournir une CLI.

Commandes :

```bash
dymo-saas init my-saas
dymo-saas migrate
dymo-saas seed
dymo-saas create-super-admin
dymo-saas add-module real_estate
dymo-saas list-modules
dymo-saas check-config
```

---

## 27. Migrations Alembic

Le core doit fournir ses propres migrations.

Tables principales :

```txt
core_tenants
core_users
core_tenant_members
core_roles
core_permissions
core_role_permissions
core_user_roles
core_plans
core_plan_features
core_subscriptions
core_subscription_changes
core_invoices
core_payments
core_provider_configs
core_provider_logs
core_notification_templates
core_notifications
core_webhook_events
core_api_keys
core_audit_logs
core_usage_counters
core_settings
```

Commande :

```bash
alembic upgrade head
```

Ou :

```bash
dymo-saas migrate
```

---

## 28. Sécurité globale

Le core doit respecter les bonnes pratiques suivantes :

* hashage sécurisé des mots de passe ;
* JWT avec expiration courte ;
* refresh token sécurisé ;
* cookies HTTPOnly ;
* CORS configurable ;
* rate limiting ;
* protection CSRF si cookies ;
* chiffrement des credentials ;
* isolation stricte tenant ;
* protection contre injection SQL ;
* validation stricte Pydantic ;
* masquage des secrets ;
* logs d’audit ;
* contrôle des permissions ;
* vérification des webhooks.

Variables importantes :

```env
APP_ENV=production
DATABASE_URL=
REDIS_URL=
SECRET_KEY=
ENCRYPTION_KEY=
COOKIE_SECURE=true
CORS_ORIGINS=
```

En développement HTTP :

```env
COOKIE_SECURE=false
```

En production HTTPS :

```env
COOKIE_SECURE=true
```

---

## 29. Gestion des erreurs

Format standard :

```json
{
  "success": false,
  "error": {
    "code": "SUBSCRIPTION_LIMIT_REACHED",
    "message": "Votre plan actuel ne permet pas cette action.",
    "details": {
      "limit": 5,
      "current": 5,
      "upgrade_required": true
    }
  }
}
```

Codes importants :

```txt
AUTH_INVALID_CREDENTIALS
AUTH_TOKEN_EXPIRED
TENANT_NOT_FOUND
TENANT_SUSPENDED
PERMISSION_DENIED
SUBSCRIPTION_EXPIRED
SUBSCRIPTION_LIMIT_REACHED
PROVIDER_NOT_CONFIGURED
PAYMENT_FAILED
WEBHOOK_INVALID_SIGNATURE
USAGE_LIMIT_REACHED
```

---

## 30. Tests

### Backend

Tests obligatoires :

* auth ;
* tenants ;
* isolation tenant ;
* users ;
* roles ;
* permissions ;
* plans ;
* subscriptions ;
* upgrade ;
* downgrade ;
* billing ;
* payments ;
* providers ;
* notifications ;
* webhooks ;
* audit logs ;
* quotas.

### Frontend

Tests importants :

* connexion ;
* dashboard ;
* gestion tenants ;
* gestion plans ;
* upgrade ;
* downgrade ;
* providers Super Admin ;
* billing ;
* utilisateurs ;
* permissions ;
* logs.

---

## 31. Critères d’acceptation

Le projet est validé lorsque :

* le core peut être installé avec `pip install` ;
* FastAPI expose automatiquement les routes core ;
* PostgreSQL fonctionne avec les migrations Alembic ;
* le multi-tenant est strict ;
* le Super Admin peut tout gérer ;
* le tenant ne peut pas configurer les providers ;
* les providers sont configurables uniquement côté Super Admin ;
* DexPay peut être configuré côté Super Admin ;
* Twilio peut être configuré côté Super Admin ;
* WhatsApp peut être configuré côté Super Admin ;
* SMTP ou Brevo peut être configuré côté Super Admin ;
* les secrets sont chiffrés ;
* les plans peuvent être créés ;
* les abonnements fonctionnent ;
* l’upgrade fonctionne ;
* le downgrade programmé fonctionne ;
* le downgrade forcé fonctionne ;
* les factures sont générées ;
* les paiements sont suivis ;
* les webhooks sont traités ;
* MRR et ARR sont visibles ;
* les usages SMS/WhatsApp/Email sont suivis ;
* les quotas sont appliqués ;
* les audit logs fonctionnent ;
* un module métier peut être ajouté sans modifier le core.

---

## 32. Roadmap recommandée

### Phase 1 — Socle backend

* structure package ;
* FastAPI setup ;
* PostgreSQL ;
* Alembic ;
* auth ;
* tenants ;
* users ;
* middleware tenant.

### Phase 2 — Permissions

* rôles ;
* permissions ;
* guards API ;
* permissions frontend ;
* permissions métiers extensibles.

### Phase 3 — Plans et abonnements

* plans ;
* features ;
* quotas ;
* subscriptions ;
* trial ;
* expiration.

### Phase 4 — Billing

* factures ;
* paiements ;
* reçus ;
* historique ;
* relances.

### Phase 5 — Upgrade / downgrade

* upgrade immédiat ;
* prorata ;
* paiement upgrade ;
* downgrade programmé ;
* annulation downgrade ;
* downgrade forcé ;
* historique changements.

### Phase 6 — Providers Super Admin

* provider configs ;
* chiffrement credentials ;
* DexPay ;
* Twilio ;
* Telnyx ;
* Meta WhatsApp ;
* SMTP/Brevo ;
* test provider ;
* logs provider.

### Phase 7 — Notifications

* templates SMS ;
* templates WhatsApp ;
* templates Email ;
* envoi test ;
* logs d’envoi.

### Phase 8 — Analytics

* MRR ;
* ARR ;
* churn ;
* revenus ;
* tenants ;
* paiements ;
* usage providers.

### Phase 9 — Frontend Admin

* Super Admin UI ;
* Tenant Admin UI ;
* plans ;
* billing ;
* providers ;
* analytics ;
* logs.

### Phase 10 — CLI et documentation

* init ;
* migrate ;
* seed ;
* create-super-admin ;
* documentation ;
* exemples SaaS.

---

## 33. Exemple d’utilisation : SaaS immobilier

Le core fournit :

* auth ;
* tenants ;
* users ;
* roles ;
* permissions ;
* plans ;
* billing ;
* payments ;
* notifications ;
* providers ;
* dashboard ;
* logs.

Le SaaS immobilier ajoute :

* biens ;
* propriétaires ;
* locataires ;
* contrats ;
* loyers ;
* quittances ;
* maintenance.

Le client immobilier utilise :

* son dashboard ;
* ses biens ;
* ses locataires ;
* ses loyers ;
* ses factures ;
* son abonnement.

Mais il ne configure pas :

* DexPay ;
* Twilio ;
* WhatsApp ;
* Email ;
* SMTP ;
* Webhooks.

Tout cela reste géré par Dymo.

---

## 34. Conclusion

Dymo SaaS Core doit devenir une base interne robuste, réutilisable et adaptée au marché africain.

Le principe final est :

```txt
Toi / Dymo :
- Propriétaire de la plateforme
- Configure les providers
- Gère les plans
- Gère les paiements
- Suit le MRR
- Contrôle les tenants

Tenant :
- Client B2B
- Utilise le SaaS
- Gère ses utilisateurs
- Gère ses données métiers
- Paie son abonnement
- Ne configure aucun provider technique
```

Cette architecture permet de lancer rapidement plusieurs SaaS B2B en Afrique sans répéter les mêmes fondations techniques à chaque nouveau projet.
