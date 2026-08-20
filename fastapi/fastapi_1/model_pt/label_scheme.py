"""라벨 체계의 단일 진실 소스.

Tier 1(검출 4종) / Tier 2(프로그램 8종) / Tier 3(원본 폴더 22종)의 매핑을
여기 한 곳에만 둔다. 이 매핑이 여러 스크립트에 흩어지면 나중에 하나만 고쳐서
조용히 어긋난다 — 이 프로젝트에서 가장 여러 번 바뀐 결정이다.

확정 근거는 docs/superpowers/specs/2026-08-04-phase2-autolabeling-design.md 2장.
"""

# ==========================================================
# Tier 1 — 검출 학습 카테고리
# ==========================================================
# ⚠ 이 순서가 YOLO 클래스 인덱스다. 바꾸면 기존 라벨이 전부 무의미해진다.
TIER1_CLASSES = ["outerwear", "top", "bottom", "headwear"]
TIER1_INDEX = {name: i for i, name in enumerate(TIER1_CLASSES)}


# ==========================================================
# Tier 3(원본 폴더 22종) → Tier 1
# ==========================================================
# hoodie_sweat와 knit은 Tier 2 하나가 outerwear/top 경계를 가로지르므로
# Tier 3 단위로 쪼개 배분한다 (지퍼·오픈프론트 = 아우터 / 풀오버 = 상의).
TIER3_TO_TIER1 = {
    # --- outerwear (11종, 15,158장) ---
    "블레이저": "outerwear",
    "9_jacket": "outerwear",
    "청자켓": "outerwear",
    "10_outer_jacket": "outerwear",
    "무스탕": "outerwear",
    "1_coat": "outerwear",
    "2_padding": "outerwear",
    "플리스": "outerwear",
    "3_training_zipup": "outerwear",
    "후드집업": "outerwear",        # 지퍼 아우터
    "가디건": "outerwear",          # 오픈프론트 아우터
    # --- top (5종, 3,406장) ---
    "7_shirt": "top",
    "5_hoodie": "top",              # 풀오버
    "6_shortsleeve": "top",
    "8_knit": "top",                # 풀오버
    "4_sweatshirt": "top",
    # --- bottom (5종, 1,741장) ---
    "슬랙스": "bottom",
    "청바지": "bottom",
    "반바지": "bottom",
    "트레이닝팬츠": "bottom",
    "코튼팬츠": "bottom",
    # --- headwear (1종, 2,898장) ---
    # 사전학습 모델에 모자 클래스가 없는데도 60장 중 52장(86.7%)에서 박스가
    # 생기고, 육안 검토상 박스가 모자를 정확히 감쌌다. 틀린 것은 라벨뿐이라
    # 폴더 라벨로 덮어쓰면 자동라벨링이 성립한다.
    "모자": "headwear",
}


# ==========================================================
# Tier 3 → Tier 2 (프로그램 카테고리 8종)
# ==========================================================
# 추천 시 하드 필터·UI 노출 단위. shorts는 pants에 병합됐다(미해결 4번).
TIER3_TO_TIER2 = {
    "블레이저": "jacket",
    "9_jacket": "jacket",
    "청자켓": "jacket",
    "10_outer_jacket": "jacket",
    "후드집업": "hoodie_sweat",
    "5_hoodie": "hoodie_sweat",
    "4_sweatshirt": "hoodie_sweat",
    "모자": "hat",
    "무스탕": "coat",
    "1_coat": "coat",
    "2_padding": "coat",
    "7_shirt": "shirt_tee",
    "6_shortsleeve": "shirt_tee",
    "가디건": "knit",
    "8_knit": "knit",
    "슬랙스": "pants",
    "청바지": "pants",
    "트레이닝팬츠": "pants",
    "코튼팬츠": "pants",
    "반바지": "pants",              # 병합됨 (구 shorts)
    "플리스": "fleece_zipup",
    "3_training_zipup": "fleece_zipup",
}


# ==========================================================
# 원본 장수 (merge_classes.py 실행 결과, 검증용)
# ==========================================================
TIER3_COUNTS = {
    "블레이저": 2515, "9_jacket": 2156, "청자켓": 1731, "10_outer_jacket": 704,
    "무스탕": 1412, "1_coat": 639, "2_padding": 395,
    "플리스": 908, "3_training_zipup": 116,
    "후드집업": 2865, "가디건": 1717,
    "7_shirt": 1541, "5_hoodie": 666, "6_shortsleeve": 568,
    "8_knit": 391, "4_sweatshirt": 240,
    "슬랙스": 1131, "청바지": 341, "반바지": 139,
    "트레이닝팬츠": 102, "코튼팬츠": 28,
    "모자": 2898,
}


# ==========================================================
# DeepFashion2 13종 (사전학습 모델 출력) → Tier 1
# ==========================================================
# ⚠ 이 순서는 모델이 정한 것이다. 바꾸면 안 된다.
DF2_CLASSES = [
    "short_sleeved_shirt", "long_sleeved_shirt", "short_sleeved_outwear",
    "long_sleeved_outwear", "vest", "sling", "shorts", "trousers", "skirt",
    "short_sleeved_dress", "long_sleeved_dress", "vest_dress", "sling_dress",
]

# 원피스류는 Tier 1에 대응이 없어 None이다. 별개 박스가 이걸로 예측되면
# "옷은 있는데 라벨을 정할 수 없는" 상태이므로 이미지째 제외한다.
DF2_TO_TIER1 = {
    "short_sleeved_outwear": "outerwear",
    "long_sleeved_outwear": "outerwear",
    "short_sleeved_shirt": "top",
    "long_sleeved_shirt": "top",
    "vest": "top",
    "sling": "top",
    "shorts": "bottom",
    "trousers": "bottom",
    "skirt": "bottom",
    "short_sleeved_dress": None,
    "long_sleeved_dress": None,
    "vest_dress": None,
    "sling_dress": None,
}


def df2_to_tier1(df2_name):
    """검출 라벨을 Tier 1으로 변환. 대응 없으면 None.

    ⚠ 이 변환의 신뢰도는 축마다 크게 다르다 (330장 실측):
        bottom 98.7% / top 85.3% / outerwear 28.5%
    따라서 별개 박스의 라벨로는 bottom 예측만 채택한다.
    대표 박스는 폴더 라벨로 덮어쓰므로 이 함수를 쓰지 않는다.
    """
    return DF2_TO_TIER1.get(df2_name)
