import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  type User,
} from "../api/client";

type AuthState = {
  user: User | null;
  loading: boolean;
  /** admin / operator 可写；viewer 只读 */
  canWrite: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // 挂载时探测会话：/me 200 → 已登录；401 → null（未登录）
  useEffect(() => {
    getMe()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const u = await apiLogin(username, password);
    setUser(u);
    return u;
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
  };

  const canWrite = user?.role === "admin" || user?.role === "operator";

  return (
    <AuthContext.Provider value={{ user, loading, canWrite, login, logout }}>
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
