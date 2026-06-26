import { endpoints } from "@/lib/endpoints";
import type { Area } from "@/types";

export type RouteSpec = {
  title: string;
  description: string;
  endpoint?: string;
  secondaryEndpoint?: string;
  canCreate?: boolean;
  kind: "dashboard" | "resource" | "detail" | "form";
};

const platformRoutes: Record<string, RouteSpec> = {
  dashboard: {
    title: "Dashboard Platform",
    description: "Vue d'ensemble de la plateforme Dymo SaaS Core.",
    endpoint: endpoints.platform.dashboard,
    secondaryEndpoint: endpoints.platform.analytics.overview,
    kind: "dashboard"
  },
  tenants: {
    title: "Tenants",
    description: "Gestion des tenants et de leurs états.",
    endpoint: endpoints.platform.tenants,
    canCreate: true,
    kind: "resource"
  },
  plans: {
    title: "Plans",
    description: "Définition des plans, quotas, features et modules.",
    endpoint: endpoints.platform.plans,
    canCreate: true,
    kind: "resource"
  },
  subscriptions: {
    title: "Subscriptions",
    description: "Suivi des abonnements actifs et historiques.",
    endpoint: endpoints.platform.subscriptions,
    kind: "resource"
  },
  payments: {
    title: "Payments",
    description: "Paiements et tentatives de paiement.",
    endpoint: endpoints.platform.payments,
    kind: "resource"
  },
  invoices: {
    title: "Invoices",
    description: "Factures liées à la plateforme.",
    endpoint: endpoints.platform.invoices,
    kind: "resource"
  },
  providers: {
    title: "Providers",
    description: "Configuration des prestataires externes, secrets masqués.",
    endpoint: endpoints.platform.providers,
    canCreate: true,
    kind: "resource"
  },
  "provider-logs": {
    title: "Provider Logs",
    description: "Journaux d’intégration et d’appels providers.",
    endpoint: endpoints.platform.providerLogs,
    kind: "resource"
  },
  webhooks: {
    title: "Webhooks",
    description: "Configuration des webhooks plateforme.",
    endpoint: endpoints.platform.webhooks,
    canCreate: true,
    kind: "resource"
  },
  "notification-templates": {
    title: "Notification Templates",
    description: "Templates de notifications du core.",
    endpoint: endpoints.platform.notificationTemplates,
    kind: "resource"
  },
  analytics: {
    title: "Analytics",
    description: "Revenu, usage et répartition multi-tenant.",
    endpoint: endpoints.platform.analytics.overview,
    secondaryEndpoint: endpoints.platform.analytics.usage,
    kind: "dashboard"
  },
  "audit-logs": {
    title: "Audit Logs",
    description: "Historique des actions plateforme.",
    endpoint: endpoints.platform.auditLogs,
    kind: "resource"
  },
  settings: {
    title: "Settings",
    description: "Paramètres de la plateforme.",
    endpoint: "/api/v1/platform/settings",
    kind: "form"
  },
  modules: {
    title: "Modules",
    description: "Synchronisation du registre de modules.",
    endpoint: endpoints.platform.modules,
    canCreate: true,
    kind: "resource"
  },
  "api-keys": {
    title: "API Keys",
    description: "Clés d’API de la plateforme.",
    endpoint: endpoints.platform.apiKeys,
    canCreate: true,
    kind: "resource"
  },
  "system-health": {
    title: "System Health",
    description: "Vérification globale de l’état du core.",
    endpoint: endpoints.platform.systemHealth,
    kind: "resource"
  }
};

const appRoutes: Record<string, RouteSpec> = {
  dashboard: {
    title: "Dashboard Tenant",
    description: "Vue d’ensemble du tenant et de ses indicateurs.",
    endpoint: endpoints.app.dashboard,
    secondaryEndpoint: endpoints.app.billing.usage,
    kind: "dashboard"
  },
  company: {
    title: "Company",
    description: "Informations de l’entreprise du tenant.",
    endpoint: endpoints.app.company,
    kind: "form"
  },
  users: {
    title: "Users",
    description: "Gestion des utilisateurs du tenant.",
    endpoint: endpoints.app.users,
    canCreate: true,
    kind: "resource"
  },
  invitations: {
    title: "Invitations",
    description: "Invitations en attente et envoi de nouvelles invitations.",
    endpoint: endpoints.app.invitations,
    canCreate: true,
    kind: "resource"
  },
  roles: {
    title: "Roles",
    description: "Gestion des rôles et permissions.",
    endpoint: endpoints.app.roles,
    canCreate: true,
    kind: "resource"
  },
  permissions: {
    title: "Permissions",
    description: "Permissions disponibles pour le tenant.",
    endpoint: endpoints.app.permissions,
    kind: "resource"
  },
  subscription: {
    title: "Subscription",
    description: "Plan actuel et actions de billing.",
    endpoint: endpoints.app.billing.subscription,
    kind: "dashboard"
  },
  billing: {
    title: "Billing",
    description: "Historique de facturation et paiements.",
    endpoint: endpoints.app.billing.subscription,
    secondaryEndpoint: endpoints.app.billing.invoices,
    kind: "dashboard"
  },
  invoices: {
    title: "Invoices",
    description: "Factures du tenant.",
    endpoint: endpoints.app.billing.invoices,
    kind: "resource"
  },
  usage: {
    title: "Usage",
    description: "Métriques d’usage et limites.",
    endpoint: endpoints.app.billing.usage,
    kind: "resource"
  },
  "api-keys": {
    title: "API Keys",
    description: "Gestion des clés d’API du tenant.",
    endpoint: endpoints.app.apiKeys,
    canCreate: true,
    kind: "resource"
  },
  webhooks: {
    title: "Webhooks",
    description: "Webhooks liés au tenant.",
    endpoint: endpoints.app.webhooks,
    canCreate: true,
    kind: "resource"
  },
  "audit-logs": {
    title: "Audit Logs",
    description: "Historique des opérations du tenant.",
    endpoint: endpoints.app.auditLogs,
    kind: "resource"
  },
  settings: {
    title: "Settings",
    description: "Paramètres du tenant.",
    endpoint: endpoints.app.settings,
    kind: "form"
  },
  "invitations-accept": {
    title: "Accept Invitation",
    description: "Acceptation d’une invitation reçue.",
    endpoint: endpoints.app.invitations,
    kind: "form"
  }
};

export function getRouteSpec(area: Area, slugParts: string[]) {
  const first = slugParts[0] ?? "dashboard";

  if (area === "platform") {
    if (first === "tenants" && slugParts[1]) {
      return {
        title: "Tenant detail",
        description: "Détail d’un tenant.",
        endpoint: `${endpoints.platform.tenants}/${slugParts[1]}`,
        kind: "detail" as const
      };
    }

    return platformRoutes[first] ?? {
      title: "Platform",
      description: "Section plateforme.",
      kind: "resource" as const
    };
  }

  if (first === "invitations" && slugParts[1] === "accept") {
    return appRoutes["invitations-accept"];
  }

  return appRoutes[first] ?? {
    title: "Tenant App",
    description: "Section tenant.",
    kind: "resource" as const
  };
}

export function getAvailableEndpoints(area: Area, slugParts: string[]) {
  return getRouteSpec(area, slugParts);
}

