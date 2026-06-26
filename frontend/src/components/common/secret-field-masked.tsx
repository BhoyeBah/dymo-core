import { EyeOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function SecretFieldMasked({ label = "Secret masqué" }: { label?: string }) {
  return (
    <Badge className="gap-2 border-amber-200 bg-amber-50 text-amber-800">
      <EyeOff className="h-3.5 w-3.5" />
      {label}
    </Badge>
  );
}

