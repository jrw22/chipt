import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/page-header";
import { MyResultsView } from "@/components/results/my-results-view";

export const metadata: Metadata = { title: "My results" };

export default function MyResultsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="My results" description="Every result you've claimed, across all providers." />
      {/* MyResultsView keeps its filter and sort in the URL, which needs a Suspense boundary. */}
      <Suspense>
        <MyResultsView />
      </Suspense>
    </div>
  );
}
