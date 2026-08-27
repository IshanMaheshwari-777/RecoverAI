# Dashboard

React + Vite + Tailwind v4. No chart library — the Sankey, funnel, and bar
breakdowns are hand-drawn SVG/CSS against the design tokens in `src/index.css`
(categorical slots taken from the validated data-viz reference palette).

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api → :8000
npm run build    # emits to ../src/revenue_recovery/api/static  (served by `revenue-recovery serve`)
npm run lint     # tsc --noEmit
```

Run the API separately during development:

```bash
revenue-recovery serve      # from the repo root
```

State is TanStack Query over a tiny fetch client (`src/api.ts`); types in
`src/types.ts` mirror `revenue_recovery.domain.results.PipelineReport`.
