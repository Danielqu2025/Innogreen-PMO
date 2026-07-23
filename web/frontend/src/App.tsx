import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { lazy, Suspense } from "react";
import { AuthProvider } from "./auth/AuthContext";
import RequireAuth from "./auth/RequireAuth";
import RequireWrite from "./auth/RequireWrite";
import AppLayout from "./layout/AppLayout";
import LoginPage from "./pages/LoginPage";

// 动态导入页面组件，减少初始包体积
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ProjectListPage = lazy(() => import("./pages/ProjectListPage"));
const ProjectFormPage = lazy(() => import("./pages/ProjectFormPage"));
const ProjectDetailPage = lazy(() => import("./pages/ProjectDetailPage"));
const TaskUpdatePage = lazy(() => import("./pages/TaskUpdatePage"));
const StageListPage = lazy(() => import("./pages/StageListPage"));
const StageDetailPage = lazy(() => import("./pages/StageDetailPage"));
const PitfallListPage = lazy(() => import("./pages/PitfallListPage"));
const PitfallFormPage = lazy(() => import("./pages/PitfallFormPage"));
const PitfallDetailPage = lazy(() => import("./pages/PitfallDetailPage"));
const UserManagementPage = lazy(() => import("./pages/UserManagementPage"));
const TaskCatalogPage = lazy(() => import("./pages/TaskCatalogPage"));
const DataExportPage = lazy(() => import("./pages/DataExportPage"));
const DataImportPage = lazy(() => import("./pages/DataImportPage"));
const TenantPlaceholderPage = lazy(() => import("./pages/TenantPlaceholderPage"));

const Fallback = <div>加载中...</div>;

const withSuspense = (node: React.ReactNode) => (
  <Suspense fallback={Fallback}>{node}</Suspense>
);

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
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/tenant/*" element={<TenantPlaceholderPage />} />
            <Route element={<RequireAuth />}>
              <Route path="/ops" element={<AppLayout />}>
                <Route index element={withSuspense(<DashboardPage />)} />
                <Route path="projects" element={withSuspense(<ProjectListPage />)} />
                <Route element={<RequireWrite />}>
                  <Route
                    path="projects/new"
                    element={withSuspense(<ProjectFormPage />)}
                  />
                  <Route
                    path="projects/:id/edit"
                    element={withSuspense(<ProjectFormPage />)}
                  />
                  <Route
                    path="projects/:id/tasks/:taskId"
                    element={withSuspense(<TaskUpdatePage />)}
                  />
                  <Route
                    path="pitfalls/new"
                    element={withSuspense(<PitfallFormPage />)}
                  />
                </Route>
                <Route
                  path="projects/:id"
                  element={withSuspense(<ProjectDetailPage />)}
                />
                <Route path="stages" element={withSuspense(<StageListPage />)} />
                <Route
                  path="stages/:id"
                  element={withSuspense(<StageDetailPage />)}
                />
                <Route
                  path="pitfalls/:id"
                  element={withSuspense(<PitfallDetailPage />)}
                />
                <Route path="pitfalls" element={withSuspense(<PitfallListPage />)} />
                <Route
                  path="users"
                  element={withSuspense(<UserManagementPage />)}
                />
                <Route
                  path="tasks"
                  element={withSuspense(<TaskCatalogPage />)}
                />
                <Route
                  path="settings/export"
                  element={withSuspense(<DataExportPage />)}
                />
                <Route
                  path="settings/import"
                  element={withSuspense(<DataImportPage />)}
                />
              </Route>
            </Route>
            <Route path="/" element={<Navigate to="/ops" replace />} />
            <Route path="*" element={<Navigate to="/ops" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}
