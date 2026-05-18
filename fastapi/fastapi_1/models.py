from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple, Dict
import math
import torch
from torch import nn
import torchvision.transforms as T
import torchvision.transforms.functional as TF
from PIL import Image
from torchvision import transforms



class DropPath(nn.Module):  # Stochastic Depth 구현
    """ per-sample DropPath (Stochastic Depth) """
    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = float(drop_prob)

    def forward(self, x):
        if self.drop_prob == 0.0 or not self.training:
            return x
        keep_prob = 1.0 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = x.new_empty(shape).bernoulli_(keep_prob)
        return x.div(keep_prob) * random_tensor

class DepthwiseConv2d(nn.Module):
    def __init__(self, channels, k=3, s=1, p=1, bias=False):
        super().__init__()
        self.dw = nn.Conv2d(channels, channels, k, s, p, groups=channels, bias=bias)

    def forward(self, x):
        return self.dw(x)

class ConvBNGELU(nn.Module):
    def __init__(self, in_ch, out_ch, k=3, s=1, p=1):
        super().__init__()
        self.conv = nn.Conv2d(in_ch, out_ch, k, s, p, bias=False)
        self.bn   = nn.BatchNorm2d(out_ch, eps=1e-5, momentum=0.1)
        self.act  = nn.GELU()

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))

class ConvStage(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.ds   = ConvBNGELU(in_ch, out_ch, k=3, s=2, p=1)
        self.body = ConvBNGELU(out_ch, out_ch, k=3, s=1, p=1)

    def forward(self, x):
        x = self.ds(x)
        x = self.body(x)
        return x

class LPU(nn.Module):
    """ Local Perception Unit: 3x3 depthwise → GELU → BN (채널 보존) """
    def __init__(self, channels):
        super().__init__()
        self.dw  = DepthwiseConv2d(channels, k=3, s=1, p=1, bias=False)
        self.bn  = nn.BatchNorm2d(channels, eps=1e-5, momentum=0.1)
        self.act = nn.GELU()

    def forward(self, x):
        x = self.dw(x)
        x = self.bn(x)
        x = self.act(x)
        return x

class MLP(nn.Module):
    def __init__(self, dim, mlp_ratio=3.0, drop=0.1):
        super().__init__()
        hidden = int(dim * mlp_ratio)
        self.fc1 = nn.Linear(dim, hidden)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden, dim)
        self.drop = nn.Dropout(drop)

    def forward(self, x):
        x = self.fc1(x); x = self.act(x); x = self.drop(x)
        x = self.fc2(x); x = self.drop(x)
        return x

# -----------------------------------------------------------
# [수정됨] LPU가 포함된 TransformerBlock
# -----------------------------------------------------------
class TransformerBlock(nn.Module):
    def __init__(self, dim, num_heads, mlp_ratio=3.0, attn_drop=0.0, proj_drop=0.1, drop_path=0.0):
        super().__init__()
        # 1. LPU (Local Perception Unit) 내부 탑재
        self.lpu = LPU(dim)

        self.norm1 = nn.LayerNorm(dim, eps=1e-6)
        self.attn  = nn.MultiheadAttention(dim, num_heads, dropout=attn_drop, batch_first=True)
        self.drop1 = nn.Dropout(proj_drop)
        self.dp1   = DropPath(drop_path)

        self.norm2 = nn.LayerNorm(dim, eps=1e-6)
        self.mlp   = MLP(dim, mlp_ratio=mlp_ratio, drop=proj_drop)
        self.dp2   = DropPath(drop_path)

    def forward(self, x):
        # x: (B, N, C) - Token 형태
        B, N, C = x.shape

        # --- [1] LPU 적용 (Token -> Image -> LPU -> Token) ---
        # 정사각형 이미지라고 가정: H = W = sqrt(N)
        H = W = int(math.sqrt(N))

        x_reshaped = x.transpose(1, 2).view(B, C, H, W) # (B, C, H, W)
        x_reshaped = self.lpu(x_reshaped)               # LPU 통과
        x_lpu = x_reshaped.flatten(2).transpose(1, 2)   # 다시 (B, N, C)

        x = x + x_lpu # Residual Connection (논문 구현에 따라 직렬 연결 혹은 잔차 연결)

        # --- [2] Self-Attention ---
        y, _ = self.attn(self.norm1(x), self.norm1(x), self.norm1(x), need_weights=False)
        x = x + self.dp1(self.drop1(y))

        # --- [3] MLP (FFN) ---
        x = x + self.dp2(self.mlp(self.norm2(x)))
        return x
# ------------------------------------------------------------
# [추가됨] EMA (Exponential Moving Average) 클래스
# ------------------------------------------------------------
from copy import deepcopy

class ModelEma(nn.Module):
    def __init__(self, model, decay=0.9999, device=None):
        super().__init__()
        # 매개변수 복사 (requires_grad=False)
        self.module = deepcopy(model)
        self.module.eval()
        self.decay = decay
        self.device = device
        if self.device is not None:
            self.module.to(device=device)

    def _update(self, model, update_fn):
        with torch.no_grad():
            for ema_v, model_v in zip(self.module.state_dict().values(), model.state_dict().values()):
                if self.device is not None:
                    model_v = model_v.to(device=self.device)
                ema_v.copy_(update_fn(ema_v, model_v))

    def update(self, model):
        self._update(model, update_fn=lambda e, m: self.decay * e + (1. - self.decay) * m)

    def set(self, model):
        self._update(model, update_fn=lambda e, m: m)
# -----------------------------------------------------------
# [수정됨] 외부 LPU 제거 및 내부 로직 변경된 CMTClassifier
# -----------------------------------------------------------
class CMTClassifier(nn.Module):
    def __init__(
            self,
            num_classes: int,
            stem_channels: int = 64,
            c_stage1: int = 96,
            c_stage2: int = 128,
            c_stage3: int = 160,
            t_dim1: int = 256,  t_heads1: int = 4,  t_depth1: int = 3,  t_mlp1: float = 3.0,
            t_dim2: int = 384,  t_heads2: int = 6,  t_depth2: int = 6,  t_mlp2: float = 3.5,
            attn_drop: float = 0.0,
            proj_drop: float = 0.1,
            drop_path_rate: float = 0.0,
            input_channels: int = 4, #이걸로 A넣을거임
    ):
        super().__init__()
        self.num_classes = num_classes

        # ----- CNN stem (224 -> 112) -----
        self.stem = nn.Sequential(
            ConvBNGELU(input_channels, stem_channels // 2, k=3, s=2, p=1),  # ⭐ 3 → input_channels
            ConvBNGELU(stem_channels // 2, stem_channels, k=3, s=1, p=1),
        )

        # ----- CNN stages (112 -> 56 -> 28 -> 14) -----
        self.stage1 = ConvStage(stem_channels, c_stage1)
        self.stage2 = ConvStage(c_stage1, c_stage2)
        self.stage3 = ConvStage(c_stage2, c_stage3)

        # ----- to embed (14x14, C3 -> D1) -----
        self.to_embed1 = nn.Conv2d(c_stage3, t_dim1, kernel_size=1, stride=1, padding=0, bias=True)

        # ----- Stage A @14x14 : Transformer(depth=t_depth1) -----
        # [삭제됨] self.lpu1 = LPU(t_dim1) <- 이제 블록 안에 있음

        dpr1 = torch.linspace(0, drop_path_rate * 0.5, steps=t_depth1).tolist()
        self.trans1 = nn.Sequential(*[
            TransformerBlock(
                dim=t_dim1, num_heads=t_heads1, mlp_ratio=t_mlp1,
                attn_drop=attn_drop, proj_drop=proj_drop, drop_path=dpr1[i]
            ) for i in range(t_depth1)
        ])

        # ----- down tokens: 14->7, D1->D2 -----
        self.down_tokens = nn.Sequential(
            nn.Conv2d(t_dim1, t_dim2, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(t_dim2, eps=1e-5, momentum=0.1),
            nn.GELU(),
        )

        # ----- Stage B @7x7 : Transformer(depth=t_depth2) -----
        # [삭제됨] self.lpu2 = LPU(t_dim2) <- 이제 블록 안에 있음

        dpr2 = torch.linspace(drop_path_rate * 0.5, drop_path_rate, steps=t_depth2).tolist()
        self.trans2 = nn.Sequential(*[
            TransformerBlock(
                dim=t_dim2, num_heads=t_heads2, mlp_ratio=t_mlp2,
                attn_drop=attn_drop, proj_drop=proj_drop, drop_path=dpr2[i]
            ) for i in range(t_depth2)
        ])

        # ----- Head -----
        self.head_norm = nn.LayerNorm(t_dim2, eps=1e-6)
        self.fc        = nn.Linear(t_dim2, num_classes)

        self.apply(self._init_weights)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None: nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.Conv2d):
            nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            if m.bias is not None: nn.init.constant_(m.bias, 0)
        elif isinstance(m, (nn.LayerNorm, nn.BatchNorm2d)):
            if hasattr(m, "weight") and m.weight is not None: nn.init.ones_(m.weight)
            if hasattr(m, "bias") and m.bias is not None:     nn.init.zeros_(m.bias)

    def forward(self, x):
        # CNN 얕은 특징
        x = self.stem(x)          # 224 -> 112
        x = self.stage1(x)        # 112 -> 56
        x = self.stage2(x)        # 56  -> 28
        x = self.stage3(x)        # 28  -> 14

        # 임베딩 (채널 C3 -> T_dim1)
        x = self.to_embed1(x)     # B x D1 x 14 x 14

        # [수정됨] Stage A: Flatten 먼저 -> Transformer (내부에서 LPU 처리)
        x = x.flatten(2).transpose(1, 2)           # B x 196 x D1 (패치 토큰화)
        x = self.trans1(x)                         # Transformer (내부에 LPU 포함됨)

        # Downsample을 위해 다시 이미지 형태로 복구
        B, N, C = x.shape
        H = W = int(math.sqrt(N)) # 14
        x = x.transpose(1, 2).view(B, C, H, W)     # 다시 (B, D1, 14, 14)

        # Downsample tokens: 14 -> 7
        x = self.down_tokens(x)                    # B x D2 x 7 x 7

        # [수정됨] Stage B: Flatten 먼저 -> Transformer (내부에서 LPU 처리)
        x = x.flatten(2).transpose(1, 2)           # B x 49 x D2
        x = self.trans2(x)                         # Transformer (내부에 LPU 포함됨)

        # Head
        x = x.mean(dim=1)                          # GAP
        x = self.head_norm(x)
        logits = self.fc(x)
        return logits
# ------------------------------------------------------------

def rgba_val_to_tensor(img: Image.Image) -> torch.Tensor:
    """
    ✅ 검증용: 고정 resize/center crop, 증강 없음
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    r, g, b, a = img.split()
    rgb   = Image.merge("RGB", (r, g, b))
    alpha = a

    rgb   = TF.resize(rgb, 256)
    alpha = TF.resize(alpha, 256)
    rgb   = TF.center_crop(rgb, 224)
    alpha = TF.center_crop(alpha, 224)

    rgb_t   = TF.to_tensor(rgb)
    alpha_t = TF.to_tensor(alpha)
    return torch.cat([rgb_t, alpha_t], dim=0)  # (4, 224, 224)

VAL_TRANSFORM = T.Compose([
    T.Lambda(rgba_val_to_tensor),
    T.Normalize(
        [0.485, 0.456, 0.406, 0.5],
        [0.229, 0.224, 0.225, 0.5],
    ),
])

def _extract_state_dict(checkpoint: object) -> dict[str, torch.Tensor]:
    if isinstance(checkpoint, nn.Module):
        return checkpoint.state_dict()
    if not isinstance(checkpoint, dict):
        raise TypeError("Unsupported checkpoint type: expected dict or nn.Module")

    possible_keys = ("model_state_dict", "state_dict", "model")
    for key in possible_keys:
        value = checkpoint.get(key)  # type: ignore[call-arg]
        if isinstance(value, dict):
            return value  # type: ignore[return-value]
    return checkpoint  # type: ignore[return-value]


def load_cmt_model(model_path: Path, num_classes: int, device: torch.device) -> Tuple[nn.Module, Tuple[str, ...], Tuple[str, ...]]:
    """
    - 체크포인트의 다양한 형태(dict/nn.Module) 지원
    - DataParallel 등의 'module.' 접두사 제거
    - stage*.ds.*  <->  stage*.downsample.* 키 자동 리매핑
    - 먼저 strict=True로 로드 → 실패 시 리매핑 시도 → 그래도 안 되면 오류 메시지에 누락/예상치 못한 키를 자세히 포함
    - fc(out_features)와 num_classes 불일치 시 명확한 예외
    """
    ckpt = torch.load(model_path, map_location=device)

    def _extract_state_dict(obj) -> Dict[str, torch.Tensor]:
        if isinstance(obj, nn.Module):
            return obj.state_dict()
        if not isinstance(obj, dict):
            raise TypeError(f"Unsupported checkpoint type: {type(obj)}")
        for key in ("model_state_dict", "state_dict", "model"):
            v = obj.get(key)
            if isinstance(v, dict):
                return v
        return obj  # raw state_dict

    def _strip_module_prefix(sd: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        # 'module.'로 시작하면 제거
        if any(k.startswith("module.") for k in sd.keys()):
            return {k.replace("module.", "", 1): v for k, v in sd.items()}
        return sd

    def _remap_ds_downsample(sd: Dict[str, torch.Tensor], to: str) -> Dict[str, torch.Tensor]:
        """
        to == 'downsample' : stage*.ds.* -> stage*.downsample.*
        to == 'ds'         : stage*.downsample.* -> stage*.ds.*
        """
        out = {}
        for k, v in sd.items():
            if to == "downsample":
                k2 = (k.replace("stage1.ds.", "stage1.downsample.")
                      .replace("stage2.ds.", "stage2.downsample.")
                      .replace("stage3.ds.", "stage3.downsample."))
            else:
                k2 = (k.replace("stage1.downsample.", "stage1.ds.")
                      .replace("stage2.downsample.", "stage2.ds.")
                      .replace("stage3.downsample.", "stage3.ds."))
            out[k2] = v
        return out

    # 1) state_dict 정규화
    sd = _extract_state_dict(ckpt)
    sd = _strip_module_prefix(sd)

    # 2) 모델 생성
    model = CMTClassifier(num_classes=num_classes, input_channels=4)

    # 3) fc(out_features)와 num_classes 일치 검증 (실패 시 바로 알려줌)
    fc_out = getattr(model, "fc", None)
    if hasattr(fc_out, "out_features") and fc_out.out_features != num_classes:
        raise ValueError(
            f"[load_cmt_model] num_classes({num_classes}) != model.fc.out_features({fc_out.out_features}). "
            "훈련 당시 라벨 개수/순서와 현재 labels.json이 다른지 확인하세요."
        )

    # 4) 우선 strict=True로 그대로 시도
    try:
        model.load_state_dict(sd, strict=True)
        model.to(device).eval()
        return model, (), ()
    except RuntimeError as e1:
        # 5) 키 패턴 보고 리매핑 방향 결정
        keys = list(sd.keys())
        has_ds = any(".ds." in k for k in keys)
        has_down = any(".downsample." in k for k in keys)

        # 현재 코드가 downsample를 쓰는 경우가 대부분이므로, 체크포인트가 ds면 downsample로 리매핑
        if has_ds and not has_down:
            sd2 = _remap_ds_downsample(sd, to="downsample")
        elif has_down and not has_ds:
            # 혹시 반대 상황이면 반대로
            sd2 = _remap_ds_downsample(sd, to="ds")
        else:
            sd2 = sd  # 패턴 판별 불가 → 원본 유지

        try:
            model.load_state_dict(sd2, strict=True)
            model.to(device).eval()
            return model, (), ()
        except RuntimeError as e2:
            # 6) 디버그용으로 missing/unexpected 키를 뽑아주기 위해 strict=False로 한 번 계산
            missing, unexpected = model.load_state_dict(sd2, strict=False)
            # 더 명확한 에러 메시지로 실패 이유 전달
            raise RuntimeError(
                "[load_cmt_model] state_dict 로딩 실패\n"
                f"- 1차(strict=True, 원본) 오류: {e1}\n"
                f"- 2차(strict=True, 리매핑) 오류: {e2}\n"
                f"- 참고: missing={sorted(missing)}, unexpected={sorted(unexpected)}"
            )

__all__ = [
    "CMTClassifier",
    "DropPath",
    "VAL_TRANSFORM",
    "load_cmt_model",
]