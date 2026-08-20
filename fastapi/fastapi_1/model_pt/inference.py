"""백엔드 서빙용 추론 인터페이스.

**이 파일이 백엔드와의 계약이다.** 설계문서 8.5의 API(`/garments` `/analyze`
`/recommend`)가 이 클래스를 호출하면 된다.

`phase1_demo_full.py`는 데모 스크립트(경로 하드코딩, MODE 전역 상수, 실행마다
모델 재로딩)라 서버에서 쓸 수 없어 이 모듈을 따로 뒀다. 여기는 자립적이다 —
같은 폴더에 `label_scheme.py`, `ko_to_en.py`만 있으면 동작한다.

사용:
    from inference import FashionPipeline

    pipe = FashionPipeline(detector_weights="best.pt")   # 서버 시작 시 1회
    pipe.warmup()                                        # 첫 요청 지연 제거

    items = pipe.analyze(image_bytes, dedup=True)        # 옷 등록용
    items = pipe.analyze(image_bytes, dedup=False)       # 착용샷 분석용
    hits  = pipe.recommend("쿨톤 스트릿하게", embeddings) # 추천

⚠ **모델을 요청마다 로드하지 말 것.** FashionSigLIP만 1.6GB다. 서버 수명 동안
인스턴스 하나를 유지한다.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import torch
from PIL import Image

# 두 가지 사용 방식을 모두 지원한다.
#   ① 패키지로:  from ai.inference import FashionPipeline   (백엔드 권장)
#   ② 단독으로:  sys.path에 이 폴더를 넣고 import inference  (이 저장소 스크립트들)
# ①에서는 상대 import가, ②에서는 절대 import가 동작한다.
try:
    from . import ko_to_en
    from .label_scheme import TIER1_CLASSES
except ImportError:
    import ko_to_en
    from label_scheme import TIER1_CLASSES

# ==========================================================
# 기본값 — 근거는 docs/진행상황_인수인계.md 1장
# ==========================================================
EMB_MODEL = "hf-hub:Marqo/marqo-fashionSigLIP"
DET_CONF = 0.25          # 2026-07-31 평가에서 상향이 무의미함을 확인
EMBED_BATCH = 32         # 8GB VRAM 기준 안전값
DEFAULT_TOP_K = 5


@dataclass
class Garment:
    """검출된 옷 하나. 백엔드가 DB에 저장할 단위다."""
    category: str                    # Tier 1: outerwear|top|bottom|headwear
    bbox: tuple[float, float, float, float]   # 정규화 좌표 (x1, y1, x2, y2)
    conf: float
    area_ratio: float                # 박스 면적 / 이미지 면적
    embedding: np.ndarray = field(repr=False)  # 768d float32, L2 정규화됨
    crop: Image.Image = field(repr=False)      # 마스크 크롭 (썸네일 저장용)

    def to_dict(self, with_embedding: bool = False) -> dict:
        """API 응답용. **임베딩은 기본으로 뺀다** — 3KB짜리라 크고 클라이언트가 안 쓴다."""
        d = {
            "category": self.category,
            "bbox": [round(v, 4) for v in self.bbox],
            "conf": round(self.conf, 4),
            "area_ratio": round(self.area_ratio, 4),
        }
        if with_embedding:
            d["embedding"] = self.embedding.tolist()
        return d


@dataclass
class Hit:
    """추천 결과 하나."""
    index: int      # recommend()에 넘긴 embeddings 배열의 인덱스
    score: float    # 코사인 유사도
    rank: int       # 1부터

    def to_dict(self) -> dict:
        # ⚠ score를 퍼센트로 노출하지 말 것. 아래 recommend() 주석 참조
        return {"index": self.index, "score": round(self.score, 4), "rank": self.rank}


class FashionPipeline:
    """검출 → 크롭 → 임베딩 → 추천. 모델을 한 번 올려 재사용한다."""

    def __init__(self, detector_weights: str | None = None, device: str | None = None):
        """
        detector_weights: 파인튜닝 가중치(`best.pt`) 경로.
            None이면 사전학습 DeepFashion2 13종을 받아 쓴다 — **권장하지 않는다.**
            Tier 1 정확도가 46.1%에 그쳐 카테고리를 신뢰할 수 없다(파인튜닝은 98.6%).
        device: "cuda" | "cpu". None이면 자동.
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._detector_weights = detector_weights
        self._detector = None
        self._embedder = None
        self._preprocess = None
        self._tokenizer = None

    # ---------- 모델 로딩 (지연 + 1회) ----------
    def _ensure_loaded(self) -> None:
        if self._detector is not None:
            return
        from ultralytics import YOLO
        import open_clip

        if self._detector_weights:
            self._detector = YOLO(self._detector_weights)
        else:
            from huggingface_hub import hf_hub_download
            self._detector = YOLO(
                hf_hub_download("Bingsu/adetailer", "deepfashion2_yolov8s-seg.pt"))

        model, preprocess = open_clip.create_model_from_pretrained(EMB_MODEL)
        self._embedder = model.to(self.device).eval()
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(EMB_MODEL)

    def warmup(self) -> None:
        """모델을 미리 올리고 더미 추론을 한 번 돌린다.

        서버 기동 시 호출하면 첫 요청이 느려지지 않는다. FashionSigLIP 다운로드가
        아직이면 여기서 1.6GB를 받으므로 **오래 걸릴 수 있다.**
        """
        self._ensure_loaded()
        dummy = Image.new("RGB", (640, 640), (255, 255, 255))
        self._embed_images([dummy])
        self.embed_text("warmup")

    @property
    def categories(self) -> list[str]:
        return list(TIER1_CLASSES)

    # ---------- 내부 유틸 ----------
    @staticmethod
    def _to_pil(image) -> Image.Image:
        """bytes / 경로 / PIL 어느 쪽이든 받는다."""
        if isinstance(image, Image.Image):
            return image.convert("RGB")
        if isinstance(image, (bytes, bytearray)):
            return Image.open(io.BytesIO(image)).convert("RGB")
        if isinstance(image, (str, os.PathLike)):
            return Image.open(image).convert("RGB")
        raise TypeError(f"지원하지 않는 이미지 타입: {type(image)}")

    @torch.no_grad()
    def _embed_images(self, pils: Sequence[Image.Image]) -> np.ndarray:
        self._ensure_loaded()
        out = []
        for i in range(0, len(pils), EMBED_BATCH):
            chunk = pils[i:i + EMBED_BATCH]
            batch = torch.stack([self._preprocess(im) for im in chunk]).to(self.device)
            f = self._embedder.encode_image(batch)
            f = f / f.norm(dim=-1, keepdim=True)
            out.append(f.cpu().numpy())
        return np.concatenate(out, axis=0).astype(np.float32)

    @staticmethod
    def _crop_with_mask(img_rgb: np.ndarray, mask, bbox, bg=(255, 255, 255)) -> np.ndarray:
        """마스크로 배경을 지우고 박스로 자른다.

        FashionSigLIP은 흰 배경 상품 이미지에 최적화돼 있어 배경을 지우면 임베딩
        품질이 올라간다(P@5 91.3 vs 86.2, 2026-07-31 평가).
        """
        x1, y1, x2, y2 = [int(v) for v in bbox]
        if mask is not None:
            img_rgb = np.where(mask[..., None].astype(bool), img_rgb,
                               np.array(bg, dtype=np.uint8))
        return img_rgb[max(y1, 0):y2, max(x1, 0):x2]

    # ---------- 공개 API ----------
    def analyze(self, image, dedup: bool = False, conf: float = DET_CONF) -> list[Garment]:
        """이미지에서 옷을 검출·크롭·임베딩한다.

        dedup=True  → 소스 1장당 **대표 박스 1개**만 남긴다. 옷 등록(`/garments`)용.
                      대표는 conf가 아니라 **conf×면적**으로 고른다. 옷의 일부(허리·소매)가
                      높은 신뢰도를 받는 경우가 있어 conf만 보면 파편이 뽑힌다.
                      이 정책으로 추천 P@5가 75.5% → 87.3%로 올랐다.
        dedup=False → 검출된 옷을 전부 반환. 착용샷 분석(`/analyze`)용.
                      **착용샷은 상·하의를 여러 개 잡아야 하므로 dedup을 걸면 안 된다.**

        검출이 하나도 안 되면 **이미지 전체를 옷 하나로** 반환한다(쇼핑몰컷 대응).
        """
        self._ensure_loaded()
        pil = self._to_pil(image)
        arr = np.asarray(pil)
        H, W = arr.shape[:2]

        r = self._detector.predict(pil, conf=conf, verbose=False)[0]
        cands = []
        if r.boxes is not None and len(r.boxes) > 0:
            boxes = r.boxes.xyxy.cpu().numpy()
            clss = r.boxes.cls.cpu().numpy().astype(int)
            confs = r.boxes.conf.cpu().numpy()
            masks = r.masks.data.cpu().numpy() if r.masks is not None else None
            for i in range(len(boxes)):
                m = None
                if masks is not None:
                    mi = masks[i]
                    if mi.shape != (H, W):
                        mi = np.asarray(Image.fromarray((mi * 255).astype(np.uint8))
                                        .resize((W, H))) > 127
                    m = mi.astype(np.uint8)
                crop = self._crop_with_mask(arr, m, boxes[i])
                if crop.size == 0:
                    continue
                x1, y1, x2, y2 = boxes[i]
                cands.append({
                    "crop": Image.fromarray(crop),
                    # 클래스 이름은 모델에서 읽는다. 사전학습(13종)과 파인튜닝(4종)이
                    # 체계가 달라 하드코딩하면 엉뚱한 이름이 붙는다
                    "category": self._detector.names.get(int(clss[i]), str(clss[i])),
                    "conf": float(confs[i]),
                    "bbox": (float(x1) / W, float(y1) / H, float(x2) / W, float(y2) / H),
                    "area_ratio": float((x2 - x1) * (y2 - y1)) / float(W * H),
                })

        if not cands:                      # 검출 실패 → 전체 이미지를 옷으로
            cands = [{"crop": pil, "category": "unknown", "conf": 1.0,
                      "bbox": (0.0, 0.0, 1.0, 1.0), "area_ratio": 1.0}]
        elif dedup:
            cands = [max(cands, key=lambda c: c["conf"] * c["area_ratio"])]

        embs = self._embed_images([c["crop"] for c in cands])
        return [Garment(category=c["category"], bbox=c["bbox"], conf=c["conf"],
                        area_ratio=c["area_ratio"], embedding=e, crop=c["crop"])
                for c, e in zip(cands, embs)]

    @torch.no_grad()
    def embed_text(self, query: str) -> np.ndarray:
        """텍스트를 768d 벡터로. **한글은 자동으로 영어로 바꾼다.**

        ⚠ 한글을 그대로 넣으면 검색이 동작하지 않는다. 토크나이저에 한글이 없어
        "파란 청바지"와 "야구 모자"가 같은 벡터가 된다(전체 P@5 87.3% → 6.4%).
        `ko_to_en`의 도메인 사전으로 치환하면 88.2%가 나온다.
        """
        self._ensure_loaded()
        text = ko_to_en.to_english(query) or query
        tokens = self._tokenizer([text]).to(self.device)
        f = self._embedder.encode_text(tokens)
        f = f / f.norm(dim=-1, keepdim=True)
        return f.cpu().numpy().astype(np.float32)[0]

    def recommend(self, query: str, embeddings: np.ndarray,
                  top_k: int = DEFAULT_TOP_K,
                  mask: Sequence[bool] | None = None) -> list[Hit]:
        """텍스트 쿼리로 옷을 추천한다.

        embeddings: (N, 768) 배열. 백엔드가 DB에서 꺼내 넘긴다.
        mask      : 길이 N의 불리언. 카테고리 하드 필터 등에 쓴다.
                    False인 항목은 후보에서 빠진다.

        ⚠ **`score`를 임계값이나 퍼센트로 쓰지 말 것.** SigLIP은 sigmoid loss로
        학습돼 정답에 가까운 추천도 0.05~0.08 수준이다. **순위만 유효하다.**
        UI에 "87% 일치"처럼 노출하면 안 되고, 컷오프가 필요하면 상위 K개를 쓴다.
        """
        if embeddings is None or len(embeddings) == 0:
            return []
        emb = np.asarray(embeddings, dtype=np.float32)
        if emb.ndim != 2:
            raise ValueError(f"embeddings는 (N, 768) 이어야 한다: {emb.shape}")

        sims = emb @ self.embed_text(query)
        if mask is not None:
            m = np.asarray(mask, dtype=bool)
            if len(m) != len(sims):
                raise ValueError(f"mask 길이 불일치: {len(m)} vs {len(sims)}")
            sims = np.where(m, sims, -np.inf)

        k = min(top_k, int(np.isfinite(sims).sum()))
        if k <= 0:
            return []
        order = np.argsort(-sims)[:k]
        return [Hit(index=int(i), score=float(sims[i]), rank=r)
                for r, i in enumerate(order, start=1)]
