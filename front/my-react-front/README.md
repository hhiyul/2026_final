# 뭐입지 프런트엔드

React/Vite 기반 회원 전용 옷장 UI입니다. `front`는 프런트, `fastapi`는 인증 및 AI 백엔드, `scg`는 게이트웨이입니다.

## 실행

```sh
npm ci
npm run dev
# 기본 개발 프록시: localhost:5173 → localhost:8080 (SCG)
# 다른 주소라면 .env.local에 VITE_API_PROXY_TARGET 지정
```

회원가입 후 로그인하면 본인의 옷장을 자동으로 불러옵니다. 기존에 등록한 계정과 비밀번호도 그대로 사용할 수 있습니다. 사용자 ID를 임의 입력해서 다른 옷장을 여는 기능은 제거했습니다.

## 화면

- 내 옷장 / AI 추천, 라벨별 그룹과 필터, 사진 업로드·미리보기, 상세 이전/다음, 비밀번호 확인 삭제
- 아우터 → 상의 → 하의 → 모자 순서. 새로운 라벨·미분류도 보존
- 그룹 안에서 옷장은 최신 등록순, 추천 결과는 서버 추천 순위순
- AI 추천 예시 버튼은 **쿨톤 / 웜톤**만 제공. 직접 입력도 가능하며 기존 `top_k: 5` 유지
- 옷 추가하기: 라임색 강조 버튼. 모바일에서는 하단 메뉴 위 고정
- 다크모드: 최초 시스템 설정 적용, 이후 사용자가 고른 테마 저장. 로그인 화면·상세·삭제 모달 포함
- 내 정보에서 계정, 테마, 로그아웃 및 접힌 API 응답 데이터 확인

## 인증 및 배포 설정

쿠키는 `HttpOnly`, `SameSite=Lax`이며 브라우저에 인증 토큰을 직접 저장하지 않습니다. Axios의 `withCredentials: true`로 로그인 쿠키를 전송하고 앱을 열 때 `/auth/me`로 확인합니다. 세션 만료 시 로그인 화면으로 돌아갑니다.

Docker Compose는 이 디렉터리를 빌드합니다. 기본 설정은 별도 API URL 없이 같은 호스트에서 동작합니다. 로컬 Vite는 요청을 `localhost:8080` 게이트웨이에 전달하고, Docker Nginx는 게이트웨이에 요청을 프록시합니다. 브라우저와 API 주소를 같은 origin으로 유지하여 인증 쿠키와 보호된 옷 썸네일이 함께 동작합니다.

로컬 HTTP 기준:

```dotenv
SESSION_COOKIE_SECURE=false
# 필요할 때만 브라우저가 접근 가능한 API origin을 지정
# VITE_API_BASE_URL=http://localhost:8080
```

다른 컴퓨터/서버에서는 `localhost` 대신 **브라우저에서 접근 가능한 같은 호스트명**을 사용하고, 루트 `.env`의 `FRONTEND_ORIGINS`에 프런트 주소(origin)를 쉼표로 구분해 지정하세요. 이 값은 SCG와 FastAPI 양쪽에 전달됩니다. `localhost`와 `127.0.0.1`을 섞지 마세요. 서로 다른 사이트의 도메인을 사용하는 배포는 기본 쿠키 정책에서 지원하지 않습니다. 같은 호스트의 게이트웨이를 통해 서비스하세요.

HTTPS 배포에서는 `SESSION_COOKIE_SECURE=true`를 사용하세요. `VITE_API_BASE_URL` 기본값은 비워 둡니다. 브라우저는 프런트 origin에 요청하고 Vite 개발 프록시 또는 Docker Nginx가 SCG로 전달합니다. Nginx는 Docker DNS를 이용해 SCG를 실행 시점에 찾으므로 컨테이너 시작 순서에 의존하지 않습니다. 로컬에서 Vite와 SCG가 다른 origin일 경우 실제 프런트 origin을 `FRONTEND_ORIGINS`에 포함해야 합니다.

최초 인증 기능 도입 시에는 프런트와 백엔드, SCG를 함께 적용해야 합니다:

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

## 이번 UX 변경 배포

이번 변경은 프론트만 수정합니다. 인증 백엔드와 SCG가 이미 정상 동작한다면 저장소 루트에서 프론트만 재빌드하세요.

```sh
git switch feat/auth-dark-mode
git pull --ff-only origin feat/auth-dark-mode
docker compose up -d --build --no-deps react-front
```

SCG 소스나 라우팅 설정을 바꾸지 않았으므로 JAR 초기화/재빌드는 필요 없습니다.
현재 SCG Dockerfile은 기존 `build/libs/*-SNAPSHOT.jar`를 복사합니다. 별도로 SCG 설정을 수정하거나 기존 로그인 405가 계속 발생하는 환경이라면 최신 JAR을 만든 뒤 게이트웨이를 재배포하세요(Windows PowerShell).

```powershell
cd scg
.\gradlew.bat clean bootJar
cd ..
docker compose up -d --build --no-deps spring-gateway
```

## UX 참고 및 적용

- [Acloset](https://www.acloset.app/ko/): 사진 등록에서 옷장·추천으로 이어지는 흐름 → 항상 접근 가능한 옷 추가 버튼, 미리보기, 처리 상태.
- [Whering](https://www.whering.co/): 보유 옷을 발견하는 경험 → 사진 중심 목록, 과도한 소개 배너 제거.
- [Indyx](https://www.myindyx.com/how-it-works/): 옷장 카탈로그와 속성 필터 → 라벨별 그룹, 개수 표시, 가로 스크롤 필터.

모바일은 2열 목록·하단 내 옷장/AI 추천/내 정보 메뉴·하단 상세창을 사용합니다. PC는 상단 메뉴와 3~5열 목록을 사용합니다. 다크모드 및 기존 테마 선택은 유지됩니다.

서버 API, 인증 쿠키 이름, 추천 요청(`top_k: 5`)은 변경하지 않습니다. 서버가 전체 5개를 반환하면 그대로 5개, 라벨별 결과를 반환하면 해당 결과 전체를 표시합니다. 라벨별 최대 5개 선정은 별도의 백엔드 변경이 필요합니다.
