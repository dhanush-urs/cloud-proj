FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@10.6.1 --activate

# ── Dependency stage ────────────────────────────────────────────────────────
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

# ── Build stage ─────────────────────────────────────────────────────────────
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# SERVER_API_BASE_URL must be set at build time so Next.js rewrites work.
# Railway: set this as a build-time env variable pointing to your backend service.
ARG SERVER_API_BASE_URL=http://localhost:8000
ENV SERVER_API_BASE_URL=${SERVER_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN pnpm build

# ── Production runner ────────────────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy only the standalone output
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Railway injects PORT at runtime
EXPOSE 3000

# next start reads PORT from environment automatically
CMD ["node", "server.js"]