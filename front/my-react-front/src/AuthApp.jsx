import { useEffect, useRef, useState } from "react";
import WardrobeApp from "./App";
import { api } from "./api";
import { errorMessage } from "./wardrobe";

function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      aria-pressed={theme === "dark"}
      aria-label="다크모드"
    >
      <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>{" "}
      {theme === "dark" ? "라이트 모드" : "다크 모드"}
    </button>
  );
}
function AuthForm({ onLogin, sessionMessage }) {
  const [mode, setMode] = useState("login");
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const lock = useRef(false);
  const signup = mode === "signup";
  const switchMode = (next) => {
    setMode(next);
    setPassword("");
    setConfirmation("");
    setNotice(null);
  };
  const submit = async (event) => {
    event.preventDefault();
    if (lock.current) return;
    if (!userId.trim()) {
      setNotice({ error: true, text: "아이디를 입력해 주세요." });
      return;
    }
    if (signup && password !== confirmation) {
      setNotice({ error: true, text: "비밀번호가 일치하지 않습니다." });
      return;
    }
    lock.current = true;
    setBusy(true);
    setNotice(null);
    try {
      const { data } = await api.post(signup ? "/users" : "/auth/login", {
        user_id: userId.trim(),
        password,
      });
      setPassword("");
      setConfirmation("");
      if (signup) {
        setMode("login");
        setNotice({
          text: "회원가입을 완료했습니다. 등록한 아이디로 로그인해 주세요.",
        });
      } else onLogin(data);
    } catch (error) {
      setNotice({ error: true, text: errorMessage(error) });
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  return (
    <div className="auth-layout">
      <section className="auth-intro">
        <span className="brand-mark">뭐</span>
        <p className="eyebrow">내 옷으로, 나답게.</p>
        <h1>
          오늘도,
          <br />
          뭐입지?
        </h1>
        <p>
          가지고 있는 옷을 모으고,
          <br />
          나에게 어울리는 스타일을 찾아보세요.
        </p>
        <div className="auth-features">
          <span>01 · 사진으로 간편하게 옷 등록</span>
          <span>02 · 라벨별로 한눈에 보는 옷장</span>
          <span>03 · 내 옷으로 받는 AI 추천</span>
        </div>
      </section>
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-tabs" role="group" aria-label="계정 메뉴">
          <button
            aria-pressed={!signup}
            onClick={() => switchMode("login")}
            disabled={busy}
          >
            로그인
          </button>
          <button
            aria-pressed={signup}
            onClick={() => switchMode("signup")}
            disabled={busy}
          >
            회원가입
          </button>
        </div>
        <h2 id="auth-title">
          {signup ? "나만의 옷장을 만들어 보세요" : "다시 만나서 반가워요"}
        </h2>
        <p className="modal-description">
          {signup
            ? "아이디와 비밀번호를 등록하면 준비 끝이에요."
            : "로그인하고 저장한 옷을 만나보세요."}
        </p>
        {(notice || sessionMessage) && (
          <div
            className={`notice ${notice?.error || (!notice && sessionMessage) ? "error" : "success"}`}
            role={
              notice?.error || (!notice && sessionMessage) ? "alert" : "status"
            }
          >
            {notice?.text || sessionMessage}
          </div>
        )}
        <form onSubmit={submit}>
          <label htmlFor="auth-id">아이디</label>
          <input
            id="auth-id"
            autoComplete="username"
            maxLength={64}
            required
            value={userId}
            disabled={busy}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="아이디를 입력하세요"
          />
          <label htmlFor="auth-password">비밀번호</label>
          <input
            id="auth-password"
            type="password"
            autoComplete={signup ? "new-password" : "current-password"}
            minLength={8}
            maxLength={128}
            required
            value={password}
            disabled={busy}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="8자 이상 입력하세요"
          />
          {signup && (
            <>
              <label htmlFor="auth-confirmation">비밀번호 확인</label>
              <input
                id="auth-confirmation"
                type="password"
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
                value={confirmation}
                disabled={busy}
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="비밀번호를 한 번 더 입력하세요"
              />
            </>
          )}
          <button className="primary full auth-submit" disabled={busy}>
            {busy ? "처리 중…" : signup ? "회원가입" : "로그인"}
          </button>
        </form>
        <p className="auth-note">
          {signup
            ? "가입 후 로그인하면 옷을 등록할 수 있어요."
            : "기존에 등록한 아이디와 비밀번호도 사용할 수 있어요."}
        </p>
      </section>
    </div>
  );
}
export default function AuthApp() {
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "light",
  );
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [connectionError, setConnectionError] = useState("");
  const [sessionMessage, setSessionMessage] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#191a18" : "#f8f7f3");
    try {
      localStorage.setItem("mwoipji-theme", theme);
    } catch {
      /* Storage may be disabled. */
    }
  }, [theme]);
  useEffect(() => {
    const controller = new AbortController();
    api
      .get("/auth/me", { signal: controller.signal })
      .then(({ data }) => {
        if (!controller.signal.aborted) {
          setUser(data);
          setConnectionError("");
        }
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        if (error.response?.status !== 401)
          setConnectionError(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    const id = api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (
          error.response?.status === 401 &&
          !["/auth/login", "/auth/me"].includes(error.config?.url)
        ) {
          setUser(null);
          setSessionMessage(
            "로그인 시간이 만료되었습니다. 다시 로그인해 주세요.",
          );
        }
        return Promise.reject(error);
      },
    );
    return () => api.interceptors.response.eject(id);
  }, []);
  const themeControl = (
    <ThemeToggle
      theme={theme}
      onToggle={() =>
        setTheme((value) => (value === "dark" ? "light" : "dark"))
      }
    />
  );
  if (checking || connectionError)
    return (
      <div className="auth-page">
        <header className="auth-header">
          <span className="brand">뭐입지</span>
          {themeControl}
        </header>
        <div className="connection-state" role="status">
          <h1>
            {checking ? "옷장을 준비하고 있어요" : "서버에 연결하지 못했어요"}
          </h1>
          <p>
            {checking ? "로그인 상태를 확인하고 있습니다." : connectionError}
          </p>
          {!checking && (
            <button
              className="primary"
              onClick={() => {
                setChecking(true);
                setConnectionError("");
                setRetry((value) => value + 1);
              }}
            >
              다시 시도
            </button>
          )}
        </div>
      </div>
    );
  if (user)
    return (
      <WardrobeApp
        key={user.user_id}
        userId={user.user_id}
        themeControl={themeControl}
        onLogout={() => {
          setUser(null);
          setSessionMessage("");
        }}
      />
    );
  return (
    <div className="auth-page">
      <header className="auth-header">
        <span className="brand">뭐입지</span>
        {themeControl}
      </header>
      <AuthForm
        sessionMessage={sessionMessage}
        onLogin={(data) => {
          setSessionMessage("");
          setUser(data);
        }}
      />
      <footer className="auth-footer">매일의 선택을 조금 더 가볍게.</footer>
    </div>
  );
}
