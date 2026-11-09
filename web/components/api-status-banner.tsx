"use client";

import { CircleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { API_BASE_URL } from "@/lib/api/client";
import { useHealth } from "@/lib/api/hooks";

/** Shown under the header when the FastAPI backend can't be reached. */
export function ApiStatusBanner() {
  const { isError } = useHealth();
  if (!isError) return null;
  return (
    <div className="mx-auto max-w-6xl px-4 pt-4 sm:px-6">
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Can&apos;t reach the Chipt API</AlertTitle>
        <AlertDescription>
          <p>
            Nothing can load until it&apos;s running at <code>{API_BASE_URL}</code>. Start it with{" "}
            <code className="break-all">uv run uvicorn chipt.api.main:app --app-dir src --reload</code>
          </p>
        </AlertDescription>
      </Alert>
    </div>
  );
}
