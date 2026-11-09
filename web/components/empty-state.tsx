import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

/** Dashed card for "nothing here yet" / "no matches" states. */
export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: LucideIcon;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
        <Icon className="size-8 text-muted-foreground" aria-hidden />
        <h2 className="font-medium">{title}</h2>
        {children ? <div className="max-w-md text-sm text-muted-foreground">{children}</div> : null}
        {action ? <div className="pt-2">{action}</div> : null}
      </CardContent>
    </Card>
  );
}
