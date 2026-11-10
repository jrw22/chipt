/**
 * Typed client for the Chipt FastAPI backend. The browser talks only to the API, never the DB.
 *
 * Types come from `schema.d.ts`, generated from FastAPI's OpenAPI schema (`npm run gen:api`),
 * so the Pydantic models in `src/chipt/schemas.py` stay the single source of truth.
 */
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export const api = createClient<paths>({ baseUrl: API_BASE_URL });

type Schemas = components["schemas"];
export type ResultOut = Schemas["ResultOut"];
export type SearchResultOut = Schemas["SearchResultOut"];
export type ResultDetailOut = Schemas["ResultDetailOut"];
export type AnalysisOut = Schemas["AnalysisOut"];
export type AnalysisPoint = Schemas["AnalysisPoint"];
export type ComparisonGroup = Schemas["ComparisonGroup"];
export type FiltersOut = Schemas["FiltersOut"];
export type Discipline = Schemas["Discipline"];
export type ManualResultIn = Schemas["ManualResultIn"];

/** A failure worth showing the user: API unreachable, or a non-2xx response. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

/** Await an openapi-fetch call and return its data, or throw an ApiError. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call;
  } catch {
    throw new ApiError(`Can't reach the Chipt API at ${API_BASE_URL}. Is it running?`);
  }
  if (!result.response.ok) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) // FastAPI validation errors (422): one line per field
          ? detail
              .map((d: { loc?: unknown[]; msg?: string }) => `${String(d.loc?.at(-1) ?? "input")}: ${(d.msg ?? "invalid").replace(/^Value error, /, "")}`)
              .join("; ")
          : `Request failed (${result.response.status})`;
    throw new ApiError(message, result.response.status);
  }
  return result.data as T;
}
