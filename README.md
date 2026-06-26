# Dymo SaaS Core

Dymo SaaS Core is a reusable FastAPI backend core for building B2B multi-tenant SaaS products.

## Features

- Multi-tenant architecture
- Platform admin API
- Tenant app API
- Authentication
- Users, roles, and permissions
- Plans and subscriptions
- Billing and payments
- Providers
- API keys
- Webhooks
- Audit logs
- Analytics
- Module registry

## Installation

```bash
pip install -e .
```

## Usage

```python
from fastapi import FastAPI
from dymo_saas_core import setup_saas_core

app = FastAPI()
setup_saas_core(app)
```

## API Spaces

```txt
/api/v1/platform/*
/api/v1/app/*
```

## Important

This package is core-only. Business modules should live in external SaaS projects.
