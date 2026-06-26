"use client";

import { useQuery } from "@tanstack/react-query";
import { endpoints } from "@/lib/endpoints";
import { safeApiRequest } from "@/lib/api";
import { LoadingState, ErrorState, EmptyState } from "@/components/common/feedback";
import { StatCard } from "@/components/common/stat-card";
import { RevenueChart, UsageChart } from "@/components/charts/overview-chart";
import type { AnalyticsOverview } from "@/types";

const fallback: AnalyticsOverview = {
  mrr: 0,
  arr: 0,
  monthlyRevenue: 0,
  activeTenants: 0,
  trialTenants: 0,
  suspendedTenants: 0,
  successfulPayments: 0,
  failedPayments: 0,
  smsUsage: 0,
  whatsappUsage: 0,
  emailUsage: 0
};

export function OverviewDashboard({
  area
}: {
  area: "platform" | "app";
}) {
  const query = useQuery({
    queryKey: [area, "dashboard"],
    queryFn: async () => {
      const primary = area === "platform" ? endpoints.platform.dashboard : endpoints.app.dashboard;
      const secondary = area === "platform" ? endpoints.platform.analytics.overview : endpoints.app.billing.usage;
      const [main, aux] = await Promise.allSettled([safeApiRequest<Record<string, unknown>>(primary), safeApiRequest<Record<string, unknown>>(secondary)]);
      return { main, aux };
    }
  });

  if (query.isLoading) {
    return <LoadingState label="Chargement du dashboard..." />;
  }

  if (query.isError) {
    return <ErrorState description={query.error instanceof Error ? query.error.message : "Erreur de chargement"} retry={() => query.refetch()} />;
  }

  const main = query.data?.main.status === "fulfilled" ? query.data.main.value.data : null;
  const aux = query.data?.aux.status === "fulfilled" ? query.data.aux.value.data : null;

  const overview = (main as Partial<AnalyticsOverview> | null) ?? fallback;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <StatCard label="MRR" value={overview.mrr ?? 0} />
        <StatCard label="ARR" value={overview.arr ?? 0} />
        <StatCard label="Revenus du mois" value={overview.monthlyRevenue ?? 0} />
        <StatCard label="Tenants actifs" value={overview.activeTenants ?? 0} />
        <StatCard label="Tenants en essai" value={overview.trialTenants ?? 0} />
        <StatCard label="Tenants suspendus" value={overview.suspendedTenants ?? 0} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <RevenueChart />
        <UsageChart />
      </div>
      {aux ? null : <EmptyState title="Endpoint non disponible" description="Le backend ne renvoie pas encore les métriques attendues pour ce tableau." />}
    </div>
  );
}

