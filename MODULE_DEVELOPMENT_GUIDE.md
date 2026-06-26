# MODULE DEVELOPMENT GUIDE

Ce document explique comment brancher **Dymo SaaS Core** dans n'importe quel projet FastAPI, puis comment créer un module métier proprement, sans modifier le noyau de la plateforme.

---

## 1. Brancher le core dans un projet

Dans chaque nouveau projet SaaS, on installe le package puis on attache le core à l'application FastAPI.

```bash
pip install dymo-saas-core
```

```python
from fastapi import FastAPI
from dymo_saas_core import setup_saas_core

app = FastAPI(title="Mon SaaS")
setup_saas_core(app)
```

Si tu veux charger des modules métiers au démarrage, tu peux les passer directement à `setup_saas_core` :

```python
from fastapi import FastAPI
from dymo_saas_core import setup_saas_core
from my_project.modules import invoicing, crm

app = FastAPI(title="Mon SaaS")
setup_saas_core(app, modules=[invoicing, crm])
```

Ce que le core branche automatiquement :

- les handlers d'exceptions standardisés ;
- le middleware CORS ;
- le middleware d'idempotence ;
- le middleware de journalisation des API keys ;
- le routeur plateforme `/api/v1/platform` ;
- le routeur tenant `/api/v1/app` ;
- le routeur webhooks `/api/v1` ;
- le healthcheck système ;
- le registre des modules.

Dans ce dépôt, l’export officiel existe déjà dans [src/dymo_saas_core/__init__.py](/home/bah/Bureau/dymo-core/src/dymo_saas_core/__init__.py), donc l'import `from dymo_saas_core import setup_saas_core` fonctionne directement.

---

## 2. Ce que fait réellement `setup_saas_core`

La fonction `setup_saas_core(app, modules=None)` :

- enregistre les exception handlers ;
- ajoute les middlewares core ;
- branche les routes plateforme et tenant ;
- branche les routes webhooks ;
- branche la route de santé `/health` ;
- enregistre les modules passés en argument ;
- synchronise les modules connus avec la base si elle est disponible.

La logique d’assemblage est visible dans [src/dymo_saas_core/app.py](/home/bah/Bureau/dymo-core/src/dymo_saas_core/app.py).

Important :

- les routes système sont montées sous `/api/v1/platform` et `/api/v1/app` ;
- les routes webhooks sont montées sous `/api/v1` ;
- les modules métiers sont ajoutés avec leur propre `routes_prefix` ;
- si un router FastAPI possède déjà un prefix local, ce prefix se combine avec celui fourni au moment du `include_router`.

---

## 3. Structure attendue d’un module

Un module métier doit contenir au minimum :

- un `manifest` ;
- un `router` FastAPI ;
- des schémas Pydantic ;
- une couche service ;
- éventuellement des modèles SQLAlchemy ;
- éventuellement une migration Alembic ;
- éventuellement des tests.

Exemple de structure :

```txt
my_module/
  __init__.py
  manifest.py
  routes.py
  schemas.py
  services.py
  models.py
```

Dans ce dépôt, on retrouve déjà ce modèle dans [src/dymo_saas_core/modules/cash_register_simple/manifest.py](/home/bah/Bureau/dymo-core/src/dymo_saas_core/modules/cash_register_simple/manifest.py) et [src/dymo_saas_core/modules/cash_register_simple/routes.py](/home/bah/Bureau/dymo-core/src/dymo_saas_core/modules/cash_register_simple/routes.py).

---

## 4. Le manifest du module

Le `manifest` décrit ce que le core doit savoir sur le module.

Il doit contenir au minimum :

- `key` : identifiant technique unique ;
- `name` : nom lisible ;
- `version` : version du module ;
- `minimum_core_version` : version minimale du core ;
- `routes_prefix` : préfixe des routes ;
- `permissions` : permissions créées par le module ;
- `limits` : quotas consommés ;
- `events` : événements métier ;
- `settings` : paramètres spécifiques éventuels.

Exemple :

```python
manifest = {
    "key": "crm",
    "name": "CRM",
    "description": "Gestion des prospects et clients",
    "version": "1.0.0",
    "minimum_core_version": "1.0.0",
    "category": "business",
    "is_core": False,
    "is_paid_addon": True,
    "routes_prefix": "/api/v1/app/crm",
    "dependencies": [],
    "permissions": [
        {"code": "crm.leads.view", "name": "View Leads", "description": "Can view leads"},
        {"code": "crm.leads.manage", "name": "Manage Leads", "description": "Can manage leads"},
    ],
    "limits": [
        {"metric_key": "crm.leads.max", "limit_value": 1000, "period": "monthly", "overage_allowed": False},
    ],
    "events": [
        {"event_type": "crm.lead.created", "description": "Triggered when a lead is created"},
    ],
    "settings": {},
}
```

Le core s'en sert pour :

- enregistrer le module dans le registre ;
- créer ou synchroniser les métadonnées en base ;
- activer ou désactiver le module selon le plan du tenant ;
- vérifier les dépendances de module ;
- brancher les routes au bon préfixe.

Le registre des modules est géré dans [src/dymo_saas_core/core/module_registry.py](/home/bah/Bureau/dymo-core/src/dymo_saas_core/core/module_registry.py).

---

## 5. Brancher un module au démarrage

Un module doit exposer son `manifest` et son `router`.

```python
from fastapi import APIRouter

manifest = {...}
router = APIRouter()
```

Ensuite, le projet principal le passe à `setup_saas_core` :

```python
from fastapi import FastAPI
from dymo_saas_core import setup_saas_core

from my_project.modules.crm import manifest, router

module = {
    "manifest": manifest,
    "router": router,
}

app = FastAPI()
setup_saas_core(app, modules=[module])
```

Si tu développes un package de module complet, tu peux aussi exposer un objet ou un module Python avec `manifest` et `router`, puis le passer directement à `setup_saas_core`.

Le core applique alors automatiquement le préfixe défini dans `routes_prefix`.

---

## 6. Où définir les permissions, features et quotas

Un module métier doit déclarer clairement ce qu'il introduit :

- les permissions fines qu'il ajoute ;
- les features de plan qu'il exploite ;
- les quotas qu'il consomme ;
- les événements métier qu'il émet.

Règle pratique :

- une `permission` sert à autoriser un type d'action ;
- une `feature` sert à activer ou désactiver une capacité de plan ;
- un `quota` sert à limiter l'usage dans le temps ;
- un `event` sert à déclencher des traitements asynchrones ou de l’audit.

---

## 7. Comment écrire les routes du module

Les routes d’un module doivent toujours respecter l’isolation tenant et les règles de contrôle d’accès.

Exemple de route sécurisée :

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.quota import check_limit, increment_usage
from dymo_saas_core.core.module_registry import require_module
from dymo_saas_core.core.tenant_context import require_tenant_user, require_active_tenant
from dymo_saas_core.core.responses import success_response

router = APIRouter()


@router.post("/leads")
def create_lead(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_tenant_user),
    tenant=Depends(require_active_tenant),
    _module=Depends(require_module("crm")),
    _perm=Depends(require_permission("crm.leads.manage")),
):
    check_limit(db, tenant.id, "crm.leads.max", requested_amount=1)
    lead = {"id": "lead_123", "tenant_id": str(tenant.id), **payload}
    increment_usage(db, tenant.id, "crm.leads.max", increment=1)
    return success_response(lead, message="Lead created")
```

La logique à retenir :

- `require_tenant_user` vérifie que l’utilisateur appartient bien à un tenant ;
- `require_active_tenant` bloque les tenants suspendus ;
- `require_module("crm")` vérifie que le module est activé pour ce tenant ;
- `require_permission(...)` vérifie le droit exact ;
- `check_limit(...)` et `increment_usage(...)` gèrent les quotas.

Les helpers de contexte tenant sont définis dans [src/dymo_saas_core/core/tenant_context.py](/home/bah/Bureau/dymo-core/src/dymo_saas_core/core/tenant_context.py).

---

## 8. Les 4 niveaux de sécurité

Chaque route sensible doit être protégée dans cet ordre :

- permission ;
- abonnement actif ;
- feature active dans le plan ;
- quota disponible.

Exemple :

```python
from fastapi import Depends
from dymo_saas_core.core.permissions import (
    require_permission,
    require_active_subscription,
    require_feature_access,
    require_usage_limit,
)


@router.post("/invoices")
def create_invoice(
    _user=Depends(require_permission("cash_register_simple.sales.create")),
    _sub=Depends(require_active_subscription()),
    _feature=Depends(require_feature_access("receipt_pdf_export")),
    _quota=Depends(require_usage_limit("invoices")),
):
    ...
```

Notes importantes :

- `require_active_subscription()` protège contre les abonnements expirés, suspendus ou absents ;
- `require_feature_access(feature_code)` vérifie qu’une capability est bien incluse dans le plan ;
- `require_usage_limit(resource_code)` bloque si la limite est dépassée ;
- `require_permission(permission_code)` reste obligatoire pour les actions sensibles.

---

## 9. Implémenter un module complet

Voici l’ordre recommandé.

### 9.1 Créer le manifeste

- définir la clé technique ;
- déclarer les permissions ;
- déclarer les quotas ;
- déclarer les features ;
- fixer le préfixe de routes.

### 9.2 Créer les schémas

- `CreateSchema` pour les entrées ;
- `UpdateSchema` pour les modifications ;
- `ResponseSchema` pour les sorties.

### 9.3 Créer les services

- logique métier pure ;
- aucune dépendance HTTP ;
- aucune règle d’interface ;
- gestion de la transaction et du tenant.

### 9.4 Créer les routes

- exposer les endpoints du module ;
- brancher les dépendances core ;
- éviter de répliquer les contrôles de sécurité ;
- renvoyer des réponses standardisées.

### 9.5 Ajouter les modèles et migrations

- chaque table métier doit contenir `tenant_id` si la donnée est multi-tenant ;
- les relations doivent être filtrées par tenant ;
- les migrations Alembic doivent créer les colonnes et index nécessaires.

### 9.6 Ajouter les tests

- test d’accès autorisé ;
- test d’accès interdit ;
- test de quota ;
- test d’isolation tenant ;
- test de désactivation de module.

---

## 10. Exemple de module minimal

```python
from fastapi import APIRouter, Depends
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.core.module_registry import require_module
from dymo_saas_core.core.tenant_context import require_tenant_user
from dymo_saas_core.core.responses import success_response

manifest = {
    "key": "reports",
    "name": "Reports",
    "version": "1.0.0",
    "minimum_core_version": "1.0.0",
    "routes_prefix": "/api/v1/app/reports",
    "permissions": [
        {"code": "reports.view", "name": "View reports", "description": "Can view reports"},
    ],
    "limits": [],
    "events": [],
    "settings": {},
}

router = APIRouter()


@router.get("/overview")
def overview(
    _user=Depends(require_tenant_user),
    _module=Depends(require_module("reports")),
    _perm=Depends(require_permission("reports.view")),
):
    return success_response({"sales": 42}, message="Overview loaded")
```

---

## 11. Règles d’or

- Le tenant ne doit jamais voir la configuration technique des providers.
- Toute donnée métier doit être scoppée par `tenant_id`.
- N’écris pas de contrôles de permission en dur dans les routes si le core fournit déjà la dépendance.
- N’appelle pas le modèle ou la base directement depuis le routeur si la logique peut vivre dans un service.
- Ajoute toujours un test quand tu ajoutes une permission, une feature ou un quota.
- Utilise les helpers du core plutôt que des implémentations locales parallèles.

---

## 12. Quand utiliser `setup_saas_core`

Utilise `setup_saas_core` dans tous les projets FastAPI qui doivent bénéficier du socle Dymo :

- nouveaux SaaS métiers ;
- backends internes ;
- API clients ;
- applications multi-tenant ;
- modules partenaires.

Si le projet ne doit pas être multi-tenant, ou s’il ne doit pas exposer les routes Dymo, alors il ne faut pas brancher ce core.

---

## 13. Checklist de validation d’un module

Avant de considérer un module comme prêt, vérifie :

- le module est enregistré avec un `manifest` valide ;
- les permissions sont synchronisées ;
- les quotas sont visibles dans le plan ;
- les routes sont montées sous le bon préfixe ;
- l’accès est bloqué si le module n’est pas activé ;
- les tests passent ;
- les données sont bien filtrées par tenant ;
- les migrations sont appliquées.
