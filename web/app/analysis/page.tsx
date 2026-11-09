import type { Metadata } from "next";
import { Suspense } from "react";

import { AnalysisView } from "@/components/analysis/analysis-view";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Analysis" };

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analysis"
        description="How your times change within one comparison group: same discipline, same distance."
      />
      {/* AnalysisView reads the group from the URL, which needs a Suspense boundary. */}
      <Suspense>
        <AnalysisView />
      </Suspense>
    </div>
  );
}
