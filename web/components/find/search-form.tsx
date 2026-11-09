"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { FilterCombobox } from "@/components/filter-combobox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Discipline } from "@/lib/api/client";
import { type SearchParams, useFilters } from "@/lib/api/hooks";
import { formatDiscipline } from "@/lib/format";

/** Name (required) plus four optional filters. Submits to the URL via `onSearch`. */
export function SearchForm({
  initial,
  onSearch,
}: {
  initial: SearchParams | null;
  onSearch: (params: SearchParams) => void;
}) {
  const filters = useFilters();
  const [name, setName] = useState(initial?.name ?? "");
  const [discipline, setDiscipline] = useState<string | undefined>(initial?.discipline);
  const [provider, setProvider] = useState<string | undefined>(initial?.provider);
  const [race, setRace] = useState<string | undefined>(initial?.race);
  const [ageGroup, setAgeGroup] = useState<string | undefined>(initial?.age_group);

  const f = filters.data;
  const loading = filters.isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!name.trim()) return;
        onSearch({
          name: name.trim(),
          discipline: discipline as Discipline | undefined,
          provider,
          race,
          age_group: ageGroup,
        });
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="name">Your name</Label>
        <div className="flex gap-2">
          <Input
            id="name"
            name="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Jane Smith"
            autoComplete="name"
            required
            className="h-9"
          />
          <Button type="submit" size="lg" className="h-9 px-4" disabled={!name.trim()}>
            <Search />
            Search
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Spelling doesn&apos;t need to be exact. Matches are ranked by how closely the name fits.
        </p>
      </div>
      <fieldset className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <legend className="sr-only">Filters</legend>
        <div className="space-y-1.5">
          <Label htmlFor="f-discipline" className="text-xs text-muted-foreground">
            Discipline
          </Label>
          <FilterCombobox
            id="f-discipline"
            label="Discipline"
            disabled={loading}
            value={discipline}
            onChange={setDiscipline}
            options={(f?.disciplines ?? []).map((d) => ({ value: d, label: formatDiscipline(d) }))}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-provider" className="text-xs text-muted-foreground">
            Results provider
          </Label>
          <FilterCombobox
            id="f-provider"
            label="Provider"
            disabled={loading}
            value={provider}
            onChange={setProvider}
            options={(f?.providers ?? []).map((p) => ({ value: p.slug, label: p.name }))}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-race" className="text-xs text-muted-foreground">
            Race
          </Label>
          <FilterCombobox
            id="f-race"
            label="Race"
            disabled={loading}
            value={race}
            onChange={setRace}
            options={(f?.races ?? []).map((r) => ({ value: r, label: r }))}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-age" className="text-xs text-muted-foreground">
            Age group
          </Label>
          <FilterCombobox
            id="f-age"
            label="Age group"
            disabled={loading}
            value={ageGroup}
            onChange={setAgeGroup}
            options={(f?.age_groups ?? []).map((a) => ({ value: a, label: a }))}
          />
        </div>
      </fieldset>
    </form>
  );
}
