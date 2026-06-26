import { useAuthStore } from "@/store/auth-store";
import type { Area, User } from "@/types";

export function getSession() {
  return useAuthStore.getState();
}

export function setSession(payload: {
  area: Area;
  token: string;
  refreshToken?: string | null;
  user: User;
  tenantSlug?: string | null;
}) {
  useAuthStore.getState().setSession(payload);
}

export function clearSession() {
  useAuthStore.getState().clearSession();
}

export function getBearerToken() {
  return useAuthStore.getState().token;
}

export function getTenantSlug() {
  return useAuthStore.getState().tenantSlug;
}

export function hasPermission(permission: string) {
  const user = useAuthStore.getState().user;
  if (!user) {
    return false;
  }

  const permissions = user.permissions ?? [];
  return permissions.includes(permission) || permissions.includes("*");
}

