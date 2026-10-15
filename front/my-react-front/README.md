# wearly 프런트엔드

React/Vite 기반 회원 전용 옷장 UI입니다. `front`는 프런트, `fastapi`는 인증 및 AI 백엔드, `scg`는 게이트웨이입니다.

## 실행

```sh
npm ci
# .env.local: VITE_API_BASE_URL=http://localhost:8080
npm run dev
```

회원가입 후 로그인하면 본인의 옷장을 자동으로 불러옵니다. 기존에 등록한 계정과 비밀번호도 그대로 사용할 수 있습니다. 사용자 ID를 임의 입력해서 다른 옷장을 여는 기능은 제거했습니다.

## 화면

- 내 옷장 / AI 추천, 라벨별 그룹과 필터, 사진 업로드·미리보기, 상세 이전/다음, 비밀번호 확인 삭제
- 아우터 → 상의 → 하의 → 모자 순서. 새로운 라벨·미분류도 보존
- 그룹 안에서 옷장은 최신 등록순, 추천 결과는 서버 추천 순위순
- AI 추천 예시 버튼은 **쿨톤 / 웜톤**만 제공. 직접 입력도 가능하며 기존 `top_k: 5` 유지
- 옷 추가하기: 대비가 높은 큰 노란 버튼. 모바일에서는 화면 하단 고정
- 다크모드: 최초 시스템 설정 적용, 이후 사용자가 고른 테마 저장. 로그인 화면·상세·삭제 모달 포함
- API 응답 JSON은 하단 접힌 영역에서 확인

## 인증 및 배포 설정

쿠키는 `HttpOnly`, `SameSite=Lax`이며 브라우저에 인증 토큰을 직접 저장하지 않습니다. Axios의 `withCredentials: true`로 로그인 쿠키를 전송하고 앱을 열 때 `/auth/me`로 확인합니다. 세션 만료 시 로그인 화면으로 돌아갑니다.

Docker Compose는 이 디렉터리를 빌드합니다. 로컬 기준:

```dotenv
VITE_API_BASE_URL=http://localhost:8080
SESSION_COOKIE_SECURE=false
```

다른 컴퓨터/서버에서는 `localhost` 대신 **브라우저에서 접근 가능한 같은 호스트명**을 사용하고, 루트 `.env`의 `FRONTEND_ORIGINS`에 프런트 주소(origin)를 쉼표로 구분해 지정하세요. 이 값은 SCG와 FastAPI 양쪽에 전달됩니다. `localhost`와 `127.0.0.1`을 섞지 마세요. 서로 다른 사이트의 도메인을 사용하는 배포는 기본 쿠키 정책에서 지원하지 않습니다. 같은 호스트의 게이트웨이를 통해 서비스하세요.

HTTPS 배포에서는 `SESSION_COOKIE_SECURE=true`를 사용하세요. `VITE_API_BASE_URL`을 생략하면 현재 origin을 사용하므로 SCG의 `:8080` 등 API와 프런트가 함께 제공되는 주소로 접속해야 합니다. 프런트 Nginx의 `:80`만 직접 사용하는 경우에는 API 주소를 지정해야 합니다.

프런트와 백엔드, SCG를 함께 적용해야 합니다:

```sh
# 저장소 루트
# API_KEY, MONGO_DETAILS, HF_TOKEN 등 기존 환경변수는 그대로 사용
 docker compose up -d --build
```

## 검증

```sh
npm test
npm run lint
npm run build
```

백엔드 인증 테스트와 배포 설명: `fastapi/fastapi_1/AUTH.md`.
