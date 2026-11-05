from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
import time
import requests

URL = "http://localhost:8080/infer"  # 게이트웨이를 통한 실제 추론 주소
IMAGE = Path("C:/Users/rkdrn/Desktop/d4eb31c30ebe6b0d1c34a4ca20d9684c.jpg")               # 테스트 이미지 경로
HEADERS = {}                            # 직접 FastAPI 호출 시 필요하면 X-API-Key 추가
FILE_FIELD = "file"                     # FastAPI 업로드 파라미터 이름에 맞게 수정

def infer(barrier):
    barrier.wait()  # 요청을 동시에 시작
    start = time.perf_counter()
    try:
        with IMAGE.open("rb") as image:
            response = requests.post(
                URL,
                headers=HEADERS,
                files={FILE_FIELD: (IMAGE.name, image, "image/jpeg")},
                timeout=180,
            )
        return response.status_code, time.perf_counter() - start
    except requests.RequestException as exc:
        return str(exc), time.perf_counter() - start

for users in (1, 2, 5, 10):
    barrier = Barrier(users)
    with ThreadPoolExecutor(max_workers=users) as pool:
        results = list(pool.map(lambda _: infer(barrier), range(users)))

    times = [seconds for _, seconds in results]
    print(
        f"{users}명 동시 요청 | 결과: {[status for status, _ in results]} "
        f"| 평균: {sum(times)/len(times):.1f}초 | 최장: {max(times):.1f}초"
    )

