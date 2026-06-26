export type Area = "platform" | "app";

export interface User {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  status?: string;
  permissions?: string[];
  roles?: string[];
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  status?: string;
  country?: string;
  currency?: string;
  plan?: string;
}

export interface Plan {
  id: string;
  name: string;
  slug: string;
  description?: string;
  price?: number;
  trialDays?: number;
  features?: string[];
  quotas?: Record<string, number>;
  modules?: string[];
}

export interface Subscription {
  id: string;
  status: string;
  billingCycle?: string;
  planName?: string;
  currentPeriodEnd?: string;
}

export interface Invoice {
  id: string;
  number?: string;
  status: string;
  amountDue?: number;
  amountPaid?: number;
  currency?: string;
  dueDate?: string;
}

export interface Payment {
  id: string;
  status: string;
  amount?: number;
  currency?: string;
  provider?: string;
  createdAt?: string;
}

export interface ProviderConfig {
  id: string;
  providerType: string;
  providerName: string;
  environment?: string;
  isActive?: boolean;
  isDefault?: boolean;
  credentials?: Record<string, string | boolean | number | null>;
  supportedCountries?: string[];
  supportedCurrencies?: string[];
}

export interface ProviderLog {
  id: string;
  providerType: string;
  action: string;
  status: string;
  createdAt?: string;
  message?: string;
}

export interface AuditLog {
  id: string;
  actor?: string;
  action: string;
  targetType?: string;
  targetId?: string;
  status?: string;
  createdAt?: string;
}

export interface ApiKey {
  id: string;
  name: string;
  lastUsedAt?: string;
  status?: string;
  prefix?: string;
  rawKey?: string;
}

export interface WebhookSubscription {
  id: string;
  name: string;
  targetUrl: string;
  status?: string;
  events?: string[];
}

export interface UsageCounter {
  metric: string;
  value: number;
  limit?: number;
  period?: string;
}

export interface AnalyticsOverview {
  mrr: number;
  arr: number;
  monthlyRevenue: number;
  activeTenants: number;
  trialTenants: number;
  suspendedTenants: number;
  successfulPayments: number;
  failedPayments: number;
  smsUsage: number;
  whatsappUsage: number;
  emailUsage: number;
}

export interface ModuleRegistryItem {
  key: string;
  name: string;
  status?: string;
  version?: string;
  routesPrefix?: string;
}

export interface ApiErrorShape {
  message: string;
  status: number;
  code?: string;
  details?: unknown;
}

