from __future__ import annotations

import io
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import numpy as np
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from auth import AuthService, ALLOWED_ORIGINS

from fastapi import FastAPI, File, Depends, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
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
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# MongoDB Atlas 연동
MONGO_DETAILS = os.getenv("MONGO_DETAILS")
if not MONGO_DETAILS:
    raise RuntimeError("MONGO_DETAILS 환경변수가 설정되지 않았습니다.")

client = MongoClient(MONGO_DETAILS, server_api=ServerApi("1"))
db = client["fashion_db"]
garments_collection = db["garments"]
users_collection = db["users"]

pipe: Optional[FashionPipeline] = None

# 비밀번호는 평문 저장하지 않고 Argon2 기반 해시로 저장/검증
auth = AuthService(users_collection, db["sessions"], garments_collection)


# ---------------------------------------------------------
# 수명 주기 관리 (Lifespan: 1회 로드 & 워밍업 & DB 점검)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe
    print("=" * 50)
    print("🚀 Fashion AI Pipeline 초기화 중 (MongoDB 모드)...")

    # FashionPipeline 싱글톤 로딩 및 워밍업
    pipe = FashionPipeline(detector_weights=MODEL_PATH)
    pipe.warmup()
    print(f"🎯 AI Model Loaded: {MODEL_PATH}")
    print(f"🏷️ Categories: {pipe.categories}")

    # MongoDB 연결 상태 테스트
    try:
        client.admin.command("ping")
        auth.create_indexes()
        garments_collection.create_index([("user_id", 1), ("garment_id", 1)])
        print("✅ MongoDB Atlas 성공적으로 연결되었습니다!")
    except Exception as e:
        print(f"❌ MongoDB 연결 실패: {e}")
        raise  # 인증 인덱스 생성에 실패하면 요청을 받지 않습니다.

    print("=" * 50)

    yield

    print("서버 종료.")


# ---------------------------------------------------------
# FastAPI 앱 인스턴스
# ---------------------------------------------------------
app = FastAPI(
    title="Fashion Recommendation API (MongoDB Atlas)",
    description="Vision Mamba/YOLO 검출 및 FashionSigLIP 기반 임베딩 추천 (MongoDB 영구 저장)",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.middleware("http")
async def protect_session_requests(request: Request, call_next):
    # Reject cross-origin cookie mutations, including login/logout CSRF.
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse({"detail": "허용되지 않은 요청 출처입니다."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith(("/auth", "/users", "/garments", "/recommend", "/thumbnails")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/thumbnails/{filename}")
def get_thumbnail(filename: str, user_id: str = Depends(auth.current_user)):
    if Path(filename).name != filename or not garments_collection.find_one({"user_id": user_id, "thumbnail_url": f"/thumbnails/{filename}"}):
        raise HTTPException(404, "이미지를 찾을 수 없습니다.")
    path = Path(THUMBNAIL_DIR) / filename
    if not path.is_file():
        raise HTTPException(404, "이미지를 찾을 수 없습니다.")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


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
    query: str = Field(..., description="자연어 추천 쿼리 (예: '쿨톤')")
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

class GarmentDeleteRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)


# ---------------------------------------------------------
# 라우트
# ---------------------------------------------------------

@app.get("/", summary="루트 헬스체크")
def root():
    return {"status": "online", "mode": "MongoDB Cloud Persistent Storage"}


@app.get("/health", summary="시스템 상태 상세 확인")
def health():
    total_count = garments_collection.count_documents({})
    return {
        "status": "ok",
        "model_loaded": pipe is not None and getattr(pipe, "_detector", None) is not None,
        "device": str(pipe.device) if pipe else "unknown",
        "categories": pipe.categories if pipe else [],
        "thumbnails_dir": str(THUMBNAIL_DIR),
        "total_mongodb_garments": total_count,
    }

# ==========================================
# 주요 비즈니스 라우트 (옷 등록, 분석, 추천, 조회)
# ==========================================

@app.post(
    "/garments",
    summary="옷 등록 (대표 박스 추출 + MongoDB 임베딩 저장 + 썸네일 생성)",
    response_model=RegisterGarmentsResponse,
)
async def register_garments(
        user_id: str = Depends(auth.current_user),
        file: UploadFile = File(...),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="업로드된 파일이 비어 있습니다.")

    try:
        # dedup=True로 대표 박스 1개만 추출
        items: List[Garment] = pipe.analyze(image_bytes, dedup=True)
    except Exception as e:
        print(f"❌ [AI Pipeline Error]: {e}")
        raise HTTPException(status_code=500, detail=f"의류 검출 모델 처리 중 오류 발생: {str(e)}")

    if not items:
        raise HTTPException(status_code=400, detail="이미지에서 감지된 의류가 없습니다. 다른 이미지로 시도해 주세요.")

    saved_items = []
    for g in items:
        gid = f"g_{uuid.uuid4().hex[:12]}"
        thumb_filename = f"{gid}.jpg"
        thumb_filepath = os.path.join(THUMBNAIL_DIR, thumb_filename)

        # 썸네일 이미지 로컬 저장
        try:
            g.crop.save(thumb_filepath, format="JPEG", quality=92)
        except Exception as e:
            print(f"❌ [Thumbnail Save Error]: {e}")
            raise HTTPException(status_code=500, detail="썸네일 이미지 저장에 실패했습니다.")

        thumb_url = f"/thumbnails/{thumb_filename}"

        # MongoDB 저장 문서 객체
        doc = {
            "garment_id": gid,
            "user_id": user_id,
            "category": g.category,
            "bbox": [round(float(v), 4) for v in g.bbox],
            "conf": round(float(g.conf), 4),
            "area_ratio": round(float(g.area_ratio), 4),
            "embedding": g.embedding.tolist(),
            "thumbnail_url": thumb_url,
            "created_at": datetime.utcnow().isoformat(),
        }

        # ✅ MongoDB Atlas 저장 예외 처리
        try:
            garments_collection.insert_one(doc.copy())
        except Exception as e:
            print(f"❌ [MongoDB Insert Error]: {e}")
            raise HTTPException(
                status_code=500,
                detail="MongoDB Atlas 저장 중 오류가 발생했습니다. IP Whitelist(0.0.0.0/0) 및 URI 설정을 확인하세요."
            )

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
        message="옷 등록 및 MongoDB 임베딩 저장이 완료되었습니다.",
        user_id=user_id,
        registered_items=saved_items,
    )


@app.post("/analyze", summary="착용샷 분석 (다중 검출, 저장 안 함)", response_model=AnalyzeResponse)
async def analyze_outfit(file: UploadFile = File(...), user_id: str = Depends(auth.current_user)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    image_bytes = await file.read()
    items: List[Garment] = pipe.analyze(image_bytes, dedup=False)

    return AnalyzeResponse(
        total_detected=len(items),
        items=[g.to_dict(with_embedding=False) for g in items],
    )


@app.post("/recommend", summary="코디 추천 (MongoDB 임베딩 유사도 랭킹)", response_model=RecommendResponse)
async def recommend_outfit(req: RecommendRequest, user_id: str = Depends(auth.current_user)):
    # ✅ MongoDB에서 user_id에 해당하는 옷 데이터 전체 조회 (_id 제외)
    rows = list(garments_collection.find({"user_id": user_id}, {"_id": 0}))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"해당 사용자({user_id})의 등록된 옷이 없습니다. 먼저 /garments 로 옷을 등록해 주세요.",
        )

    embs = np.array([r["embedding"] for r in rows], dtype=np.float32)

    # 카테고리 필터 마스크
    mask = [r["category"] == req.category for r in rows] if req.category else None

    # 추천 연산 실행
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
        user_id: str = Depends(auth.current_user),
        category: Optional[str] = Query(None, description="특정 카테고리 필터"),
):
    query = {"user_id": user_id}
    if category:
        query["category"] = category

    # ✅ MongoDB에서 데이터 조회 (JSON 직렬화를 위해 _id 및 embedding 제외)
    user_rows = list(garments_collection.find(query, {"_id": 0, "embedding": 0}))

    return {"user_id": user_id, "count": len(user_rows), "items": user_rows}


@app.delete("/garments/{garment_id}", summary="비밀번호 확인 후 등록 의류 삭제")
def delete_garment(garment_id: str, req: GarmentDeleteRequest, user_id: str = Depends(auth.current_user)):
    if not auth.verify_password(user_id, req.password):
        raise HTTPException(status_code=403, detail="비밀번호가 올바르지 않습니다.")

    # 3) 해당 사용자의 옷인지 확인
    garment = garments_collection.find_one({
        "garment_id": garment_id,
        "user_id": user_id
    })

    if not garment:
        raise HTTPException(
            status_code=404,
            detail="해당 의류를 찾을 수 없습니다."
        )

    # 4) MongoDB 문서 삭제
    result = garments_collection.delete_one({
        "garment_id": garment_id,
        "user_id": user_id
    })

    if result.deleted_count != 1:
        raise HTTPException(
            status_code=500,
            detail="의류 데이터 삭제에 실패했습니다."
        )

    # 5) 저장된 썸네일 파일도 함께 삭제
    thumbnail_url = garment.get("thumbnail_url")
    thumbnail_deleted = False

    if thumbnail_url:
        thumbnail_name = os.path.basename(thumbnail_url)
        thumbnail_path = Path(THUMBNAIL_DIR) / thumbnail_name

        try:
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                thumbnail_deleted = True
        except OSError as e:
            # DB 삭제 자체는 완료됐으므로 파일 삭제 실패는 로그만 남김
            print(f"⚠️ [Thumbnail Delete Error] {thumbnail_path}: {e}")

    return {
        "message": "옷이 삭제되었습니다.",
        "garment_id": garment_id,
        "thumbnail_deleted": thumbnail_deleted
    }


# ---------------------------------------------------------
# 테스트 UI (/ui)
# ---------------------------------------------------------
@app.get("/ui", summary="테스트용 UI", response_class=HTMLResponse)
def test_ui():
    return HTMLResponse(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <title>Fashion AI Pipeline Test (MongoDB Atlas)</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 30px auto; padding: 20px; background: #f9fafb; color: #333; }
    h2 { text-align: center; margin-bottom: 25px; }
    .box { background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    input, button { width: 100%; margin-top: 8px; padding: 10px; box-sizing: border-box; border-radius: 6px; }
    input { border: 1px solid #d1d5db; }
    button { background: #2563eb; color: white; border: none; font-weight: bold; cursor: pointer; transition: 0.2s; }
    button:hover { background: #1d4ed8; }
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
  <h2>👗 Fashion AI 추천 & 시각화 테스트 (MongoDB Atlas)</h2>
  
  <div class="box">
    <h3>로그인 / 회원가입</h3>
    <input id="loginId" autocomplete="username" placeholder="아이디" />
    <input id="loginPassword" type="password" autocomplete="current-password" placeholder="비밀번호 (8자 이상)" />
    <button onclick="authenticate('/users')">회원가입</button>
    <button onclick="authenticate('/auth/login')">로그인</button>
    <button onclick="fetch('/auth/logout', {method:'POST'}).then(r=>r.json()).then(log)">로그아웃</button>
  </div>
  <div class="box">
    <h3>1. 옷 등록 (POST /garments)</h3>
    <p>로그인한 사용자의 옷장을 사용합니다.</p>
    <input id="garmentFile" type="file" accept="image/*" />
    <button onclick="registerGarment()">옷 등록 및 임베딩 저장</button>
  </div>

  <div class="box">
    <h3>2. 코디 추천 (POST /recommend)</h3>
    <input id="recQuery" type="text" value="쿨톤" placeholder="추천 쿼리 입력" />
    <button onclick="getRecommendation()">추천 요청</button>
  </div>

  <div class="box">
    <h3>3. 내 전체 옷장 조회 (GET /garments)</h3>
    <button onclick="getGarments()" style="background:#4b5563;">옷장 불러오기</button>
  </div>

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

    async function authenticate(path) {
      const res = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: document.getElementById('loginId').value.trim(), password: document.getElementById('loginPassword').value})});
      log(await res.json());
      document.getElementById('loginPassword').value = '';
    }

    async function registerGarment() {
      const file = document.getElementById("garmentFile").files[0];
      if (!file) return alert("이미지를 선택하세요");

      const fd = new FormData();
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

    async function getRecommendation() {
      const q = document.getElementById("recQuery").value;

      const res = await fetch("/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, top_k: 5 })
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

    async function getGarments() {
      const res = await fetch("/garments");
      const data = await res.json();
      log(data);

      if (data.items && data.items.length > 0) {
        document.getElementById("galleryTitle").textContent = `🧺 내 옷장 (${data.count}벌)`;
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