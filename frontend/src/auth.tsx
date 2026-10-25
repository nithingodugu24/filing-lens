import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, post } from "./api";
type User = { id: string; full_name: string; email: string; role: string };
type Session = { access_token: string; user: User };
const AuthContext = createContext<{ user: User | null; logout: () => void }>({
  user: null,
  logout: () => {},
});
export const useAuth = () => useContext(AuthContext);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState<boolean | null>(null),
    [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  function logout() {
    localStorage.removeItem("filinglens-token");
    setUser(null);
  }
  useEffect(() => {
    if (!user) return;
    let expires = Date.now() + 30 * 60 * 1000;
    try {
      const token = localStorage.getItem("filinglens-token");
      if (token)
        expires =
          JSON.parse(
            atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
          ).exp * 1000;
    } catch {}
    const timer = setTimeout(
      () => {
        post<Session>("/auth/refresh", {})
          .then((session) => {
            localStorage.setItem("filinglens-token", session.access_token);
            setUser(session.user);
          })
          .catch(logout);
      },
      Math.max(5000, expires - Date.now() - 60000),
    );
    return () => clearTimeout(timer);
  }, [user]);
  useEffect(() => {
    api<{ enabled: boolean }>("/auth/config")
      .then(async (config) => {
        setEnabled(config.enabled);
        if (config.enabled && localStorage.getItem("filinglens-token")) {
          try {
            setUser(await api<User>("/auth/me"));
          } catch {
            logout();
          }
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    window.addEventListener("filinglens-signout", logout);
    return () => window.removeEventListener("filinglens-signout", logout);
  }, []);
  if (loading)
    return (
      <div className="splash" role="status">
        <strong>FilingLens</strong>
        <p>Connecting to database…</p>
      </div>
    );
  if (error)
    return (
      <div className="splash" role="alert">
        <h1>Could not connect</h1>
        <p>{error}</p>
        <button
          className="button secondary"
          onClick={() => window.location.reload()}
        >
          Try again
        </button>
      </div>
    );
  return (
    <AuthContext.Provider value={{ user, logout }}>
      {enabled && !user ? (
        <Login
          onLogin={(session) => {
            localStorage.setItem("filinglens-token", session.access_token);
            setUser(session.user);
          }}
        />
      ) : (
        <div key={user?.id ?? "local-demo"}>{children}</div>
      )}
    </AuthContext.Provider>
  );
}
function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [register, setRegister] = useState(false),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [name, setName] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <main className="auth-page">
      <div className="auth-card">
        <span className="eyebrow">FILINGLENS</span>
        <h1>{register ? "Create your account" : "Welcome back"}</h1>
        <p>Understand company reports and keep your analysis together.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              onLogin(
                await post<Session>(
                  register ? "/auth/register" : "/auth/login",
                  { email, password, ...(register ? { full_name: name } : {}) },
                ),
              );
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {register && (
            <label>
              Your name
              <input
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={120}
                required
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={10}
              maxLength={72}
              required
            />
          </label>
          {register && <small>Use at least 10 characters.</small>}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary" disabled={busy}>
            {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
          </button>
        </form>
        <button
          className="text-button"
          onClick={() => {
            setRegister(!register);
            setError("");
          }}
        >
          {register
            ? "Already have an account? Sign in"
            : "New here? Create an account"}
        </button>
      </div>
    </main>
  );
}
