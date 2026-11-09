import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/page-header";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Your personal bests and recent races at a glance." />
      <ComingSoon step="step 4 (analysis + dashboard)" />
    </div>
  );
}
