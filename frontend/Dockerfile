# syntax=docker/dockerfile:1
# Build context: frontend/ (see `make docker-build`).
# VITE_* values are public and baked in at build time; pass them as build args.
FROM node@sha256:a34ab6d7f6f4813f4d0c5469d74685604b962fbdbf5793a7bc7b4998ecb867c8 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
ARG VITE_API_BASE_URL=http://127.0.0.1:8000
ARG VITE_ENTRA_AUTHORITY=
ARG VITE_ENTRA_CLIENT_ID=
ARG VITE_API_SCOPES=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ENTRA_AUTHORITY=$VITE_ENTRA_AUTHORITY \
    VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID \
    VITE_API_SCOPES=$VITE_API_SCOPES
RUN npm run build

FROM nginxinc/nginx-unprivileged@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
# nginx handles SIGQUIT/SIGTERM gracefully; the stop signal lets it drain.
STOPSIGNAL SIGQUIT
