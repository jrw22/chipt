import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Analysis" };

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analysis"
        description="How your times change within one comparison group (same discipline and distance)."
      />
      <ComingSoon step="step 4 (analysis + dashboard)" />
    </div>
  );
}
