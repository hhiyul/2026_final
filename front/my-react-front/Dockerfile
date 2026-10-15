# ==========================================
# 1단계: Node.js 빌드 (Vite 8 지원을 위해 Node 20 사용)
# ==========================================
FROM node:20-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install
COPY . .

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ==========================================
# 2단계: Nginx 서빙
# ==========================================
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# API calls and protected thumbnails share the frontend's public origin.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY proxy_params /etc/nginx/proxy_params

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
