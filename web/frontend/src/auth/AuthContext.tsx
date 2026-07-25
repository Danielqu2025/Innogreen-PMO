import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  fetchSsoStatus,
  getMe,
  login as apiLogin,
  loginRedirectUrl,
  logout as apiLogout,
  type User,
} from "../api/client";

type AuthState = {
  user: User | null;
  loading: boolean;
  /** admin / operator 可写；viewer 只读 */
  canWrite: boolean;
  ssoEnabled: boolean;
  portalLoginUrl: string | null;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [ssoEnabled, setSsoEnabled] = useState(false);
  const [portalLoginUrl, setPortalLoginUrl] = useState<string | null>(null);

  // 先探 SSO，再探会话（未登录时 SSO 跳 Portal）
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const sso = await fetchSsoStatus();
      if (cancelled) return;
      setSsoEnabled(sso.enabled);
      setPortalLoginUrl(sso.portal_login_url);
      try {
        const me = await getMe();
        if (!cancelled) setUser(me);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (username: string, password: string) => {
    const u = await apiLogin(username, password);
    setUser(u);
    return u;
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
    window.location.href = loginRedirectUrl();
  };

  const canWrite = user?.role === "admin" || user?.role === "operator";

  return (
    <AuthContext.Provider
      value={{ user, loading, canWrite, ssoEnabled, portalLoginUrl, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth 必须在 AuthProvider 内使用");
  }
  return ctx;
}
