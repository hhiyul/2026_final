1. scg 관련 .\gradlew clean bootJar는 반드시 cd로 scg 디렉터리로 이동후 실행
2.  도커 초기화 순서 1. docker compose down 우선 2..\gradlew clean bootJar 실행후 최상위 디렉터리 이동 3. 다시 킬떄는 docker compose up --build -d

3.  scg- 게이트웨이 + 로드벨런서
4.  front - 리엑트 프론트 (나중에 폰웹에서도 테스트 예정)
5.  fastapi - fastapi (추후 수정)

6.  현재 fastapi 서버 2개

7.  남은거 - db 연결 fastapi구조 수정및 프론트 개발
