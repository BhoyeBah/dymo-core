import { SectionPage } from "@/components/layout/page-shell";
import { OverviewDashboard } from "@/features/dashboard/overview-dashboard";
import { getRouteSpec } from "@/features/routes";
import { ResourcePage } from "@/features/resources/resource-page";
import { EmptyState } from "@/components/common/feedback";

export default function PlatformCatchAllPage({
  params
}: {
  params: { slug: string[] };
}) {
  const slug = params.slug ?? [];
  const spec = getRouteSpec("platform", slug);
  const detailId = spec.kind === "detail" ? slug[1] : undefined;

  if (spec.kind === "dashboard") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <OverviewDashboard area="platform" />
      </SectionPage>
    );
  }

  if (spec.kind === "form") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <EmptyState title="Endpoint non disponible" description="Le formulaire dédié sera branché sur l’endpoint backend lorsque le schéma final sera exposé." />
      </SectionPage>
    );
  }

  return (
    <SectionPage title={spec.title} description={spec.description}>
      <ResourcePage area="platform" title={spec.title} description={spec.description} endpoint={spec.endpoint} canCreate={spec.canCreate} detailId={detailId} />
    </SectionPage>
  );
}

