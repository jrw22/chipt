import type { Metadata } from "next";
import { Suspense } from "react";

import { FindView } from "@/components/find/find-view";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Find results" };

export default function FindPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Find your results"
        description="Search by name across every results provider, then claim the results that are yours."
      />
      {/* FindView reads the URL's search params, which needs a Suspense boundary. */}
      <Suspense>
        <FindView />
      </Suspense>
    </div>
  );
}
