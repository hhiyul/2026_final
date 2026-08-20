"""한글 쿼리를 FashionSigLIP가 읽을 수 있는 영어로 바꾼다 — 사전 치환 방식.

**왜 번역기가 아니라 사전인가**

FashionSigLIP의 토크나이저에는 한글이 없다. 한글을 그대로 넣으면 전부 UNK가 되어
"파란 청바지"와 "야구 모자"가 같은 벡터가 된다(전체 P@5 87.3% → 6.4%).
번역이 필수인데, 방식을 실측으로 비교했더니 결과가 예상과 달랐다.

    조건            아이템 Top1   전체 P@5
    영어 원본            93.8%     87.3%
    한글 직접             0.0%      6.4%
    로컬 번역 모델         68.8%     62.7%   ← opus-mt-ko-en
    사전 치환           100.0%     89.1%   ← 이 모듈

**번역기가 진 이유는 패션 한국어가 대부분 영어 외래어이기 때문이다.**
일반 번역기는 이를 원래 영어로 되돌리지 못하고 음차해버린다:

    데님 자켓  → Deim's jacket   (denim)
    니트 스웨터 → Nit sweater     (knit)
    플리스     → Fliss           (fleece)
    반바지     → Vandals         (shorts)
    쿨톤      → Koulton          (cool tone)

사전은 원래 단어를 정확히 복원하므로 오히려 번역기보다 낫다. 외부 API·모델이
필요 없어 비용·지연·네트워크 의존이 전부 0이고, 같은 입력에 같은 출력을 준다.

**한계**: 사전에 없는 순우리말·한자어 표현(예: "청량한", "차분한")은 제거된다.
사전을 넓히거나, 남은 한글이 많으면 번역 API로 폴백하는 하이브리드를 검토한다.
`has_unmapped()`가 그 판단에 쓰인다.
"""

import re

# ⚠ 이 목록의 **작성 순서는 의미가 없다.** 적용 시 길이 내림차순으로 정렬한다
# (아래 _SORTED). 짧은 항목이 먼저 걸리면 긴 단어가 망가지기 때문이다 —
# "울"(wool)이 "겨울"보다 먼저 적용되면 "겨울"이 "winter"가 아니라 "wool"이 된다.
#
# 같은 이유로 **1글자 항목은 넣지 않는다.** "면"(cotton)은 "측면"에, "티"(t-shirt)는
# "파티"에 걸린다. 1글자로만 표현되는 개념은 더 긴 형태로 적는다.
FASHION_KO_EN = [
    # --- 아이템 ---
    ("청바지", "jeans"), ("데님", "denim"), ("니트", "knit"), ("스웨터", "sweater"),
    ("맨투맨", "sweatshirt"), ("후드집업", "zip up hoodie"), ("후드", "hooded"),
    ("티셔츠", "t-shirt"), ("코트", "coat"),
    ("패딩", "puffer down"), ("점퍼", "jacket"), ("플리스", "fleece"),
    ("무스탕", "shearling"), ("블레이저", "blazer"), ("자켓", "jacket"),
    ("재킷", "jacket"), ("가디건", "cardigan"), ("셔츠", "shirt"),
    ("버튼업", "button up"), ("슬랙스", "slacks"), ("트레이닝", "track"),
    ("팬츠", "pants"), ("반바지", "shorts"), ("숏팬츠", "shorts"),
    ("치마", "skirt"), ("스커트", "skirt"), ("원피스", "dress"),
    ("바지", "trousers"), ("정장", "suit"), ("조끼", "vest"), ("베스트", "vest"),
    # --- 소매·기장 ---
    ("반팔", "short sleeve"), ("긴팔", "long sleeve"), ("민소매", "sleeveless"),
    ("크롭", "cropped"), ("오버핏", "oversized"), ("루즈핏", "loose fit"),
    ("슬림핏", "slim fit"),
    # --- 모자 ---
    ("야구모자", "baseball cap"), ("볼캡", "baseball cap"), ("버킷햇", "bucket hat"),
    ("비니", "beanie"), ("모자", "cap"), ("야구", "baseball"),
    # --- 무드·스타일 (대부분 외래어라 사전이 특히 잘 통한다) ---
    ("쿨톤", "cool tone"), ("웜톤", "warm tone"), ("스트릿", "street"),
    ("미니멀", "minimal"), ("포멀", "formal"), ("캐주얼", "casual"),
    ("스포티", "sporty"), ("빈티지", "vintage"), ("클래식", "classic"),
    ("모던", "modern"), ("러블리", "lovely"), ("시크", "chic"),
    ("댄디", "dandy"), ("아메카지", "americana casual"),
    ("오피스", "office"), ("비즈니스", "business"), ("데일리", "daily"),
    ("스타일", "style"), ("룩", "look"), ("코디", "outfit"),
    ("옷차림", "outfit"), ("운동복", "athletic wear"), ("울코트", "wool coat"),
    # --- 색 ---
    ("파란", "blue"), ("파랑", "blue"), ("빨간", "red"), ("빨강", "red"),
    ("검은", "black"), ("검정", "black"), ("하얀", "white"), ("흰색", "white"),
    ("회색", "gray"), ("베이지", "beige"), ("네이비", "navy"),
    ("카키", "khaki"), ("갈색", "brown"), ("초록", "green"), ("노란", "yellow"),
    # --- 소재 ---
    ("울소재", "wool"), ("코튼", "cotton"), ("가죽", "leather"),
    ("스웨이드", "suede"), ("퍼자켓", "fur jacket"), ("린넨", "linen"), ("실크", "silk"),
    ("코듀로이", "corduroy"), ("골덴", "corduroy"),
    # --- 계절·느낌 ---
    # ⚠ "봄"은 넣지 않는다. "추천해봄", "입어봄" 같은 어미에 걸린다
    ("겨울", "winter"), ("여름", "summer"), ("가을", "autumn"),
    ("봄옷", "spring clothes"), ("봄에", "spring"),
    ("따뜻하고", "warm"), ("따뜻한", "warm"), ("포근한", "cozy"),
    ("시원한", "cool"), ("깔끔한", "neat"), ("편안한", "comfortable"),
    ("귀여운", "cute"), ("세련된", "sophisticated"), ("심플한", "simple"),
    ("화려한", "colorful"), ("무난한", "basic"),
    # --- 수식 ---
    # ⚠ "긴"은 넣지 않는다. "따뜻하긴 한데" 같은 어미에 걸린다. "롱"을 쓴다
    ("롱", "long"), ("짧은", "short"), ("두꺼운", "thick"), ("얇은", "thin"),
]

# 1글자로 두어도 안전하다고 검증한 항목만. 나머지 1글자는 금지다
# ("면"은 "측면"에, "티"는 "파티"에, "긴"은 "따뜻하긴"에 걸린다)
ALLOWED_SINGLE = {"롱", "룩"}

# 길이 내림차순. 부분 문자열 충돌을 막는 핵심 장치다
_SORTED = sorted(FASHION_KO_EN, key=lambda kv: -len(kv[0]))

_HANGUL = re.compile(r"[가-힣]+")
_SPACES = re.compile(r"\s+")


def to_english(query):
    """한글 쿼리를 영어로 바꾼다. 매핑되지 않은 한글은 제거된다.

    조사·어미("~한", "~의", "추천해줘")는 의미를 거의 담지 않으므로 지워도
    검색 품질에 영향이 없다. 오히려 남기면 UNK 토큰이 되어 방해한다.
    """
    s = query
    for ko, en in _SORTED:
        s = s.replace(ko, f" {en} ")
    s = _HANGUL.sub(" ", s)
    return _SPACES.sub(" ", s).strip()


def has_unmapped(query, min_len=2):
    """사전으로 처리하지 못한 한글이 남는지 본다.

    True면 사전만으로는 부족하다는 신호다. 번역 API 폴백을 붙일지 판단하거나,
    로그로 모아 사전을 넓히는 데 쓴다.
    """
    s = query
    for ko, _ in _SORTED:
        s = s.replace(ko, " ")
    남은것 = [m for m in _HANGUL.findall(s) if len(m) >= min_len]
    return bool(남은것), 남은것


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    샘플 = [
        "파란 청바지", "무스탕 자켓", "쿨톤 스트릿 스타일",
        "따뜻하고 포근한 겨울 옷차림", "오피스 비즈니스 정장",
        "청량한 느낌의 옷 추천해줘",          # 사전에 없는 표현 섞임
    ]
    for q in 샘플:
        남음, 목록 = has_unmapped(q)
        표시 = f"   ⚠ 미매핑: {목록}" if 남음 else ""
        print(f"{q:28s} → {to_english(q)}{표시}")
