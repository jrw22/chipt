import { Card, CardContent } from "@/components/ui/card";

/** Placeholder body for pages built in later V1 steps (see docs/v1_plan.md). */
export function ComingSoon({ step }: { step: string }) {
  return (
    <Card className="border-dashed">
      <CardContent className="py-10 text-center text-sm text-muted-foreground">
        Coming in V1 phase 1, {step}.
      </CardContent>
    </Card>
  );
}
