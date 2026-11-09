# 0014. Entra External ID tenant created through the Azure API

- Status: accepted
- Date: 2026-11-08

## Context

Real sign-in needs an Entra External ID (CIAM) tenant with an API registration,
a SPA registration and a sign-up/sign-in flow. The previous tenant had been
deleted.

## Decision

- Created `agenttemplate.onmicrosoft.com` ("Agent Template") as an ARM resource
  of type `Microsoft.AzureActiveDirectory/ciamDirectories` in the resource group
  `rg-agent-template-auth`. External ID is free up to a monthly active user
  allowance, so it adds no fixed cost.
- Inside the tenant, through Microsoft Graph: an API registration with the
  delegated scope `chat.use` (v2 access tokens), a SPA registration with the
  redirect URIs `http://127.0.0.1:5173/auth/callback` and the `dev` web app
  `/auth/callback`, admin consent for the scope, and an email-and-password
  sign-up/sign-in flow bound to the SPA.
- The API validates tokens with `OIDC_ISSUER`, `OIDC_DISCOVERY_URL`,
  `OIDC_AUDIENCE` (the API application ID) and `OIDC_REQUIRED_SCOPE=chat.use`,
  passed to the Container App through Terraform variables. The SPA build gets
  `VITE_ENTRA_AUTHORITY`, `VITE_ENTRA_CLIENT_ID` and `VITE_API_SCOPES` from
  GitHub repository variables (public values, not secrets).
- Created imperatively, not with Terraform: the `azuread` provider does not
  cover External ID user flows well, and the simplest thing is to record the
  steps and the resulting names.

## Consequences

- Real sign-up and sign-in become testable against Azure.
- The tenant and registrations are not in Terraform state; recreating them
  means repeating the documented steps.
- The local loopback sign-in (`VITE_LOCAL_SIGNIN_URL`) stays available for
  offline development and must not be combined with `VITE_ENTRA_*`.
