export const categories = ["outerwear", "top", "bottom", "headwear"];
export const label = (category) =>
  ({ outerwear: "아우터", top: "상의", bottom: "하의", headwear: "모자" })[
    category
  ] ||
  category ||
  "미분류";
export const categoryKey = (item) => item.category || "미분류";
export function groupItems(items, filter = "all", recommended = false) {
  const groups = new Map();
  for (const item of items) {
    const key = categoryKey(item);
    if (filter !== "all" && key !== filter) continue;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  const order = (key) =>
    categories.includes(key) ? categories.indexOf(key) : categories.length;
  return [...groups]
    .sort(([a], [b]) => order(a) - order(b) || a.localeCompare(b, "ko"))
    .map(([key, values]) => [
      key,
      [...values].sort((a, b) =>
        recommended
          ? (a.rank ?? Infinity) - (b.rank ?? Infinity) ||
            (b.score ?? -Infinity) - (a.score ?? -Infinity)
          : (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0),
      ),
    ]);
}
export function errorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(" / ");
  return error.response
    ? "요청을 처리하지 못했습니다. 다시 시도해 주세요."
    : "서버에 연결하지 못했습니다. 연결 상태를 확인하고 다시 시도해 주세요.";
}
