import { AlertTriangle, LockKeyhole, Loader2, SearchX } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function LoadingState({ label = "Chargement..." }: { label?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-6 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label}
      </CardContent>
    </Card>
  );
}

export function ErrorState({ title = "Une erreur est survenue", description, retry }: { title?: string; description?: string; retry?: () => void }) {
  return (
    <Card className="border-rose-200 bg-rose-50/70">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-rose-700">
          <AlertTriangle className="h-5 w-5" />
          {title}
        </CardTitle>
        {description ? <CardDescription className="text-rose-700/80">{description}</CardDescription> : null}
      </CardHeader>
      {retry ? (
        <CardContent>
          <Button onClick={retry}>Réessayer</Button>
        </CardContent>
      ) : null}
    </Card>
  );
}

export function EmptyState({ title = "Aucune donnée", description }: { title?: string; description?: string }) {
  return (
    <Card className="border-dashed border-slate-200 bg-slate-50/70">
      <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
        <SearchX className="h-8 w-8 text-slate-400" />
        <div>
          <p className="font-medium text-slate-900">{title}</p>
          {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function ForbiddenState() {
  return (
    <Card className="border-amber-200 bg-amber-50/80">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-amber-700">
          <LockKeyhole className="h-5 w-5" />
          Accès refusé
        </CardTitle>
        <CardDescription className="text-amber-700/80">Votre session ne possède pas les permissions nécessaires pour ouvrir cette page.</CardDescription>
      </CardHeader>
    </Card>
  );
}

