import { ReactNode } from "react";
import { PageHeader } from "@/components/common/page-header";
import { Card, CardContent } from "@/components/ui/card";

export function SectionPage({
  title,
  description,
  children,
  actions
}: {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="space-y-6">
      <PageHeader title={title} description={description} actions={actions} />
      {children}
    </div>
  );
}

export function SectionCard({ children }: { children: ReactNode }) {
  return (
    <Card>
      <CardContent className="p-6">{children}</CardContent>
    </Card>
  );
}

