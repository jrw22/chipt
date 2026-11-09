"use client";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Sticky bar that appears once the user has ticked or unticked results. */
export function ClaimBar({
  claimCount,
  unclaimCount,
  saving,
  onSave,
  onDiscard,
}: {
  claimCount: number;
  unclaimCount: number;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
}) {
  const total = claimCount + unclaimCount;
  if (total === 0 && !saving) return null;

  const summary = [
    claimCount && `${claimCount} to add`,
    unclaimCount && `${unclaimCount} to remove`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      role="region"
      aria-label="Unsaved changes"
      className="fixed inset-x-0 bottom-4 z-30 flex justify-center px-4 animate-in fade-in slide-in-from-bottom-4"
    >
      <div className="flex w-full max-w-xl items-center gap-3 rounded-xl border bg-popover p-3 pl-4 shadow-lg">
        <p className="min-w-0 flex-1 text-sm">
          <span className="font-medium">Your results:</span>{" "}
          <span className="text-muted-foreground">{summary || "saving…"}</span>
        </p>
        <Button variant="ghost" onClick={onDiscard} disabled={saving}>
          Discard
        </Button>
        <Button onClick={onSave} disabled={saving || total === 0}>
          {saving ? <Loader2 className="animate-spin" /> : null}
          Save changes
        </Button>
      </div>
    </div>
  );
}
