# Agent Template frontend

Use Node.js 24.x as pinned in the repository root `.nvmrc`. From the repository root:

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

The Vite development server is available at `http://127.0.0.1:5173`. Create a production build with `npm run build`.

## Quality checks

Run from `frontend/`:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```
