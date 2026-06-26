import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { RouteGuard } from "@/features/auth/route-guard";

export default function PlatformLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <RouteGuard area="platform">
      <AppShell area="platform">{children}</AppShell>
    </RouteGuard>
  );
}
