"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { Loader2, Plus } from "lucide-react";
import { apiRequest, safeApiRequest, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { LoadingState, ErrorState, EmptyState } from "@/components/common/feedback";
import { DataTable, StatusBadge } from "@/components/common/data-table";
import { Dialog } from "@/components/ui/dialog";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { SecretFieldMasked } from "@/components/common/secret-field-masked";
import { CopyButton } from "@/components/common/copy-button";

type ResourcePageProps = {
  area: "platform" | "app";
  title: string;
  description: string;
  endpoint?: string;
  canCreate?: boolean;
  detailId?: string;
};

const genericCreateSchema = z.object({
  name: z.string().min(1, "Nom requis"),
  description: z.string().optional(),
  slug: z.string().optional()
});

export function ResourcePage({ area, title, description, endpoint, canCreate, detailId }: ResourcePageProps) {
  const [createOpen, setCreateOpen] = useState(false);

  const query = useQuery({
    queryKey: [area, endpoint, detailId],
    queryFn: async () => {
      if (!endpoint) {
        return { data: null, unavailable: true };
      }

      const target = detailId ? `${endpoint}/${detailId}` : endpoint;
      const response = await safeApiRequest<unknown>(target);

      if (response.error instanceof ApiError && response.error.status === 404) {
        return { data: null, unavailable: true };
      }

      if (response.error) {
        throw response.error;
      }

      return { data: response.data, unavailable: false };
    }
  });

  const rows = useMemo(() => normalizeRows(query.data?.data), [query.data?.data]);

  if (query.isLoading) {
    return <LoadingState label={`Chargement de ${title}...`} />;
  }

  if (query.isError) {
    return <ErrorState description={query.error instanceof Error ? query.error.message : "Erreur de chargement"} retry={() => query.refetch()} />;
  }

  if (query.data?.unavailable) {
    return <EmptyState title="Endpoint non disponible" description={`Le backend ne propose pas encore ${title.toLowerCase()}.`} />;
  }

  const createDialog = canCreate ? (
    <CreateDialog open={createOpen} onOpenChange={setCreateOpen} area={area} endpoint={endpoint} resourceTitle={title} />
  ) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm text-slate-600">{description}</p>
        </div>
        {canCreate ? (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Créer
          </Button>
        ) : null}
      </div>
      {renderTable(rows)}
      {renderSummary(query.data?.data)}
      {createDialog}
    </div>
  );
}

function normalizeRows(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) {
    return data as Array<Record<string, unknown>>;
  }

  if (data && typeof data === "object") {
    const candidate = data as Record<string, unknown>;
    if (Array.isArray(candidate.items)) {
      return candidate.items as Array<Record<string, unknown>>;
    }

    if (Array.isArray(candidate.data)) {
      return candidate.data as Array<Record<string, unknown>>;
    }

    return [candidate];
  }

  return [];
}

function renderTable(rows: Array<Record<string, unknown>>) {
  if (!rows.length) {
    return <EmptyState title="Aucune donnée" description="La ressource est vide ou les filtres ne renvoient aucun résultat." />;
  }

  const first = rows[0];
  const keys = Object.keys(first).slice(0, 5);

  return (
    <DataTable
      rows={rows}
      columns={keys.map((key) => ({
        key,
        header: key.replaceAll("_", " "),
        render: (row) => renderValue((row as Record<string, unknown>)[key])
      }))}
    />
  );
}

function renderValue(value: unknown) {
  if (typeof value === "boolean") {
    return <StatusBadge value={value ? "active" : "inactive"} />;
  }

  if (typeof value === "string" && value.toLowerCase().includes("secret")) {
    return <SecretFieldMasked />;
  }

  if (typeof value === "string" && value.length > 40) {
    return (
      <div className="flex items-center gap-2">
        <span className="max-w-[24rem] truncate">{value}</span>
        <CopyButton value={value} />
      </div>
    );
  }

  return <span>{String(value ?? "—")}</span>;
}

function renderSummary(data: unknown) {
  if (!data || typeof data !== "object") {
    return null;
  }

  return (
    <pre className="overflow-auto rounded-2xl border border-slate-200 bg-slate-950 p-4 text-xs text-slate-100">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function CreateDialog({
  open,
  onOpenChange,
  endpoint,
  resourceTitle,
  area
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  endpoint?: string;
  resourceTitle: string;
  area: "platform" | "app";
}) {
  const form = useForm<z.infer<typeof genericCreateSchema>>({
    resolver: zodResolver(genericCreateSchema),
    defaultValues: {
      name: "",
      description: "",
      slug: ""
    }
  });

  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = form.handleSubmit(async (values) => {
    if (!endpoint) {
      setMessage("Endpoint non disponible");
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      await apiRequest(endpoint, {
        method: "POST",
        body: JSON.stringify(
          Object.fromEntries(
            Object.entries(values).filter(([, value]) => typeof value === "string" && value.trim().length > 0)
          )
        )
      });
      setMessage(`${resourceTitle} créé.`);
      onOpenChange(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setSaving(false);
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Créer ${resourceTitle}`}
      description={`Formulaire générique pour ${area}. Les champs précis dépendront du backend.`}
      footer={
        <Button onClick={submit} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Enregistrer
        </Button>
      }
    >
      <form className="space-y-4" onSubmit={submit}>
        <div className="space-y-2">
          <label className="text-sm font-medium">Nom</label>
          <Input {...form.register("name")} />
          {form.formState.errors.name ? <p className="text-sm text-rose-600">{form.formState.errors.name.message}</p> : null}
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Slug</label>
          <Input {...form.register("slug")} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Description</label>
          <Textarea {...form.register("description")} />
        </div>
        {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      </form>
    </Dialog>
  );
}
