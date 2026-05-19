from __future__ import annotations

import io
import json
import os
from fastapi.concurrency import run_in_threadpool
from pathlib import Path
from threading import Lock
from typing import Tuple
import torch
import torch.nn.functional as F
from fastapi import FastAPI, File, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
from fastapi.security import APIKeyHeader
from    models import VAL_TRANSFORM, load_cmt_model
from typing import List

LABEL_KR = { #추후 수정
    "freshapples": "Fresh Apples",
    "freshbanana": "Fresh Banana",
    "freshcapsicum": "Fresh Capsicum",
    "freshcucumber": "Fresh Cucumber",
    "freshoranges": "Fresh Oranges",
    "freshpotato": "Fresh Potato",
    "freshtomato": "Fresh Tomato",

    "rottenapples": "Rotten Apples",
    "rottenbanana": "블레이저",
    "rottencapsicum": "Rotten Capsicum",
    "rottencucumber": "Rotten Cucumber",
    "rottenoranges": "Rotten Oranges",
    "rottenpotato": "Rotten Potato",
    "rottentomato": "Rotten Tomato"
}

BASE_DIR = Path(__file__).resolve().parent

def _path_from_env_or_default(env_var: str, *relative: str) -> Path:
    v = os.getenv(env_var)
    if v:
        p = Path(v)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p.resolve()
    return (BASE_DIR.joinpath(*relative)).resolve()

MODEL_PATH  = _path_from_env_or_default("MODEL_PATH",  "model_pt", "best_model_fold1.pt")
LABELS_PATH = _path_from_env_or_default("LABELS_PATH", "model_pt", "label_names.json")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


if not MODEL_PATH.exists():
    raise FileNotFoundError(f"Model checkpoint not found: {MODEL_PATH}")
if not LABELS_PATH.exists():
    raise FileNotFoundError(f"Label file not found: {LABELS_PATH}")


class InferenceResponse(BaseModel):
    filename: str
    content_type: str | None
    size_bytes: int
    prediction: str
    confidence: float


# ----------------------------
class ModelService:
    def __init__(self, model_path: Path, labels_path: Path) -> None:
        self.model_path = model_path
        self.labels_path = labels_path
        self.device = DEVICE
        self.transform = VAL_TRANSFORM
        self._model: torch.nn.Module | None = None
        self._labels: list[str] = []
        self._lock = Lock()

    def ensure_loaded(self) -> None:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._load()

    def _load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {self.model_path}")
        if not self.labels_path.exists():
            raise FileNotFoundError(f"Label file not found: {self.labels_path}")

        with self.labels_path.open("r", encoding="utf-8") as f:
            labels = json.load(f)
        if not isinstance(labels, list) or not all(isinstance(s, str) for s in labels) or not labels:
            raise ValueError("json이 이상해요")

        model, missing, unexpected = load_cmt_model(
            model_path=self.model_path, num_classes=len(labels), device=self.device
        )
        if missing:
            print("[load] missing keys:", list(missing))
        if unexpected:
            print("[load] unexpected keys:", list(unexpected))

        self._model = model.to(self.device).eval()
        self._labels = list(labels)
        torch.set_num_threads(1)  # CPU 서버면 과한 스레드 방지(상황 맞게 조절)

    def predict(self, image_bytes: bytes) -> Tuple[str, float]:
        self.ensure_loaded()
        assert self._model is not None
        assert self._labels

        try:
            pil = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image") from exc

        x = self.transform(pil).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            logits = self._model(x)
            probs = F.softmax(logits, dim=1).squeeze(0)
            conf, idx = probs.max(dim=0)
        label = self._labels[int(idx)]
        return label, float(conf)


# ----------------------------
# FastAPI 앱 & 라우트
# ----------------------------
app = FastAPI(
    title="융소프",
    description="딥러닝이에요"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

model_service = ModelService(MODEL_PATH, LABELS_PATH)

#API키
API_KEY = os.getenv("API_KEY", "default-dev-key")
API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

#api키 맞나 체크하는거 틀리면 오류코드 반환
async def check_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="api키 분실됨")
    return api_key

@app.get("/", summary="홈")
def root():
    return {"message": "정상작동 중"}


@app.get("/health", summary="연결상태확인", dependencies=[Depends(check_api_key)])
def health():
    """
    api 연결상태 정상인지 확인하는 기능
    """
    return {
        "model_loaded": model_service._model is not None,
        "labels_loaded": bool(model_service._labels),
        "device": str(DEVICE),
        "model_path": str(MODEL_PATH),
        "labels_path": str(LABELS_PATH),
    }


# ✅ 시각테스트용 UI 다 만들면 없앨거임
@app.get("/ui", summary="시각용ui", response_class=HTMLResponse)
def ui():
    """
    테스트용 뒤에서 돌아가는지 시각화함
    """
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <title>Inference UI</title>
  <style>
          body {
        font-family: system-ui, -apple-system, sans-serif;
        margin: 0;
        padding: 0;
    
        display: flex;
        flex-direction: column;
        align-items: center;   /* 🔹 h2 포함 전체 가로 중앙 */
        min-height: 100vh;
      }
    
      h2 {
        margin-top: 40px;      /* 🔹 위 여백 */
        text-align: center;
      }
    
      /* 🔹 카드만 화면의 남은 공간에서 수직 중앙 정렬 */
      .card {
        margin-top: auto;
        margin-bottom: auto;
    
        max-width: 520px;
        padding: 20px;
        border: 1px solid #ddd;
        border-radius: 12px;
      }
    .row { margin-top: 12px; }
    img { max-width: 100%; border-radius: 8px; }
    button { padding: 10px 14px; border-radius: 8px; border: 1px solid #ccc; cursor:pointer; }
    #result { margin-top: 10px; font-weight: 600; }
    #err { color: #b00020; margin-top: 8px; }
  </style>
</head>
<body>
  <h2>이미지 분류 테스트</h2>
  <div class="card">
    <div class="row">
      <input id="file" type="file" accept="image/*"/>
    </div>
    <div class="row">
      <img id="preview" alt="preview" />
    </div>
    <div class="row">
      <button id="btn">분류 요청</button>
    </div>
    <div id="result"></div>
    <div id="err"></div>
  </div>

<script>
const $ = id => document.getElementById(id);

// 파일 선택 시 미리보기
$("file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const url = URL.createObjectURL(f);
  $("preview").src = url;
});

// 분류 요청 버튼 클릭
$("btn").addEventListener("click", async () => {
  $("result").textContent = "";
  $("err").textContent = "";

  const f = $("file").files[0];
  if (!f) {
    $("err").textContent = "이미지를 선택하세요.";
    return;
  }

  const form = new FormData();
  form.append("file", f);

  try {
    const res = await fetch("/infer", {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const msg = await res.text();
      $("err").textContent = "오류: " + msg;
      return;
    }

    const data = await res.json();
    $("result").textContent =
      `예측: ${data.prediction}`;

  } catch (err) {
    $("err").textContent = "요청 실패: " + err;
  }
});
</script>
</body>
</html>
        """.strip()
    )


@app.post("/infer", summary="딥러닝추론", response_model=InferenceResponse, dependencies=[Depends(check_api_key)])
async def infer(files: List[UploadFile] = File(...)):

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Uploaded files are empty")

    predictions = []
    total_conf = 0.0

    # 💡 핵심 2: 들어온 여러 장의 사진을 반복문으로 모두 돌려줍니다.
    for file in files:
        blob = await file.read()

        # 각 이미지마다 딥러닝 추론 (비동기 스레드풀 사용)
        pred, conf = await run_in_threadpool(model_service.predict, blob)

        # 한국어 라벨로 변환 후 리스트에 저장
        pred_kr = LABEL_KR.get(pred, pred)
        predictions.append(pred_kr)
        total_conf += conf

    # 여러 벌의 옷을 분석한 결과를 하나로 예쁘게 합칩니다.
    # 예: "맨투맨, 데님 팬츠, 스니커즈"
    combined_prediction = ", ".join(predictions)

    # 평균 정확도 계산
    avg_conf = total_conf / len(files)

    return InferenceResponse(
        filename=f"총 {len(files)}장의 이미지",
        content_type="multipart/form-data",
        size_bytes=0, # 다중 파일이므로 생략하거나 전체 합산 가능
        prediction=combined_prediction,
        confidence=avg_conf,
    )

