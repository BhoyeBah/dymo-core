import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Area, User } from "@/types";

interface AuthState {
  area: Area | null;
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  tenantSlug: string | null;
  isHydrated: boolean;
  setHydrated: (value: boolean) => void;
  setSession: (payload: {
    area: Area;
    token: string;
    refreshToken?: string | null;
    user: User;
    tenantSlug?: string | null;
  }) => void;
  updateUser: (user: User) => void;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      area: null,
      token: null,
      refreshToken: null,
      user: null,
      tenantSlug: null,
      isHydrated: false,
      setHydrated: (value) => set({ isHydrated: value }),
      setSession: ({ area, token, refreshToken = null, user, tenantSlug = null }) =>
        set({ area, token, refreshToken, user, tenantSlug }),
      updateUser: (user) => set({ user }),
      clearSession: () => set({ area: null, token: null, refreshToken: null, user: null, tenantSlug: null })
    }),
    {
      name: "dymo-saas-core-auth",
      partialize: (state) => ({
        area: state.area,
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
        tenantSlug: state.tenantSlug
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      }
    }
  )
);

