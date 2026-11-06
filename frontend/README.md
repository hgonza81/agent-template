# Agent Template frontend

Use Node.js 24.x as pinned in the repository root `.nvmrc`. From the
repository root, run `make setup` to create local environment files and install
dependencies, then run `make frontend`. The Vite development server is
available at `http://127.0.0.1:5173`.

## Generated API types

The backend owns the API schema. Run `make api-types` from the repository root
to export the OpenAPI contract and regenerate the frontend types.

Commit both the updated `openapi/openapi.json` contract and generated
`frontend/src/generated/Api.ts`. Do not edit the generated file by hand.

## Quality checks

From the repository root, run `make test-frontend` for frontend tests,
`make check-frontend` for lint, type checking, and a production build, or
`make audit` to scan frontend and backend dependencies. `make check` runs
the full project checks and tests.
