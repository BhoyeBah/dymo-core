"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { getQueryClient } from "@/lib/query-client";
import { useAuthStore } from "@/store/auth-store";

export function AppProviders({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();

  useEffect(() => {
    useAuthStore.persist.rehydrate();
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
