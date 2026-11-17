# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies first (cached layer).
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Copy source and build.
COPY . .
RUN npm run build

# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:alpine AS runtime

# Replace the default nginx config with ours.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built assets from the build stage.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
