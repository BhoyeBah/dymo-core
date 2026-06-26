export const endpoints = {
  platform: {
    auth: {
      login: "/api/v1/platform/auth/login",
      me: "/api/v1/platform/auth/me",
      logout: "/api/v1/platform/auth/logout",
      refresh: "/api/v1/platform/auth/refresh"
    },
    dashboard: "/api/v1/platform/dashboard",
    analytics: {
      overview: "/api/v1/platform/analytics/overview",
      revenue: "/api/v1/platform/analytics/revenue",
      tenants: "/api/v1/platform/analytics/tenants",
      providers: "/api/v1/platform/analytics/providers",
      usage: "/api/v1/platform/analytics/usage"
    },
    tenants: "/api/v1/platform/tenants",
    plans: "/api/v1/platform/plans",
    subscriptions: "/api/v1/platform/subscriptions",
    payments: "/api/v1/platform/payments",
    invoices: "/api/v1/platform/invoices",
    providers: "/api/v1/platform/providers",
    providerLogs: "/api/v1/platform/provider-logs",
    webhooks: "/api/v1/platform/webhooks",
    notificationTemplates: "/api/v1/platform/notification-templates",
    auditLogs: "/api/v1/platform/audit-logs",
    modules: "/api/v1/platform/modules",
    apiKeys: "/api/v1/platform/api-keys",
    systemHealth: "/api/v1/platform/system-health"
  },
  app: {
    auth: {
      login: "/api/v1/app/auth/login",
      me: "/api/v1/app/auth/me",
      logout: "/api/v1/app/auth/logout",
      refresh: "/api/v1/app/auth/refresh"
    },
    dashboard: "/api/v1/app/dashboard",
    users: "/api/v1/app/users",
    invitations: "/api/v1/app/invitations",
    roles: "/api/v1/app/roles",
    permissions: "/api/v1/app/permissions",
    billing: {
      subscription: "/api/v1/app/billing/subscription",
      upgrade: "/api/v1/app/billing/subscription/upgrade",
      downgrade: "/api/v1/app/billing/subscription/downgrade",
      cancelDowngrade: "/api/v1/app/billing/subscription/cancel-downgrade",
      checkoutSession: "/api/v1/app/billing/subscription/checkout-session",
      portalSession: "/api/v1/app/billing/subscription/portal-session",
      invoices: "/api/v1/app/billing/invoices",
      usage: "/api/v1/app/billing/usage"
    },
    apiKeys: "/api/v1/app/api-keys",
    webhooks: "/api/v1/app/webhooks",
    auditLogs: "/api/v1/app/audit-logs",
    settings: "/api/v1/app/settings",
    company: "/api/v1/app/company"
  }
} as const;

