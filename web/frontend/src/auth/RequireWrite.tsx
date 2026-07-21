import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

/** 写操作路由门禁：viewer 重定向回运营首页（后端另有 403）。 */
export default function RequireWrite() {
  const { user } = useAuth();
  if (user?.role === "viewer") {
    return <Navigate to="/ops" replace />;
  }
  return <Outlet />;
}
