"use client";

import { toast } from "sonner";

import { useSetClaimed } from "@/lib/api/hooks";

/** Unclaim straight away, with an "Undo" action on the toast instead of a confirm dialog. */
export function useUnclaimWithUndo() {
  const setClaimed = useSetClaimed();
  const unclaim = (id: number, label: string) =>
    setClaimed.mutate(
      { id, claimed: false },
      {
        onSuccess: () =>
          toast(`Removed ${label} from your results.`, {
            duration: 10_000, // long enough to notice and undo
            action: { label: "Undo", onClick: () => setClaimed.mutate({ id, claimed: true }) },
          }),
        onError: (e) => toast.error(`Couldn't remove it: ${e.message}`),
      },
    );
  return { unclaim, pending: setClaimed.isPending };
}
