# Chipt web (V1)

The Next.js frontend for Chipt. It talks to the FastAPI backend over HTTP only. See the
repository [README](../README.md) for setup, and [docs/v1_plan.md](../docs/v1_plan.md) for the plan.

```bash
nvm use            # Node 22 (.nvmrc)
npm install
npm run dev        # http://localhost:3000; needs the API on http://127.0.0.1:8000
npm run check      # typecheck + lint + build
npm run gen:api    # regenerate lib/api/schema.d.ts from the API's OpenAPI schema
```

- `app/`: routes (Dashboard, Find results, My results, Analysis)
- `components/ui/`: shadcn/ui components (add more with `npx shadcn@latest add <name>`)
- `lib/api/`: generated types, typed client and TanStack Query hooks
- Theme tokens (neutral base and orange accent, light/dark) live in `app/globals.css`
