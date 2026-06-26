import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { RouteGuard } from "@/features/auth/route-guard";

export default function TenantLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <RouteGuard area="app">
      <AppShell area="app">{children}</AppShell>
    </RouteGuard>
  );
}
