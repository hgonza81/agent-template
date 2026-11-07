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

## Sign-in (Entra External ID, MSAL)

The app uses `@azure/msal-react` with Authorization Code + PKCE as a public
client: there is no client secret, and the app never handles passwords. MSAL
keeps tokens in `sessionStorage`; the app stores only the intended route
(sanitized to same-origin paths) there.

- `/` is the public start page with **Sign in** and **Create account**
  (sign-up uses the `create` prompt).
- `/auth/callback` is the redirect URI (register
  `http://127.0.0.1:5173/auth/callback` on the SPA registration, plus the
  logout URI `http://127.0.0.1:5173/`). It waits for MSAL to finish and then
  returns the user to the route they asked for.
- `/chat` is behind `ProtectedRoute`. Unauthenticated visitors are sent to `/`
  and returned after sign-in. This is a UX guard only; FastAPI enforces
  authorization.
- `useAuth().getAccessToken()` acquires the API token silently and falls back
  to a redirect when interaction is required.

Tenant values are pending provisioning. Set `VITE_ENTRA_AUTHORITY`,
`VITE_ENTRA_CLIENT_ID`, and `VITE_API_SCOPES` together in `frontend/.env`, or
leave all three blank to run with sign-in disabled. Partial or invalid values
fail `npm run dev` and `npm run build`. Tests use a fake auth context and a
mocked MSAL, so they never contact a tenant.

### Account entry points

The start page offers **Create a free account**, **Sign in**, and a password
reset entry. All three redirect to Entra External ID; this app has no password
fields and never stores or resets passwords. Entra's sign-in page hosts the
"forgot password" option, so the reset entry sends the user there with
instructions. The Entra user-flow wiring (sign-up, sign-in, and self-service
password reset enabled on the tenant) is **unverified** until the tenant is
provisioned; confirm it before real sign-up acceptance tests. The page has a
skip link, a `main` landmark, a labelled account region, and entry points that
are disabled while the session state is loading.
