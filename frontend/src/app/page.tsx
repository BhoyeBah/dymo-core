import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, Building2, Shield } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(15,23,42,0.12),_transparent_30%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] px-4 py-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl flex-col justify-center gap-10">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Dymo SaaS Core</p>
          <h1 className="mt-4 font-[var(--font-heading)] text-5xl font-semibold tracking-tight text-slate-950 md:text-7xl">
            Core backend
            <span className="block text-slate-500">Platform and tenant control panels.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-slate-600">
            Deux espaces seulement: <strong>/platform</strong> pour le super admin et <strong>/app</strong> pour le tenant.
            Aucun module métier n’est embarqué dans ce frontend.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <LandingCard
            title="Platform Admin"
            description="Pilotage global du core, des tenants, plans, providers, analytics et logs."
            href="/platform/login"
            icon={<Shield className="h-5 w-5" />}
          />
          <LandingCard
            title="Tenant App"
            description="Espace client pour les utilisateurs, billing, API keys, webhooks et settings."
            href="/app/login"
            icon={<Building2 className="h-5 w-5" />}
          />
        </div>
      </div>
    </main>
  );
}

function LandingCard({
  title,
  description,
  href,
  icon
}: {
  title: string;
  description: string;
  href: string;
  icon: ReactNode;
}) {
  return (
    <Card className="group overflow-hidden border-slate-200/80 bg-white/85 shadow-glow transition hover:-translate-y-1">
      <CardHeader>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg">
          {icon}
        </div>
        <CardTitle className="mt-4 text-2xl">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Link
          href={href}
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 text-sm font-medium text-white transition hover:bg-slate-800"
        >
          Ouvrir
          <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
        </Link>
      </CardContent>
    </Card>
  );
}
