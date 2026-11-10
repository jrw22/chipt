"use client";

import { ChevronDown, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Discipline, ManualResultIn } from "@/lib/api/client";
import { useAddManualResult } from "@/lib/api/hooks";
import { DISCIPLINES, DISTANCE_LABELS } from "@/lib/distances";
import { formatDiscipline } from "@/lib/format";
import { cn } from "@/lib/utils";

const OTHER = "__other__";
const SINGLE: Discipline[] = ["running", "cycling", "swimming"];
const TIME_RE = /^(\d+:)?\d{1,2}:\d{2}$/;

function Field({ id, label, hint, children, className }: { id: string; label: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

const toInt = (v: string) => (v.trim() ? Number.parseInt(v, 10) : null);
const orNull = (v: string) => v.trim() || null;

/**
 * "Add a result" form for platforms Chipt can't read (e.g. IRONMAN): the owner types in their own
 * result. The API files it under "Manual entry" and claims it straight away.
 */
export function AddResultDialog({ trigger }: { trigger?: React.ReactNode }) {
  const router = useRouter();
  const add = useAddManualResult();
  const [open, setOpen] = useState(false);
  const [more, setMore] = useState(false);
  const [discipline, setDiscipline] = useState<Discipline>("triathlon");
  const [distance, setDistance] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const labels = DISTANCE_LABELS[discipline];
  const other = labels.length === 0 || distance === OTHER;
  const single = SINGLE.includes(discipline);

  function reset() {
    setMore(false);
    setDiscipline("triathlon");
    setDistance("");
    setError(null);
    add.reset();
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const s = (k: string) => String(f.get(k) ?? "");
    const label = other ? s("distance_other").trim() : distance;
    const time = s("chip_time").trim();
    if (!label) return setError("Choose or type a distance.");
    if (!TIME_RE.test(time)) return setError("Enter the time as H:MM:SS (or MM:SS), e.g. 5:31:07.");
    setError(null);

    const km = Number.parseFloat(s("distance_km"));
    const body: ManualResultIn = {
      event_name: s("event_name").trim(),
      event_date: s("event_date"),
      discipline,
      distance_label: label,
      distance_km: single && other && km > 0 ? km : null,
      chip_time: time,
      finisher: true,
      source_platform: orNull(s("source_platform")),
      source_url: orNull(s("source_url")),
      location: orNull(s("location")),
      age_group: orNull(s("age_group")),
      gender: orNull(s("gender")),
      overall_rank: toInt(s("overall_rank")),
      gender_rank: toInt(s("gender_rank")),
      category_rank: toInt(s("category_rank")),
    };
    add.mutate(body, {
      onSuccess: (r) => {
        setOpen(false);
        reset();
        toast.success(`Added ${r.event_name}`, {
          action: { label: "View", onClick: () => router.push(`/results/${r.id}`) },
        });
      },
      onError: (err) => setError(err.message),
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline">
            <Plus /> Add a result
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a result</DialogTitle>
          <DialogDescription>
            For races Chipt can&apos;t read automatically, such as IRONMAN. Copy your result from the results page.
          </DialogDescription>
        </DialogHeader>

        <form id="add-result" className="grid gap-4 sm:grid-cols-2" onSubmit={onSubmit}>
          <Field id="ar-name" label="Race" className="sm:col-span-2">
            <Input id="ar-name" name="event_name" required maxLength={200} placeholder="e.g. IRONMAN 70.3 Weymouth" />
          </Field>
          <Field id="ar-date" label="Date">
            <Input id="ar-date" name="event_date" type="date" required />
          </Field>
          <Field id="ar-discipline" label="Discipline">
            <Select
              value={discipline}
              onValueChange={(v) => {
                setDiscipline(v as Discipline);
                setDistance("");
              }}
            >
              <SelectTrigger id="ar-discipline" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DISCIPLINES.map((d) => (
                  <SelectItem key={d} value={d}>
                    {formatDiscipline(d)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          {labels.length > 0 ? (
            <Field id="ar-distance" label="Distance">
              <Select value={distance} onValueChange={setDistance}>
                <SelectTrigger id="ar-distance" className="w-full">
                  <SelectValue placeholder="Choose…" />
                </SelectTrigger>
                <SelectContent>
                  {labels.map((l) => (
                    <SelectItem key={l} value={l}>
                      {l}
                    </SelectItem>
                  ))}
                  <SelectItem value={OTHER}>Other…</SelectItem>
                </SelectContent>
              </Select>
            </Field>
          ) : null}
          {other ? (
            <Field id="ar-distance-other" label={labels.length ? "Other distance" : "Distance"} hint="Results only compare within the same distance name.">
              <Input id="ar-distance-other" name="distance_other" required maxLength={60} placeholder={single ? "e.g. 25K" : "e.g. Aquabike Sprint"} />
            </Field>
          ) : null}
          {other && single ? (
            <Field id="ar-km" label="Distance (km)" hint="Optional. Used for pace.">
              <Input id="ar-km" name="distance_km" type="number" inputMode="decimal" min="0" step="0.001" />
            </Field>
          ) : null}
          <Field id="ar-time" label="Chip time" hint="H:MM:SS, e.g. 5:31:07">
            <Input id="ar-time" name="chip_time" required inputMode="numeric" placeholder="5:31:07" className="font-mono" />
          </Field>
          <Field id="ar-platform" label="Results published on" hint="Optional, e.g. IRONMAN">
            <Input id="ar-platform" name="source_platform" maxLength={100} />
          </Field>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-2 justify-self-start text-muted-foreground sm:col-span-2"
            aria-expanded={more}
            onClick={() => setMore((m) => !m)}
          >
            <ChevronDown className={cn("transition-transform", more && "rotate-180")} /> More details
          </Button>
          <div className={cn("grid gap-4 sm:col-span-2 sm:grid-cols-3", !more && "hidden")}>
            <Field id="ar-ag" label="Age group">
              <Input id="ar-ag" name="age_group" maxLength={40} placeholder="e.g. M30-34" />
            </Field>
            <Field id="ar-gender" label="Gender">
              <Input id="ar-gender" name="gender" maxLength={40} />
            </Field>
            <Field id="ar-location" label="Location">
              <Input id="ar-location" name="location" maxLength={200} />
            </Field>
            <Field id="ar-overall" label="Overall position">
              <Input id="ar-overall" name="overall_rank" type="number" inputMode="numeric" min="1" />
            </Field>
            <Field id="ar-gender-rank" label="Gender position">
              <Input id="ar-gender-rank" name="gender_rank" type="number" inputMode="numeric" min="1" />
            </Field>
            <Field id="ar-cat-rank" label="Age-group position">
              <Input id="ar-cat-rank" name="category_rank" type="number" inputMode="numeric" min="1" />
            </Field>
            <Field id="ar-url" label="Results link" className="sm:col-span-3">
              <Input id="ar-url" name="source_url" type="url" maxLength={2000} placeholder="https://…" />
            </Field>
          </div>
        </form>

        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <DialogFooter>
          <Button type="submit" form="add-result" disabled={add.isPending}>
            {add.isPending ? "Adding…" : "Add result"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
