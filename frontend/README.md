# Agent Template frontend

Use Node.js 24.x as pinned in the repository root `.nvmrc`. From the repository root:

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

The Vite development server is available at `http://127.0.0.1:5173`. Create a production build with `npm run build`.

## Generated API types

The backend owns the API schema. After updating it from `backend/`, regenerate
the frontend types from the repository root:

```bash
cd frontend
npm run generate:api
```

Commit both the updated `openapi/openapi.json` contract and generated
`frontend/src/generated/Api.ts`. Do not edit the generated file by hand.

## Quality checks

Run from `frontend/`:

```bash
npm run lint
npm run typecheck
npm test
npm audit --audit-level=low
npm run build
```
