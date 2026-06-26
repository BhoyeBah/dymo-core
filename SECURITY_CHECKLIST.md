# SECURITY CHECKLIST

Ce document regroupe les contrôles et les validations de sécurité indispensables pour assurer la conformité et la robustesse de la plateforme **Dymo SaaS Core** avant tout déploiement en production.

---

## 1. Authentification & Sessions
- [ ] Mots de passe chiffrés en base de données à l'aide d'un algorithme de hashage robuste (ex: bcrypt ou argon2).
- [ ] Jeton d'accès JWT (`access_token`) à durée de vie courte (ex: 15 minutes).
- [ ] Jeton de rafraîchissement (`refresh_token`) stocké de manière sécurisée et doté d'une rotation systématique à chaque appel.
- [ ] Cookies d'authentification configurés avec les attributs `HttpOnly`, `Secure` et `SameSite=Lax/Strict` en production.
- [ ] Possibilité de révoquer immédiatement toutes les sessions actives d'un utilisateur en cas de compromission.
- [ ] Tokens de réinitialisation de mot de passe à usage unique et expirables rapidement (ex: 1 heure).

---

## 2. Access Control (Les 4 Niveaux de Blocage)
Toute requête sur l'espace client `/api/v1/app/*` ou le chargement d'une ressource métier doit être validée et éventuellement bloquée par le backend sur 4 niveaux successifs :
- [ ] **Niveau 1 : Permission** (Vérification des habilitations RBAC de l'utilisateur connecté via `require_permission`).
- [ ] **Niveau 2 : État de l'abonnement** (Validation que le tenant possède un abonnement actif et non expiré ou suspendu via `require_active_subscription`).
- [ ] **Niveau 3 : Accès aux fonctionnalités** (Contrôle que le forfait/plan du tenant inclut bien la fonctionnalité demandée via `require_feature_access`).
- [ ] **Niveau 4 : Respect des Quotas** (Vérification en temps réel que la limite d'usage sur la ressource ou l'action n'est pas atteinte via `require_usage_limit`).

---

## 3. Isolation des Configurations et Secrets
- [ ] **Pas de Credentials dans l'espace Tenant** : Les configurations de SMTP, SMS (Twilio/Brevo), WhatsApp et passerelles de paiement (Stripe/DexPay) restent exclusivement dans l'espace Super Admin `/platform`.
- [ ] **Interdiction formelle** d'exposer des points d'accès de lecture, écriture ou modification des configurations provider sous le préfixe `/app`.
- [ ] Chiffrement symétrique fort (ex: AES-256 via la bibliothèque `cryptography`) de tous les secrets d'API et identifiants stockés dans la table `core_provider_configs`.
- [ ] Masquage systématique des secrets dans les payloads JSON renvoyés par l'API (champs masqués par `***` dans les réponses).
- [ ] Blocage et suppression automatique des secrets ou jetons en clair dans les logs système ou d'audit.
- [ ] Les routes `GET /api/v1/platform/providers`, `GET /api/v1/platform/provider-logs`, `GET /api/v1/platform/payments`, `GET /api/v1/platform/invoices` et `GET /api/v1/platform/audit-logs` sont les seules voies d'administration globale pour ces objets.

---

## 4. Multi-Tenant & Isolation de Données
- [ ] Clé étrangère `tenant_id` présente et indexée sur l'intégralité des tables hébergeant des données client ou métier.
- [ ] Injection systématique et automatique du contexte tenant via le header `X-Tenant-Slug` sur toutes les routes `/app/*`.
- [ ] Requêtes SQL toujours filtrées explicitement par `tenant_id` à l'aide d'un middleware SQLAlchemy ou d'un gestionnaire de contexte.
- [ ] Réalisation de tests unitaires et d'intégration vérifiant l'impossibilité pour le Tenant A d'accéder aux données ou d'exécuter des actions pour le compte du Tenant B (Isolation de données).
