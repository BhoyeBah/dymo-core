import { SectionPage } from "@/components/layout/page-shell";
import { OverviewDashboard } from "@/features/dashboard/overview-dashboard";
import { getRouteSpec } from "@/features/routes";
import { ResourcePage } from "@/features/resources/resource-page";
import { EmptyState } from "@/components/common/feedback";
import type { Area } from "@/types";

export function ScreenPage({
  area,
  slugParts,
  detailId
}: {
  area: Area;
  slugParts: string[];
  detailId?: string;
}) {
  const spec = getRouteSpec(area, slugParts);

  if (area === "app" && slugParts[0] === "invitations" && slugParts[1] === "accept") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <EmptyState
          title="Formulaire d’acceptation"
          description="Cette page servira à valider une invitation reçue. Elle reste neutre tant que le backend n’expose pas le schéma final."
        />
      </SectionPage>
    );
  }

  if (spec.kind === "dashboard") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <OverviewDashboard area={area} />
      </SectionPage>
    );
  }

  if (spec.kind === "form") {
    return (
      <SectionPage title={spec.title} description={spec.description}>
        <EmptyState
          title="Endpoint non disponible"
          description="Le formulaire dédié sera branché sur l’endpoint backend lorsque le schéma final sera exposé."
        />
      </SectionPage>
    );
  }

  return (
    <SectionPage title={spec.title} description={spec.description}>
      <ResourcePage area={area} title={spec.title} description={spec.description} endpoint={spec.endpoint} canCreate={spec.canCreate} detailId={detailId} />
    </SectionPage>
  );
}

