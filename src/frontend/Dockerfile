# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Stage 1: Build TanStack Start / Nitro application
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder

# Enable pnpm package manager via Corepack
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

# Cache package installation layer
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile || pnpm install

# Build arguments for frontend configuration (can be overridden at build time)
ARG VITE_BACKEND_URL=""
ARG VITE_API_URL=""
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL \
    VITE_API_URL=$VITE_API_URL

# Copy frontend source code
COPY . .

# Build the production server and client assets via Nitro
RUN pnpm run build

# ------------------------------------------------------------------------------
# Stage 2: Minimal Production Runner
# ------------------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

# Copy the standalone Nitro server bundle
COPY --from=builder /app/.output ./.output

# Expose frontend application port
EXPOSE 3000

# Start the Nitro production server
CMD ["node", ".output/server/index.mjs"]
