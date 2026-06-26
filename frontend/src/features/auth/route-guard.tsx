"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { Area } from "@/types";
import { useAuthStore } from "@/store/auth-store";
import { ForbiddenState, LoadingState } from "@/components/common/feedback";
import { hasPermission } from "@/lib/auth";

export function RouteGuard({
  area,
  requiredPermission,
  children
}: {
  area: Area;
  requiredPermission?: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const { area: sessionArea, token, isHydrated } = useAuthStore();

  useEffect(() => {
    if (!isHydrated) {
      return;
    }

    if (!token || sessionArea !== area) {
      router.replace(`/${area}/login`);
    }
  }, [area, isHydrated, router, sessionArea, token]);

  if (!isHydrated) {
    return <LoadingState label="Vérification de session..." />;
  }

  if (!token || sessionArea !== area) {
    return <LoadingState label="Redirection..." />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <ForbiddenState />;
  }

  return <>{children}</>;
}
