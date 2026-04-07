FROM node:18-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:18-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=https://api.datacenter.photog.art/api/v1
ARG INTERNAL_API_BASE_URL=http://fastapi:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV INTERNAL_API_BASE_URL=${INTERNAL_API_BASE_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3210
ARG NEXT_PUBLIC_API_BASE_URL=https://api.datacenter.photog.art/api/v1
ARG INTERNAL_API_BASE_URL=http://fastapi:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV INTERNAL_API_BASE_URL=${INTERNAL_API_BASE_URL}
COPY --from=builder /app ./
RUN npm prune --omit=dev
EXPOSE 3210
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3210"]
