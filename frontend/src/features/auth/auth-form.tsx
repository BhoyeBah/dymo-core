"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api";
import { endpoints } from "@/lib/endpoints";
import { setSession } from "@/lib/auth";
import type { Area, User } from "@/types";

const schema = z.object({
  email: z.string().email("Email invalide"),
  password: z.string().min(6, "Mot de passe trop court"),
  tenantSlug: z.string().optional().or(z.literal(""))
});

type FormValues = z.infer<typeof schema>;

export function AuthForm({ area }: { area: Area }) {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      password: "",
      tenantSlug: ""
    }
  });

  const submit = form.handleSubmit(async (values) => {
    setServerError(null);
    setIsSubmitting(true);

    try {
      const payload = {
        email: values.email,
        password: values.password
      };

      const headers: Record<string, string> = {};
      if (values.tenantSlug) {
        headers["X-Tenant-Slug"] = values.tenantSlug;
      }

      const response = await apiRequest<{
        access_token?: string;
        refresh_token?: string;
        token?: string;
        user?: User;
      }>(area === "platform" ? endpoints.platform.auth.login : endpoints.app.auth.login, {
        method: "POST",
        body: JSON.stringify(payload),
        headers
      });

      const token = response.access_token ?? response.token ?? "";
      if (!token) {
        throw new Error("Token absent dans la réponse");
      }

      setSession({
        area,
        token,
        refreshToken: response.refresh_token ?? null,
        user:
          response.user ?? {
            id: "local",
            email: values.email,
            permissions: ["*"]
          },
        tenantSlug: values.tenantSlug || null
      });

      router.push(area === "platform" ? "/platform/dashboard" : "/app/dashboard");
    } catch (error) {
      setServerError(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setIsSubmitting(false);
    }
  });

  return (
    <Card className="mx-auto w-full max-w-md shadow-glow">
      <CardHeader>
        <CardTitle>{area === "platform" ? "Platform Admin" : "Tenant App"}</CardTitle>
        <CardDescription>
          {area === "platform"
            ? "Connexion super admin au socle Dymo SaaS Core."
            : "Connexion de l'espace client/tenant du core."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Email</label>
            <Input type="email" placeholder="admin@dymo.io" {...form.register("email")} />
            {form.formState.errors.email ? <p className="text-sm text-rose-600">{form.formState.errors.email.message}</p> : null}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Mot de passe</label>
            <Input type="password" placeholder="••••••••" {...form.register("password")} />
            {form.formState.errors.password ? <p className="text-sm text-rose-600">{form.formState.errors.password.message}</p> : null}
          </div>
          {area === "app" ? (
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Tenant slug</label>
              <Input placeholder="acme" {...form.register("tenantSlug")} />
              {form.formState.errors.tenantSlug ? <p className="text-sm text-rose-600">{form.formState.errors.tenantSlug.message}</p> : null}
            </div>
          ) : null}
          {serverError ? <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{serverError}</p> : null}
          <Button className="w-full" type="submit" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Se connecter
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

