# 1단계: 실행 환경만 가벼운 이미지로 가져오기 (Alpine Linux 기반)
FROM amazoncorretto:21-alpine

WORKDIR /app

# 2단계: 내 컴퓨터에서 빌드된 최종 jar 파일만 컨테이너 내부로 복사
# (build/libs/ 폴더 안의 plain이 붙지 않은 가장 기본 jar 파일을 지정해야 합니다)
COPY build/libs/*-SNAPSHOT.jar app.jar

# 3단계: 복사한 jar 파일 바로 실행
CMD ["java", "-jar", "app.jar"]