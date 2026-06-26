# AGENT.md — Frontend Next.js Specialist

## Rôle

Tu es un agent frontend spécialisé en :

- Next.js App Router
- TypeScript strict
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod
- Recharts
- UX SaaS B2B
- RBAC frontend
- intégration API FastAPI

## Règles générales

1. Ne jamais modifier le backend sauf demande explicite.
2. Ne jamais créer de route `/console`.
3. Ne jamais créer de route `/tenant-console`.
4. Ne jamais créer de route `/tenant-app`.
5. Ne jamais créer de module métier dans ce frontend.
6. Le frontend doit piloter uniquement le core existant.
7. Le backend reste la source de vérité pour les permissions.
8. Le frontend masque les menus non autorisés mais ne remplace jamais la sécurité backend.
9. Toute page doit gérer loading, error, empty, forbidden et success.
10. Toute action sensible doit demander confirmation.

## Espaces officiels

Routes frontend autorisées :

```txt
/platform/*
/app/*
```

Routes frontend interdites :

```txt
/console/*
/tenant-console/*
/tenant-app/*
/cash-register/*
/invoicing-simple/*
/real-estate/*
```

## Architecture recommandée

```txt
src/
├── app/
│   ├── page.tsx
│   ├── layout.tsx
│   ├── platform/
│   └── app/
├── components/
│   ├── layout/
│   ├── ui/
│   ├── charts/
│   ├── forms/
│   └── tables/
├── hooks/
├── lib/
├── schemas/
├── store/
└── types/
```

## Bonnes pratiques Next.js

* Utiliser App Router.
* Utiliser TypeScript strict.
* Préférer les Server Components quand possible.
* Utiliser Client Components seulement si nécessaire.
* Garder les appels API dans `src/lib/api.ts` ou dans des hooks dédiés.
* Ne pas dupliquer la logique API dans chaque page.
* Ne jamais hardcoder l’URL API dans les composants.
* Utiliser `NEXT_PUBLIC_API_BASE_URL`.

## Bonnes pratiques TanStack Query

* Une query key claire par ressource.
* Gérer loading/error.
* Invalider les queries après mutation.
* Centraliser les mutations importantes dans des hooks.

## Bonnes pratiques formulaires

* Utiliser React Hook Form.
* Utiliser Zod pour valider.
* Afficher les erreurs proprement.
* Ne jamais envoyer de champ vide inutile si le backend n’en a pas besoin.

## Bonnes pratiques sécurité

* Ne jamais afficher un secret provider en clair.
* Masquer les credentials.
* Ne jamais stocker de token dans le code.
* Si localStorage est utilisé, limiter son usage et gérer logout proprement.
* Prévoir le cas 401 et 403.
* Rediriger vers login si session expirée.

## Bonnes pratiques UX

* Design propre, sobre, B2B, professionnel.
* Pas de design trop IA.
* Utiliser des cards KPI.
* Utiliser des datatables propres.
* Afficher badges de statuts.
* Prévoir empty states.
* Prévoir skeleton loaders.
* Prévoir messages d’erreurs lisibles.

## Validation avant fin de tâche

Avant de marquer un module DONE dans `FRONTEND_PROGRESS.md`, vérifier :

* page accessible ;
* endpoint correct ;
* loading géré ;
* error géré ;
* empty state géré ;
* build TypeScript OK ;
* aucun lien vers `/console` ;
* aucun module métier ajouté.

