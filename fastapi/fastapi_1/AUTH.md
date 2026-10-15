# 회원가입과 세션 인증

## API

| 경로 | 입력 | 동작 |
| --- | --- | --- |
| `POST /users` | `{user_id, password}` | 회원가입. ID 앞뒤 공백 제거, 중복 409, 비밀번호 8~128자 |
| `POST /auth/login` | `{user_id, password}` | 비밀번호 검증 후 HttpOnly 세션 쿠키 발급 |
| `GET /auth/me` | 세션 쿠키 | 현재 `{user_id}` 반환, 미인증/만료 401 |
| `POST /auth/logout` | 세션 쿠키 | 서버 세션 폐기 및 쿠키 제거 |
| `GET /garments` | 세션 쿠키, 선택적 category | 로그인한 계정의 옷장 |
| `POST /garments` | 세션 쿠키, multipart file | 로그인한 계정으로 저장 |
| `POST /recommend` | 세션 쿠키, `{query, category?, top_k?}` | 로그인한 계정의 옷만 추천 |
| `DELETE /garments/{id}` | 세션 쿠키, `{password}` | 소유권·비밀번호 확인 후 삭제 |
| `GET /thumbnails/{filename}` | 세션 쿠키 | 본인 옷의 이미지만 반환 |
| `POST /analyze` | 세션 쿠키, multipart file | 인증 후 분석 |

옷 관련 요청의 `user_id`는 더 이상 신뢰하거나 필요로 하지 않습니다. 이전 클라이언트가 보내더라도 세션의 계정을 사용합니다. 로그인 전 요청은 401입니다. 잘못된 삭제 비밀번호는 세션 만료와 구분하기 위해 403입니다. `/ui` 테스트 페이지에도 회원가입·로그인·로그아웃 버튼을 추가했습니다.

## 저장 및 기존 데이터

- 기존 users의 Argon2 password_hash와 의류 user_id를 그대로 사용합니다. 기존 계정은 재가입할 필요가 없습니다.
- 로그인하지 않고 등록했던 옷에는 대응하는 users 레코드가 없을 수 있습니다. 이러한 옷장이 이미 있는 ID로 새 계정을 만들어 기존 데이터를 가져가는 것을 차단합니다. 해당 ID는 다른 ID로 가입하거나, 관리자가 소유자를 확인해 기존 데이터를 이관해야 합니다.
- 신규 sessions 컬렉션에 랜덤 토큰의 SHA-256 해시와 계정, 만료 시각을 저장합니다. 원문 토큰은 DB에 저장하지 않습니다.
- 세션은 발급 후 7일 유효합니다. TTL 인덱스로 정리하고, 매 요청에도 만료 여부를 확인합니다.
- 두 FastAPI 노드는 같은 MongoDB를 사용하므로 별도 서명 키나 고정 라우팅 없이 로그인 상태와 로그아웃을 공유합니다.
- users의 고유 ID 인덱스와 sessions의 TTL 인덱스는 시작 시 생성합니다. 인덱스 또는 DB 연결 실패 시 서버 시작을 중단합니다.
- 사용자 데이터와 썸네일 응답은 Cache-Control: no-store를 사용합니다.

## 환경변수 및 게이트웨이

- `FRONTEND_ORIGINS`: 허용하는 브라우저 origin을 쉼표로 구분합니다. 기본값은 localhost 및 127.0.0.1의 로컬 개발 주소입니다. Docker Compose에서 SCG와 FastAPI 두 노드에 동일하게 전달합니다.
- `SESSION_COOKIE_SECURE`: 로컬 HTTP는 false, HTTPS 배포는 true. 쿠키는 항상 HttpOnly, SameSite=Lax입니다.
- 요청의 Origin이 허용 목록 밖이면 변경 요청을 거절합니다. 프런트와 API는 같은 사이트에서 제공해야 합니다.
- SCG는 `/auth/**`를 FastAPI에 전달하고 CORS credentials를 허용합니다. `/thumbnails/**`도 기존 두 노드 라우트를 통해 인증 후 전달됩니다.
- 새 JWT 비밀키나 별도 인증 서버는 필요하지 않습니다. 기존 MONGO_DETAILS 등은 그대로 유지합니다.

## 테스트

모델·GPU 없이 실제 라우트 및 인증 로직을 검증합니다. MongoDB 저장소와 추론만 대체합니다.

```sh
python -m pip install -r requirements-test.txt
python -m pytest tests -q
```

검증 항목: 회원가입/중복/잘못된 입력, 기존 해시 호환, 로그인 실패, HttpOnly 쿠키, 노드 간 세션 공유, 토큰 교체, 로그아웃/만료, 미인증 접근, 타 계정 조회·저장·추천·삭제·이미지 접근 방지, 삭제 비밀번호, Origin/CORS.
