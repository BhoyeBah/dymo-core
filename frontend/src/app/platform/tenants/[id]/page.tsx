import { ScreenPage } from "@/features/screens/screen-page";

export default function PlatformTenantDetailPage({ params }: { params: { id: string } }) {
  return <ScreenPage area="platform" slugParts={["tenants", params.id]} detailId={params.id} />;
}

