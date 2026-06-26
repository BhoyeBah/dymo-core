"use client";

import type { ComponentType, ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Bell,
  Building2,
  CreditCard,
  Database,
  FileText,
  Fingerprint,
  Gauge,
  Globe,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Shield,
  SlidersHorizontal,
  Users,
  Wallet,
  Webhook,
  Boxes,
  Activity,
  FileClock
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { clearSession } from "@/lib/auth";
import { useState } from "react";
import type { Area } from "@/types";

type MenuItem = {
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
};

const platformMenu: MenuItem[] = [
  { label: "Dashboard", href: "/platform/dashboard", icon: LayoutDashboard },
  { label: "Tenants", href: "/platform/tenants", icon: Building2 },
  { label: "Plans", href: "/platform/plans", icon: SlidersHorizontal },
  { label: "Subscriptions", href: "/platform/subscriptions", icon: CreditCard },
  { label: "Payments", href: "/platform/payments", icon: Wallet },
  { label: "Invoices", href: "/platform/invoices", icon: FileText },
  { label: "Providers", href: "/platform/providers", icon: Globe },
  { label: "Provider Logs", href: "/platform/provider-logs", icon: FileClock },
  { label: "Webhooks", href: "/platform/webhooks", icon: Webhook },
  { label: "Notification Templates", href: "/platform/notification-templates", icon: Bell },
  { label: "Analytics", href: "/platform/analytics", icon: BarChart3 },
  { label: "Audit Logs", href: "/platform/audit-logs", icon: Shield },
  { label: "Settings", href: "/platform/settings", icon: SlidersHorizontal },
  { label: "Modules", href: "/platform/modules", icon: Boxes },
  { label: "API Keys", href: "/platform/api-keys", icon: KeyRound },
  { label: "System Health", href: "/platform/system-health", icon: Activity }
];

const appMenu: MenuItem[] = [
  { label: "Dashboard", href: "/app/dashboard", icon: LayoutDashboard },
  { label: "Company", href: "/app/company", icon: Building2 },
  { label: "Users", href: "/app/users", icon: Users },
  { label: "Invitations", href: "/app/invitations", icon: MailIcon },
  { label: "Roles", href: "/app/roles", icon: Fingerprint },
  { label: "Permissions", href: "/app/permissions", icon: Shield },
  { label: "Subscription", href: "/app/subscription", icon: CreditCard },
  { label: "Billing", href: "/app/billing", icon: Wallet },
  { label: "Invoices", href: "/app/invoices", icon: FileText },
  { label: "Usage", href: "/app/usage", icon: Gauge },
  { label: "API Keys", href: "/app/api-keys", icon: KeyRound },
  { label: "Webhooks", href: "/app/webhooks", icon: Webhook },
  { label: "Audit Logs", href: "/app/audit-logs", icon: Shield },
  { label: "Settings", href: "/app/settings", icon: SlidersHorizontal }
];

function MailIcon({ className }: { className?: string }) {
  return <Bell className={className} />;
}

function MenuLink({ item, active }: { item: MenuItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition",
        active ? "bg-slate-900 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
      )}
    >
      <Icon className="h-4 w-4" />
      {item.label}
    </Link>
  );
}

export function AppShell({ area, children }: { area: Area; children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const menu = area === "platform" ? platformMenu : appMenu;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,23,42,0.08),_transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] text-slate-950">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="sticky top-0 hidden h-screen w-80 shrink-0 border-r border-slate-200/80 bg-white/80 px-4 py-6 backdrop-blur xl:block">
          <SidebarContent area={area} menu={menu} pathname={pathname} />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/70 px-4 py-3 backdrop-blur xl:px-8">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" className="xl:hidden" onClick={() => setMobileOpen((value) => !value)}>
                  <Menu className="h-4 w-4" />
                </Button>
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{area}</p>
                  <p className="text-sm font-medium text-slate-950">{area === "platform" ? "Super Admin Dymo" : "Tenant App"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm" onClick={() => router.refresh()}>
                  <Database className="h-4 w-4" />
                  Refresh
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    clearSession();
                    router.push(`/${area}/login`);
                  }}
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </Button>
              </div>
            </div>
          </header>
          {mobileOpen ? (
            <div className="border-b border-slate-200 bg-white/90 px-4 py-4 xl:hidden">
              <SidebarContent area={area} menu={menu} pathname={pathname} onNavigate={() => setMobileOpen(false)} />
            </div>
          ) : null}
          <main className="flex-1 px-4 py-6 xl:px-8">
            <div className="space-y-6">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}

function SidebarContent({
  area,
  menu,
  pathname,
  onNavigate
}: {
  area: Area;
  menu: MenuItem[];
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col gap-6">
      <Link href="/" className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-glow">
          <Shield className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight">Dymo SaaS Core</p>
          <p className="text-xs text-slate-500">{area === "platform" ? "Platform Admin" : "Tenant App"}</p>
        </div>
      </Link>
      <nav className="flex-1 space-y-1 overflow-y-auto pr-1">
        {menu.map((item) => (
          <div key={item.href} onClick={onNavigate}>
            <MenuLink item={item} active={pathname.startsWith(item.href)} />
          </div>
        ))}
      </nav>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-sm font-medium text-slate-900">Core only</p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Le frontend pilote uniquement `/api/v1/platform/*` et `/api/v1/app/*`.
        </p>
      </div>
    </div>
  );
}
