# ==========================================
# 1단계: Node.js 빌드 (Vite 8 지원을 위해 Node 20 사용)
# ==========================================
FROM node:20-alpine AS builder
WORKDIR /app

# 패키지 파일 복사 및 설치
COPY package.json package-lock.json* ./
RUN npm install

# 전체 소스코드 복사
COPY . .

# Vite 프로덕션 빌드
RUN npm run build

# ==========================================
# 2단계: Nginx 서빙
# ==========================================
FROM nginx:alpine

# Vite 결과물(dist) 복사
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]