FROM node:22-alpine

WORKDIR /app

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@10.6.1 --activate

# Copy package files (with wildcard for lockfile to handle if it doesn't exist)
COPY package.json pnpm-lock.yaml* ./

# Install dependencies inside container
RUN pnpm install

# Copy the rest of the app (obeying .dockerignore)
COPY . .

EXPOSE 3000

# Run dev server bound to 0.0.0.0
CMD ["pnpm", "dev", "--host", "0.0.0.0"]