from __future__ import annotations

import io
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# 모델 및 파이프라인 임포트 (model_pt 폴더 기준)
# ---------------------------------------------------------
from model_pt.inference import FashionPipeline, Garment, Hit
from model_pt.label_scheme import TIER1_CLASSES

# ---------------------------------------------------------
# 환경 설정 및 디렉터리 세팅
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "model_pt" / "best.pt"))
THUMBNAILS_DIR = Path(os.getenv("THUMBNAILS_DIR", str(BASE_DIR / "thumbnails")))
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

# 전역 파이프라인 및 인메모리 DB
pipe: Optional[FashionPipeline] = None
GARMENTS_DB: List[dict] = []  # MongoDB 대신 사용할 인메모리 저장소


# ---------------------------------------------------------
# 수명 주기 관리 (Lifespan: 1회 로드 & 워밍업)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe
    print("=" * 50)
    print("🚀 Fashion AI Pipeline 초기화 중 (인메모리 모드)...")

    # FashionPipeline 싱글톤 로딩 및 워밍업
    pipe = FashionPipeline(detector_weights=MODEL_PATH)
    pipe.warmup()  #[cite: 1]
    print(f"🎯 AI Model Loaded: {MODEL_PATH}")
    print(f"🏷️ Categories: {pipe.categories}")  #[cite: 1]
    print("=" * 50)

    yield

    print("🛑 서버가 안전하게 종료되었습니다.")


# ---------------------------------------------------------
# FastAPI 앱 인스턴스
# ---------------------------------------------------------
app = FastAPI(
    title="Fashion Recommendation API (In-Memory)",
    description="Vision Mamba/YOLO 검출 및 FashionSigLIP 기반 임베딩 추천",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 크롭 썸네일 서빙용 정적 폴더 마운트
app.mount("/thumbnails", StaticFiles(directory=str(THUMBNAILS_DIR)), name="thumbnails")


# ---------------------------------------------------------
# Pydantic DTO 스키마
# ---------------------------------------------------------
class GarmentItemResponse(BaseModel):
    garment_id: str
    category: str
    bbox: List[float]
    conf: float
    area_ratio: float
    thumbnail_url: str


class RegisterGarmentsResponse(BaseModel):
    message: str
    user_id: str
    registered_items: List[GarmentItemResponse]


class AnalyzeResponse(BaseModel):
    total_detected: int
    items: List[dict]


class RecommendRequest(BaseModel):
    user_id: str = Field(..., description="사용자 식별 고유 ID")
    query: str = Field(..., description="자연어 추천 쿼리 (예: '쿨톤 스트릿하게')")
    category: Optional[str] = Field(None, description="outerwear|top|bottom|headwear 필터")
    top_k: int = Field(5, ge=1, le=20, description="반환할 상위 결과 개수")


class RecommendResultItem(BaseModel):
    garment_id: str
    category: str
    rank: int
    score: float
    thumbnail_url: str
    bbox: List[float]
    created_at: str


class RecommendResponse(BaseModel):
    query: str
    total_results: int
    results: List[RecommendResultItem]


# ---------------------------------------------------------
# 라우트
# ---------------------------------------------------------
@app.get("/", summary="루트 헬스체크")
def root():
    return {"status": "online", "mode": "in-memory (no MongoDB)"}


@app.get("/health", summary="시스템 상태 상세 확인")
def health():
    return {
        "model_loaded": pipe is not None and pipe._detector is not None,
        "device": str(pipe.device) if pipe else "unknown",
        "detector_weights": MODEL_PATH,
        "categories": pipe.categories if pipe else [],
        "thumbnails_dir": str(THUMBNAILS_DIR),
        "total_saved_garments": len(GARMENTS_DB),
    }


@app.post(
    "/garments",
    summary="옷 등록 (대표 박스 추출 + 임베딩 메모리 저장 + 썸네일 생성)",
    response_model=RegisterGarmentsResponse,
)
async def register_garments(
        user_id: str = Form(..., description="사용자 ID (비회원 UUID 또는 회원 ID)"),
        file: UploadFile = File(...),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="업로드된 파일이 비어 있습니다.")

    # dedup=True로 대표 박스 1개만 추출[cite: 1, 4]
    items: List[Garment] = pipe.analyze(image_bytes, dedup=True)

    saved_items = []
    for g in items:
        gid = f"g_{uuid.uuid4().hex[:12]}"
        thumb_filename = f"{gid}.jpg"
        thumb_filepath = THUMBNAILS_DIR / thumb_filename

        # 썸네일 이미지 로컬 저장[cite: 1]
        g.crop.save(thumb_filepath, format="JPEG", quality=92)
        thumb_url = f"/thumbnails/{thumb_filename}"

        # 인메모리 리스트에 적재[cite: 1]
        doc = {
            "garment_id": gid,
            "user_id": user_id,
            "category": g.category,
            "bbox": [round(v, 4) for v in g.bbox],
            "conf": round(g.conf, 4),
            "area_ratio": round(g.area_ratio, 4),
            "embedding": g.embedding.tolist(),
            "thumbnail_url": thumb_url,
            "created_at": datetime.utcnow().isoformat(),
        }
        GARMENTS_DB.append(doc)

        saved_items.append(
            GarmentItemResponse(
                garment_id=gid,
                category=g.category,
                bbox=doc["bbox"],
                conf=doc["conf"],
                area_ratio=doc["area_ratio"],
                thumbnail_url=thumb_url,
            )
        )

    return RegisterGarmentsResponse(
        message="옷 등록 및 임베딩 저장이 완료되었습니다.",
        user_id=user_id,
        registered_items=saved_items,
    )


@app.post("/analyze", summary="착용샷 분석 (다중 검출, 저장 안 함)", response_model=AnalyzeResponse)
async def analyze_outfit(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    image_bytes = await file.read()
    # 착용샷 분석은 dedup=False[cite: 1, 4]
    items: List[Garment] = pipe.analyze(image_bytes, dedup=False)

    return AnalyzeResponse(
        total_detected=len(items),
        items=[g.to_dict(with_embedding=False) for g in items],
    )


@app.post("/recommend", summary="코디 추천 (임베딩 유사도 랭킹)", response_model=RecommendResponse)
async def recommend_outfit(req: RecommendRequest):
    # 인메모리에서 user_id에 해당하는 옷 목록 추출[cite: 1]
    rows = [r for r in GARMENTS_DB if r["user_id"] == req.user_id]

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"해당 사용자({req.user_id})의 등록된 옷이 없습니다. 먼저 /garments 로 옷을 등록해 주세요.",
        )

    embs = np.array([r["embedding"] for r in rows], dtype=np.float32)

    # 카테고리 필터 마스크[cite: 1, 4]
    mask = [r["category"] == req.category for r in rows] if req.category else None

    # 추천 연산 실행[cite: 1, 4]
    hits: List[Hit] = pipe.recommend(req.query, embs, top_k=req.top_k, mask=mask)

    results = []
    for h in hits:
        matched_row = rows[h.index]
        results.append(
            RecommendResultItem(
                garment_id=matched_row["garment_id"],
                category=matched_row["category"],
                rank=h.rank,
                score=round(h.score, 4),
                thumbnail_url=matched_row["thumbnail_url"],
                bbox=matched_row["bbox"],
                created_at=matched_row.get("created_at", ""),
            )
        )

    return RecommendResponse(
        query=req.query,
        total_results=len(results),
        results=results,
    )


@app.get("/garments", summary="등록된 옷장 목록 조회")
def get_user_garments(
        user_id: str = Query(..., description="사용자 ID"),
        category: Optional[str] = Query(None, description="특정 카테고리 필터"),
):
    user_rows = [r for r in GARMENTS_DB if r["user_id"] == user_id]
    if category:
        user_rows = [r for r in user_rows if r["category"] == category]

    items = [{k: v for k, v in r.items() if k != "embedding"} for r in user_rows]
    return {"user_id": user_id, "count": len(items), "items": items}


# ---------------------------------------------------------
## ---------------------------------------------------------
# 테스트 UI (/ui) - 시각화 렌더링 개선
# ---------------------------------------------------------
@app.get("/ui", summary="테스트용 UI", response_class=HTMLResponse)
def test_ui():
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <title>Fashion AI Pipeline Test (In-Memory)</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 30px auto; padding: 20px; background: #f9fafb; color: #333; }
    h2 { text-align: center; margin-bottom: 25px; }
    .box { background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    input, button { width: 100%; margin-top: 8px; padding: 10px; box-sizing: border-box; border-radius: 6px; }
    input { border: 1px solid #d1d5db; }
    button { background: #2563eb; color: white; border: none; font-weight: bold; cursor: pointer; transition: 0.2s; }
    button:hover { background: #1d4ed8; }
    
    /* 썸네일 카드 갤러리 스타일 */
    .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; margin-top: 15px; }
    .item-card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.04); }
    .item-card img { width: 100%; height: 160px; object-fit: contain; background: #f3f4f6; border-radius: 6px; margin-bottom: 8px; border: 1px solid #eee; }
    .rank-badge { display: inline-block; background: #10b981; color: white; font-weight: bold; font-size: 12px; padding: 2px 8px; border-radius: 12px; margin-bottom: 4px; }
    .item-title { font-weight: bold; font-size: 14px; margin: 4px 0; }
    .item-score { font-size: 12px; color: #6b7280; }
    pre { background: #1f2937; color: #f9fafb; padding: 12px; border-radius: 6px; overflow: auto; font-size: 12px; max-height: 250px; }
  </style>
</head>
<body>
  <h2>👗 Fashion AI 추천 & 시각화 테스트</h2>
  
  <div class="box">
    <h3>1. 옷 등록 (POST /garments)</h3>
    <input id="userId" type="text" value="test_user" placeholder="User ID" />
    <input id="garmentFile" type="file" accept="image/*" />
    <button onclick="registerGarment()">옷 등록 및 임베딩 저장</button>
  </div>

  <div class="box">
    <h3>2. 코디 추천 (POST /recommend)</h3>
    <input id="recQuery" type="text" value="쿨톤 스트릿하게" placeholder="추천 쿼리 입력" />
    <button onclick="getRecommendation()">추천 요청</button>
  </div>

  <div class="box">
    <h3>3. 내 전체 옷장 조회 (GET /garments)</h3>
    <button onclick="getGarments()" style="background:#4b5563;">옷장 불러오기</button>
  </div>

  <!-- 추천/조회 결과 이미지 갤러리 영역 -->
  <div class="box">
    <h3 id="galleryTitle">🖼️ 결과 이미지 뷰어</h3>
    <div id="galleryContainer" class="card-grid">
      <p style="color:#9ca3af; grid-column: 1/-1;">등록 또는 추천을 실행하면 이미지가 여기에 나타납니다.</p>
    </div>
  </div>

  <div class="box">
    <h3>📋 Raw JSON Response</h3>
    <pre id="output">결과 로그가 여기에 출력됩니다.</pre>
  </div>

  <script>
    const log = (msg) => document.getElementById("output").textContent = JSON.stringify(msg, null, 2);

    // 1. 옷 등록
    async function registerGarment() {
      const file = document.getElementById("garmentFile").files[0];
      const uid = document.getElementById("userId").value;
      if (!file) return alert("이미지를 선택하세요");

      const fd = new FormData();
      fd.append("user_id", uid);
      fd.append("file", file);

      const res = await fetch("/garments", { method: "POST", body: fd });
      const data = await res.json();
      log(data);

      if (data.registered_items && data.registered_items.length > 0) {
        document.getElementById("galleryTitle").textContent = "✨ 방금 등록된 옷 (마스크 크롭 썸네일)";
        const container = document.getElementById("galleryContainer");
        container.innerHTML = data.registered_items.map(item => `
          <div class="item-card">
            <img src="${item.thumbnail_url}" alt="${item.category}" />
            <div class="item-title">${item.category}</div>
            <div class="item-score">신뢰도: ${(item.conf * 100).toFixed(1)}%</div>
          </div>
        `).join("");
      }
    }

    // 2. 코디 추천 (순위 및 크롭 이미지 렌더링)
    async function getRecommendation() {
      const uid = document.getElementById("userId").value;
      const q = document.getElementById("recQuery").value;

      const res = await fetch("/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, query: q, top_k: 5 })
      });
      const data = await res.json();
      log(data);

      if (data.results && data.results.length > 0) {
        document.getElementById("galleryTitle").textContent = `🎯 "${data.query}" 추천 결과 (상위 ${data.results.length}개)`;
        const container = document.getElementById("galleryContainer");
        container.innerHTML = data.results.map(item => `
          <div class="item-card">
            <span class="rank-badge">Rank #${item.rank}</span>
            <img src="${item.thumbnail_url}" alt="${item.category}" />
            <div class="item-title">${item.category}</div>
            <div class="item-score">SigLIP Score: ${item.score}</div>
          </div>
        `).join("");
      } else {
        document.getElementById("galleryContainer").innerHTML = `<p style="color:#ef4444; grid-column: 1/-1;">추천 결과가 없습니다. 옷을 먼저 등록했는지 확인하세요.</p>`;
      }
    }

    // 3. 내 옷장 목록 조회
    async function getGarments() {
      const uid = document.getElementById("userId").value;
      const res = await fetch(`/garments?user_id=${uid}`);
      const data = await res.json();
      log(data);

      if (data.items && data.items.length > 0) {
        document.getElementById("galleryTitle").textContent = `🧺 ${uid} 님의 옷장 (${data.count}벌)`;
        const container = document.getElementById("galleryContainer");
        container.innerHTML = data.items.map(item => `
          <div class="item-card">
            <img src="${item.thumbnail_url}" alt="${item.category}" />
            <div class="item-title">${item.category}</div>
            <div class="item-score">ID: ${item.garment_id}</div>
          </div>
        `).join("");
      }
    }
  </script>
</body>
</html>
        """.strip()
    )