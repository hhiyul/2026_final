import { useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  categories,
  categoryKey,
  label,
  groupItems,
  errorMessage,
} from "./wardrobe";
import "./App.css";

const baseURL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const api = axios.create({ baseURL });
const imageUrl = (url) =>
  !url
    ? ""
    : /^https?:\/\//.test(url)
      ? url
      : `${baseURL}/${url.replace(/^\//, "")}`;
function GarmentImage({ item, className = "" }) {
  const [failed, setFailed] = useState(false);
  return failed || !item.thumbnail_url ? (
    <div className={`image-fallback ${className}`}>
      이미지를 불러올 수 없습니다
    </div>
  ) : (
    <img
      className={className}
      src={imageUrl(item.thumbnail_url)}
      alt={`${label(item.category)} 의류`}
      onError={() => setFailed(true)}
      loading="lazy"
    />
  );
}
function Modal({ title, onClose, children, busy }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current.showModal();
    return () => previous?.focus();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-inner">
        <div className="section-heading">
          <h2 id="modal-title">{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            disabled={busy}
            aria-label="닫기"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export default function App() {
  const [userId, setUserId] = useState("test_user");
  const [password, setPassword] = useState("");
  const [tab, setTab] = useState("wardrobe");
  const [items, setItems] = useState([]);
  const [results, setResults] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [searched, setSearched] = useState(false);
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState(null);
  const [json, setJson] = useState(null);
  const [modal, setModal] = useState(null);
  const [detail, setDetail] = useState(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const fileInput = useRef(null);
  const requestLock = useRef(false);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  const notify = (message, type = "success") => setNotice({ message, type });
  const run = async (action, callback) => {
    if (requestLock.current) return;
    if (!userId.trim()) {
      notify("먼저 사용자 ID를 입력해 주세요.", "error");
      return;
    }
    requestLock.current = true;
    setBusy(action);
    setNotice(null);
    try {
      await callback();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      requestLock.current = false;
      setBusy("");
    }
  };
  const load = async () => {
    const { data } = await api.get("/garments", {
      params: { user_id: userId.trim() },
    });
    setItems(data.items || []);
    setLoaded(true);
    setJson(data);
  };
  const changeUser = (value) => {
    setUserId(value);
    setItems([]);
    setResults([]);
    setLoaded(false);
    setSearched(false);
    setJson(null);
    setNotice(null);
    setFilter("all");
  };
  const switchTab = (value) => {
    setTab(value);
    setFilter("all");
  };
  const chooseFile = (value) => {
    if (!value) return;
    if (!value.type.startsWith("image/")) {
      notify("이미지 파일을 선택해 주세요.", "error");
      return;
    }
    setFile(value);
    setPreview(URL.createObjectURL(value));
    setNotice(null);
  };
  const register = () =>
    run("upload", async () => {
      if (!file) return;
      const body = new FormData();
      body.append("user_id", userId.trim());
      body.append("file", file);
      const { data } = await api.post("/garments", body);
      setJson(data);
      setFile(null);
      setPreview("");
      setModal(null);
      switchTab("wardrobe");
      try {
        await load();
        notify("옷을 등록했습니다. 내 옷장에서 확인해 보세요.");
      } catch {
        notify(
          "옷은 등록되었지만 목록을 갱신하지 못했습니다. 새로고침을 눌러 주세요.",
          "error",
        );
      }
    });
  const recommend = (event) => {
    event.preventDefault();
    if (!query.trim()) return;
    run("recommend", async () => {
      const { data } = await api.post("/recommend", {
        user_id: userId.trim(),
        query: query.trim(),
        top_k: 5,
      });
      setResults(data.results || []);
      setSearched(true);
      setLastQuery(query.trim());
      setJson(data);
      setFilter("all");
    });
  };
  const createUser = (event) => {
    event.preventDefault();
    run("user", async () => {
      const { data } = await api.post("/users", {
        user_id: userId.trim(),
        password,
      });
      setJson(data);
      setPassword("");
      setModal(null);
      notify("사용자를 등록했습니다. 이제 옷을 추가해 보세요.");
    });
  };
  const deleteItem = (event) => {
    event.preventDefault();
    run("delete", async () => {
      const id = detail.items[detail.index].garment_id;
      const { data } = await api.delete(`/garments/${id}`, {
        data: { user_id: userId.trim(), password: deletePassword },
      });
      setItems((old) => old.filter((item) => item.garment_id !== id));
      setResults((old) => old.filter((item) => item.garment_id !== id));
      setJson(data);
      setDetail(null);
      setModal(null);
      setDeletePassword("");
      notify("옷을 삭제했습니다.");
    });
  };
  const activeItems = tab === "wardrobe" ? items : results;
  const groups = groupItems(activeItems, filter, tab === "recommend");
  const orderedItems = groups.flatMap(([, values]) => values);
  const availableCategories = [
    ...new Set([...categories, ...activeItems.map(categoryKey)]),
  ];
  const selected = detail?.items[detail.index];
  const closeModal = () => {
    if (!busy) {
      setModal(null);
      setDetail(null);
      setPassword("");
      setDeletePassword("");
    }
  };
  const status = notice && (
    <div
      className={`notice ${notice.type}`}
      role={notice.type === "error" ? "alert" : "status"}
    >
      {notice.message}
    </div>
  );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        본문으로 이동
      </a>
      <aside className="sidebar">
        <a href="#main" className="brand">
          <span className="brand-mark">W</span>
          <span>
            wearly<span className="brand-caption">나를 위한 스마트 옷장</span>
          </span>
        </a>
        <p className="nav-caption">MY SPACE</p>
        <nav aria-label="주요 메뉴">
          <button
            className={tab === "wardrobe" ? "nav-item active" : "nav-item"}
            onClick={() => switchTab("wardrobe")}
          >
            <span aria-hidden="true">▦</span> 내 옷장{" "}
            <span className="nav-count">{loaded ? items.length : "—"}</span>
          </button>
          <button
            className={tab === "recommend" ? "nav-item active" : "nav-item"}
            onClick={() => switchTab("recommend")}
          >
            <span aria-hidden="true">✧</span> AI 추천
          </button>
        </nav>
        <div className="sidebar-tip">
          <span>YOUR DAILY INSPIRATION</span>
          <h3>
            있는 옷으로,
            <br />
            새로운 나를 발견해요.
          </h3>
          <p>
            원하는 분위기를 말하면
            <br />내 옷장에서 어울리는 옷을 찾아요.
          </p>
        </div>
        <div className="account">
          <label htmlFor="user-id">사용자 ID</label>
          <input
            id="user-id"
            value={userId}
            onChange={(event) => changeUser(event.target.value)}
            disabled={!!busy}
            autoComplete="username"
          />
          <p>ID별로 저장된 옷장을 조회합니다.</p>
          <button
            className="text-button"
            onClick={() => {
              setNotice(null);
              setModal("user");
            }}
            disabled={!!busy}
          >
            새 사용자 등록 →
          </button>
        </div>
      </aside>
      <main id="main">
        <header className="topbar">
          <span>
            MY WARDROBE / {tab === "wardrobe" ? "COLLECTION" : "AI STYLING"}
          </span>
          <span className="user-chip">
            <span className="user-dot" />
            {userId.trim() || "사용자 ID를 입력하세요"}
          </span>
        </header>
        <div className="page-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                {tab === "wardrobe"
                  ? "EVERY PIECE, YOUR STYLE"
                  : "A LITTLE INSPIRATION"}
              </p>
              <h1>
                {tab === "wardrobe" ? "내 옷장" : "오늘, 어떤 분위기인가요?"}
              </h1>
              <p>
                {tab === "wardrobe"
                  ? "가지고 있는 옷을 한눈에 보고, 새로운 조합을 발견하세요."
                  : "원하는 스타일을 알려 주세요. 내 옷장에서 어울리는 옷을 찾아드릴게요."}
              </p>
            </div>
            <button
              className="primary"
              onClick={() => {
                setNotice(null);
                setModal("upload");
              }}
              disabled={!!busy}
            >
              ＋ 옷 추가하기
            </button>
          </div>
          {!modal && status}
          {tab === "wardrobe" ? (
            <section className="intro-banner">
              <div>
                <span className="eyebrow">YOUR PERSONAL COLLECTION</span>
                <h2>취향이 모이는 공간</h2>
                <p>
                  옷을 등록하면 AI가 라벨을 분류해요.
                  <br />
                  아우터부터 모자까지, 찾기 쉽게 정리하세요.
                </p>
                <button
                  className="banner-link"
                  onClick={() => switchTab("recommend")}
                >
                  내 옷으로 추천받기 <span>↗</span>
                </button>
              </div>
              <div className="wardrobe-art" aria-hidden="true">
                <div className="art-card art-one">
                  <svg viewBox="0 0 100 110">
                    <path
                      d="M30 15 10 30 22 48 32 42 32 96 68 96 68 42 78 48 90 30 70 15 61 20Q50 31 39 20Z"
                      fill="#faf8f2"
                      stroke="#9aa789"
                      strokeWidth="2"
                    />
                  </svg>
                  <span>MY FAVORITES</span>
                </div>
                <div className="art-card art-two">
                  <svg viewBox="0 0 100 110">
                    <path
                      d="M29 12H71L78 98H55L50 48 45 98H22Z"
                      fill="#55664f"
                    />
                    <path
                      d="M30 24H70M50 14V42"
                      stroke="#98a78f"
                      strokeWidth="2"
                    />
                  </svg>
                  <span>EVERYDAY ESSENTIALS</span>
                </div>
              </div>
            </section>
          ) : (
            <section className="recommend-box">
              <form onSubmit={recommend}>
                <label htmlFor="style-query">어떤 스타일을 찾고 있나요?</label>
                <div className="query-row">
                  <input
                    id="style-query"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="예: 쿨톤 스트릿하게, 편안한 주말 캐주얼"
                    required
                    disabled={!!busy}
                  />
                  <button
                    className="primary"
                    disabled={!!busy || !query.trim()}
                  >
                    {busy === "recommend"
                      ? "어울리는 옷 찾는 중…"
                      : "✧ 추천받기"}
                  </button>
                </div>
                <div className="suggestions">
                  {[
                    "쿨톤 스트릿하게",
                    "편안한 주말 캐주얼",
                    "차분한 미니멀룩",
                  ].map((text) => (
                    <button
                      type="button"
                      key={text}
                      onClick={() => setQuery(text)}
                      disabled={!!busy}
                    >
                      {text} ↗
                    </button>
                  ))}
                </div>
                <p className="helper">
                  저장된 옷에서 최대 5개를 추천합니다. 라벨 안에서는 추천 순위를
                  유지해요.
                </p>
              </form>
            </section>
          )}
          <section
            className="collection"
            aria-busy={busy === "load" || busy === "recommend"}
          >
            <div className="section-heading">
              <h2>
                {tab === "wardrobe" ? "나의 컬렉션" : "추천 결과"}{" "}
                <span className="total">{activeItems.length}</span>
              </h2>
              {tab === "wardrobe" && (
                <button
                  className="secondary"
                  onClick={() => run("load", load)}
                  disabled={!!busy}
                >
                  {busy === "load"
                    ? "불러오는 중…"
                    : loaded
                      ? "↻ 새로고침"
                      : "옷장 불러오기"}
                </button>
              )}
            </div>
            {tab === "recommend" && searched && (
              <p className="result-query">“{lastQuery}”에 어울리는 옷</p>
            )}
            <div
              className="filter-row"
              role="group"
              aria-label="의류 라벨 필터"
            >
              {["all", ...availableCategories].map((key) => (
                <button
                  key={key}
                  aria-pressed={filter === key}
                  className={filter === key ? "filter selected" : "filter"}
                  onClick={() => setFilter(key)}
                >
                  {key === "all" ? "전체" : label(key)}{" "}
                  <span>
                    {key === "all"
                      ? activeItems.length
                      : activeItems.filter((item) => categoryKey(item) === key)
                          .length}
                  </span>
                </button>
              ))}
            </div>
            <div className="sort-caption">
              {tab === "wardrobe"
                ? "라벨별 보기 · 라벨 내 최신 등록순"
                : "라벨별 보기 · 라벨 내 추천순"}
            </div>
            {busy === "load" || busy === "recommend" ? (
              <div className="empty-state" role="status">
                <div className="spinner" />
                <h3>
                  {busy === "load"
                    ? "옷장을 불러오고 있어요"
                    : "스타일에 어울리는 옷을 찾고 있어요"}
                </h3>
                <p>잠시만 기다려 주세요.</p>
              </div>
            ) : groups.length ? (
              groups.map(([key, values]) => (
                <section className="category-section" key={key}>
                  <h3>
                    {label(key)} <span>{values.length}</span>
                  </h3>
                  <div className="garment-grid">
                    {values.map((item, index) => (
                      <button
                        className="garment-card"
                        key={item.garment_id || `${key}-${index}`}
                        onClick={() => {
                          setDetail({
                            items: orderedItems,
                            index: orderedItems.indexOf(item),
                          });
                          setNotice(null);
                          setModal("detail");
                        }}
                      >
                        <div className="garment-photo">
                          <GarmentImage key={item.thumbnail_url} item={item} />
                          {tab === "recommend" && item.rank != null && (
                            <span className="rank-badge">
                              추천 {item.rank}위
                            </span>
                          )}
                          <span className="view-detail">자세히 보기 ↗</span>
                        </div>
                        <div className="garment-info">
                          <span>
                            <strong>{label(item.category)}</strong>
                            <small>
                              {tab === "recommend"
                                ? `유사도 점수 ${item.score ?? "—"}`
                                : item.created_at
                                  ? item.created_at
                                      .slice(0, 10)
                                      .replaceAll("-", ".") + " 등록"
                                  : "내 옷장에 저장됨"}
                            </small>
                          </span>
                          <span className="card-arrow">↗</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
              ))
            ) : (
              <div className="empty-state">
                <span className="empty-icon" aria-hidden="true">
                  {tab === "wardrobe" ? "▦" : "✧"}
                </span>
                <h3>
                  {filter !== "all"
                    ? `${label(filter)} 항목이 없어요`
                    : tab === "wardrobe"
                      ? loaded
                        ? "첫 번째 옷을 추가해 보세요"
                        : "내 옷장을 불러와 주세요"
                      : searched
                        ? "추천할 옷을 찾지 못했어요"
                        : "오늘의 스타일을 찾아보세요"}
                </h3>
                <p>
                  {filter !== "all"
                    ? "다른 라벨을 선택하거나 전체 옷을 확인하세요."
                    : tab === "wardrobe"
                      ? loaded
                        ? "사진 한 장으로 나만의 컬렉션을 시작할 수 있어요."
                        : "왼쪽 사용자 ID를 확인한 뒤 옷장을 불러오세요."
                      : searched
                        ? "옷을 등록하거나 다른 스타일로 다시 검색해 보세요."
                        : "위에 원하는 분위기를 입력하면 추천 결과가 여기에 표시돼요."}
                </p>
                {filter !== "all" ? (
                  <button
                    className="secondary"
                    onClick={() => setFilter("all")}
                  >
                    전체 보기
                  </button>
                ) : (
                  tab === "wardrobe" && (
                    <button
                      className="secondary"
                      disabled={!!busy}
                      onClick={() =>
                        loaded ? setModal("upload") : run("load", load)
                      }
                    >
                      {loaded ? "＋ 첫 옷 추가하기" : "옷장 불러오기"}
                    </button>
                  )
                )}
              </div>
            )}
          </section>
          <details className="debug">
            <summary>응답 데이터 확인</summary>
            <pre>
              {JSON.stringify(json, null, 2) ||
                "아직 요청한 데이터가 없습니다."}
            </pre>
          </details>
          <footer>
            wearly <span>매일의 선택을 조금 더 가볍게.</span>
          </footer>
        </div>
      </main>
      {modal && (
        <Modal
          title={
            {
              user: "새 사용자 등록",
              upload: "내 옷장에 옷 추가",
              detail: "의류 상세",
              delete: "옷을 삭제할까요?",
            }[modal]
          }
          onClose={closeModal}
          busy={!!busy}
        >
          {status}
          {modal === "user" && (
            <form onSubmit={createUser}>
              <p className="modal-description">
                사용자 ID로 옷장을 관리하고, 비밀번호로 옷 삭제를 확인해요.
              </p>
              <label htmlFor="new-user">사용자 ID</label>
              <input
                id="new-user"
                value={userId}
                onChange={(event) => changeUser(event.target.value)}
                disabled={!!busy}
                required
                autoComplete="username"
              />
              <label htmlFor="new-password">비밀번호</label>
              <input
                id="new-password"
                type="password"
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={!!busy}
                autoComplete="new-password"
              />
              <p className="helper">8자 이상 입력해 주세요.</p>
              <button className="primary full" disabled={!!busy}>
                {busy === "user" ? "등록 중…" : "사용자 등록"}
              </button>
            </form>
          )}
          {modal === "upload" && (
            <>
              <p className="modal-description">
                옷이 잘 보이는 사진을 선택하세요. AI가 의류를 찾아 자동으로
                분류합니다.
              </p>
              <input
                ref={fileInput}
                type="file"
                accept="image/*"
                className="sr-only"
                id="garment-file"
                disabled={!!busy}
                onChange={(event) => {
                  chooseFile(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
              <button
                className="upload-zone"
                disabled={!!busy}
                onClick={() => fileInput.current.click()}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  if (!busy) chooseFile(event.dataTransfer.files[0]);
                }}
              >
                {file && preview ? (
                  <img src={preview} alt="등록할 의류 미리보기" />
                ) : (
                  <>
                    <span className="upload-symbol">＋</span>
                    <strong>사진을 선택하거나 여기로 끌어오세요</strong>
                    <span>한 번에 이미지 1장</span>
                  </>
                )}
              </button>
              {file && (
                <div className="file-caption">
                  <span>{file.name}</span>
                  <button
                    className="text-button"
                    disabled={!!busy}
                    onClick={() => {
                      setFile(null);
                      setPreview("");
                    }}
                  >
                    제거
                  </button>
                </div>
              )}
              <p className="helper">
                현재 사용자: {userId || "ID를 먼저 입력해 주세요"}
              </p>
              <button
                className="primary full"
                onClick={register}
                disabled={!!busy || !file}
              >
                {busy === "upload"
                  ? "AI가 옷을 분석하고 저장 중…"
                  : "옷 등록하기"}
              </button>
            </>
          )}
          {(modal === "detail" || modal === "delete") && selected && (
            <>
              <GarmentImage
                key={selected.thumbnail_url}
                item={selected}
                className="detail-image"
              />
              {modal === "detail" ? (
                <>
                  <dl className="detail-data">
                    <div>
                      <dt>라벨</dt>
                      <dd>{label(selected.category)}</dd>
                    </div>
                    {selected.rank != null && (
                      <div>
                        <dt>추천 순위</dt>
                        <dd>{selected.rank}위</dd>
                      </div>
                    )}
                    {selected.score != null && (
                      <div>
                        <dt>유사도 점수</dt>
                        <dd>{selected.score}</dd>
                      </div>
                    )}
                    {selected.conf != null && (
                      <div>
                        <dt>검출 신뢰도</dt>
                        <dd>{(selected.conf * 100).toFixed(1)}%</dd>
                      </div>
                    )}
                    {selected.created_at && (
                      <div>
                        <dt>등록일시</dt>
                        <dd>{selected.created_at.replace("T", " ")}</dd>
                      </div>
                    )}
                  </dl>
                  <div className="detail-navigation">
                    <button
                      className="secondary"
                      disabled={detail.index === 0}
                      onClick={() =>
                        setDetail({ ...detail, index: detail.index - 1 })
                      }
                    >
                      ← 이전
                    </button>
                    <span>
                      {detail.index + 1} / {detail.items.length}
                    </span>
                    <button
                      className="secondary"
                      disabled={detail.index === detail.items.length - 1}
                      onClick={() =>
                        setDetail({ ...detail, index: detail.index + 1 })
                      }
                    >
                      다음 →
                    </button>
                  </div>
                  <button
                    className="text-button danger-text"
                    disabled={!!busy || !selected.garment_id}
                    onClick={() => {
                      setDeletePassword("");
                      setModal("delete");
                    }}
                  >
                    이 옷 삭제하기
                  </button>
                </>
              ) : (
                <form onSubmit={deleteItem}>
                  <p className="modal-description">
                    {label(selected.category)} 항목이 옷장과 추천 결과에서
                    삭제됩니다. 삭제 후 복구할 수 없습니다.
                  </p>
                  <label htmlFor="delete-password">사용자 비밀번호</label>
                  <input
                    id="delete-password"
                    type="password"
                    value={deletePassword}
                    onChange={(event) => setDeletePassword(event.target.value)}
                    required
                    disabled={!!busy}
                    autoComplete="current-password"
                  />
                  <div className="modal-actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={!!busy}
                      onClick={() => {
                        setModal("detail");
                        setNotice(null);
                      }}
                    >
                      취소
                    </button>
                    <button
                      className="danger"
                      disabled={!!busy || !deletePassword}
                    >
                      {busy === "delete" ? "삭제 중…" : "삭제하기"}
                    </button>
                  </div>
                </form>
              )}
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
