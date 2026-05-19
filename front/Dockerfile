FROM node:18-alpine AS builder
WORKDIR /app

# 패키지 파일만 먼저 복사해서 설치 (도커 캐시 활용)
COPY package.json package-lock.json ./
RUN npm install

# 나머지 모든 소스코드 복사 후 압축(빌드)
COPY . .
RUN npm run build
# (주의: Vite를 쓰셨다면 npm run build 결과물이 'dist' 폴더에 생기지만,
# 아까 CRA 방식을 쓰셨으므로 'build' 폴더에 생성됩니다.)

# ==========================================
# 2단계: 서비스 (가볍고 빠른 Nginx 웹 서버 환경)
# ==========================================
FROM nginx:alpine

# 1단계에서 완성된 /app/build 폴더의 결과물만 쏙 빼와서 Nginx 서빙 폴더로 복사
COPY --from=builder /app/build /usr/share/nginx/html

# Nginx의 기본 포트인 80번 개방
EXPOSE 80

# Nginx 실행
CMD ["nginx", "-g", "daemon off;"]