export const PLATFORM_MENU_PERMISSIONS = {
  dashboard: "platform.dashboard.view",
  tenants: "platform.tenants.view",
  plans: "platform.plans.view",
  subscriptions: "platform.subscriptions.view",
  payments: "platform.payments.view",
  invoices: "platform.invoices.view",
  providers: "platform.providers.view",
  providerLogs: "platform.providers.logs.view",
  webhooks: "platform.webhooks.view",
  analytics: "platform.analytics.view",
  auditLogs: "platform.audit_logs.view",
  settings: "platform.settings.view",
  modules: "platform.modules.view",
  apiKeys: "platform.api_keys.view",
  systemHealth: "platform.system_health.view"
} as const;

export const APP_MENU_PERMISSIONS = {
  dashboard: "app.dashboard.view",
  company: "app.company.view",
  users: "app.users.view",
  invitations: "app.invitations.view",
  roles: "app.roles.view",
  permissions: "app.permissions.view",
  subscription: "app.subscription.view",
  billing: "app.billing.view",
  invoices: "app.invoices.view",
  usage: "app.usage.view",
  apiKeys: "app.api_keys.view",
  webhooks: "app.webhooks.view",
  auditLogs: "app.audit_logs.view",
  settings: "app.settings.view"
} as const;

