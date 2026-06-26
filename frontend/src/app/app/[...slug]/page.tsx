import { SectionPage } from "@/components/layout/page-shell";
import { OverviewDashboard } from "@/features/dashboard/overview-dashboard";
import { getRouteSpec } from "@/features/routes";
import { ResourcePage } from "@/features/resources/resource-page";
import { EmptyState } from "@/components/common/feedback";

export default function TenantCatchAllPage({
  params
}: {
  params: { slug: string[] };
}) {
  const slug = params.slug ?? [];
  const spec = getRouteSpec("app", slug);

  if (slug[0] === "invitations" && slug[1] === "accept") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <EmptyState title="Formulaire d’acceptation" description="Cette page servira à valider une invitation reçue. Elle reste neutre tant que le backend n’expose pas le schéma final." />
      </SectionPage>
    );
  }

  if (spec.kind === "dashboard") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <OverviewDashboard area="app" />
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

  const detailId = slug[1] && slug[0] === "users" ? slug[1] : undefined;

  return (
    <SectionPage title={spec.title} description={spec.description}>
      <ResourcePage area="app" title={spec.title} description={spec.description} endpoint={spec.endpoint} canCreate={spec.canCreate} detailId={detailId} />
    </SectionPage>
  );
}

