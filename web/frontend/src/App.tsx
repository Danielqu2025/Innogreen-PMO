import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { lazy, Suspense } from "react";
import RequireAuth from "./auth/RequireAuth";
import AppLayout from "./layout/AppLayout";
import LoginPage from "./pages/LoginPage";

// 动态导入页面组件，减少初始包体积
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ProjectListPage = lazy(() => import("./pages/ProjectListPage"));
const ProjectDetailPage = lazy(() => import("./pages/ProjectDetailPage"));
const StageListPage = lazy(() => import("./pages/StageListPage"));
const StageDetailPage = lazy(() => import("./pages/StageDetailPage"));
const PitfallListPage = lazy(() => import("./pages/PitfallListPage"));
const TenantPlaceholderPage = lazy(() => import("./pages/TenantPlaceholderPage"));

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1677ff",
          colorError: "#ff4d4f",
          colorWarning: "#faad14",
          colorSuccess: "#52c41a",
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/tenant/*" element={<TenantPlaceholderPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/ops" element={<AppLayout />}>
              <Route
                index
                element={
                  <Suspense fallback={<div>加载中...</div>}>
                    <DashboardPage />
                  </Suspense>
                }
              />
              <Route
                path="projects"
                element={
                  <Suspense fallback={<div>加载中...</div>}>
                    <ProjectListPage />
                  </Suspense>
                }
              />
              <Route
                path="projects/:id"
                element={
                  <Suspense fallback={<div>加载中...</div>}>
                    <ProjectDetailPage />
                  </Suspense>
                }
              />
              <Route
                path="stages"
                element={
                  <Suspense fallback={<div>加载中...</div>}>
                    <StageListPage />
                  </Suspense>
                }
              />
              <Route
                path="stages/:id"
                element={
                  <Suspense fallback={<div>加载中...</div>}>
                    <StageDetailPage />
                  </Suspense>
                }
              />
              <Route
                path="pitfalls"
                element={
                  <Suspense fallback={<div>加载中...</div>}>
                    <PitfallListPage />
                  </Suspense>
                }
              />
            </Route>
          </Route>
          <Route path="/" element={<Navigate to="/ops" replace />} />
          <Route path="*" element={<Navigate to="/ops" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
