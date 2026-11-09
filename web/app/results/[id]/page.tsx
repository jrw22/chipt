import type { Metadata } from "next";

import { ResultDetailView } from "@/components/results/result-detail-view";

export const metadata: Metadata = { title: "Result" };

export default async function ResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ResultDetailView id={Number(id)} />;
}
