import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "My results" };

export default function MyResultsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="My results" description="Every result you've claimed, across all providers." />
      <ComingSoon step="step 3 (my results + detail)" />
    </div>
  );
}
