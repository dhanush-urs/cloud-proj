FROM node:22-alpine

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.6.1 --activate

COPY package.json ./
RUN pnpm install

COPY . .

EXPOSE 3000

CMD ["pnpm", "dev"]