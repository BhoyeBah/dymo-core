import { formatCurrency, formatDate } from "@/lib/utils";

export function DateFormatter({ value }: { value?: string | number | Date }) {
  return <>{value ? formatDate(value) : "—"}</>;
}

export function MoneyFormatter({ value, currency = "EUR" }: { value?: number; currency?: string }) {
  return <>{typeof value === "number" ? formatCurrency(value, currency) : "—"}</>;
}

