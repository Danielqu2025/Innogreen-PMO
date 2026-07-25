import { Navigate, Outlet } from "react-router-dom";
import { Spin } from "antd";
import { useEffect } from "react";
import { useAuth } from "./AuthContext";

export default function RequireAuth() {
  const { user, loading, ssoEnabled, portalLoginUrl } = useAuth();

  useEffect(() => {
    if (loading || user) return;
    if (ssoEnabled && portalLoginUrl) {
      window.location.replace(portalLoginUrl);
    }
  }, [loading, user, ssoEnabled, portalLoginUrl]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
        <Spin />
      </div>
    );
  }
  if (!user) {
    if (ssoEnabled && portalLoginUrl) {
      return (
        <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
          <Spin tip="正在前往统一登录…" />
        </div>
      );
    }
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
