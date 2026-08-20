# ==========================================
# 1단계: 빌드 (Node.js 환경)
# ==========================================
FROM node:18-alpine AS builder
WORKDIR /app

# 패키지 파일만 먼저 복사해서 설치 (도커 레이어 캐시 활용)
COPY package.json package-lock.json* ./
RUN npm install

# 소스코드 복사 후 Vite 프로덕션 빌드 실행
COPY . .
RUN npm run build
# Vite 빌드 결과물은 기본적으로 'dist' 폴더에 생성됩니다.

# ==========================================
# 2단계: 서비스 서빙 (Nginx 웹 서버)
# ==========================================
FROM nginx:alpine

# 1단계에서 완성된 Vite 결과물(/app/dist)을 Nginx 기본 서빙 경로로 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# (선택) React Router(SPA) 새로고침 404 방지용 Nginx 설정 파일이 있다면 주석 해제
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# Nginx 기본 80 포트 노출
EXPOSE 80

# Nginx 포그라운드 실행
CMD ["nginx", "-g", "daemon off;"]