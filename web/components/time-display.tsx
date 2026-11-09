import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ResultOut } from "@/lib/api/client";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";

const NOTES: Record<ResultOut["time_source"], string | null> = {
  chip: null,
  gun: "Gun time: this race didn't publish chip times, so this is measured from the start gun.",
  unspecified: "The race published a single time without saying whether it's chip or gun time.",
};

/** A result's time, with a small marker when it isn't a chip time. */
export function TimeDisplay({
  seconds,
  source,
  className,
}: {
  seconds: number;
  source: ResultOut["time_source"];
  className?: string;
}) {
  const note = NOTES[source];
  return (
    <span className={cn("inline-flex items-baseline gap-1 font-mono tabular-nums", className)}>
      {formatDuration(seconds)}
      {note ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="cursor-help rounded font-sans text-[10px] font-medium tracking-wide text-muted-foreground uppercase underline decoration-dotted underline-offset-2"
            >
              {source === "gun" ? "gun" : "time"}
              <span className="sr-only"> ({note})</span>
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-64">{note}</TooltipContent>
        </Tooltip>
      ) : null}
    </span>
  );
}
