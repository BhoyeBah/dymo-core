import { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/feedback";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
}

export function DataTable<T extends { id?: string }>({
  rows,
  columns,
  emptyTitle = "Aucune ligne",
  emptyDescription
}: {
  rows: T[];
  columns: Column<T>[];
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  if (!rows.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {columns.map((column) => (
                  <th key={column.key} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {rows.map((row, index) => (
                <tr key={row.id ?? index} className="transition hover:bg-slate-50/80">
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-3 text-sm text-slate-700">
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

export function StatusBadge({ value }: { value?: string }) {
  const normalized = (value ?? "unknown").toLowerCase();
  const classes =
    normalized.includes("active") || normalized.includes("success") || normalized.includes("paid")
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : normalized.includes("pending") || normalized.includes("trial")
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : normalized.includes("error") || normalized.includes("failed") || normalized.includes("suspended")
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-slate-200 bg-slate-100 text-slate-700";

  return <Badge className={classes}>{value ?? "unknown"}</Badge>;
}

