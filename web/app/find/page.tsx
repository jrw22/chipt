import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Find results" };

export default function FindPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Find your results" description="Search by name, then claim the results that are yours." />
      <ComingSoon step="step 2 (find & claim)" />
    </div>
  );
}
