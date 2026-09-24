import { Navigate, Outlet } from "react-router-dom";

export default function PublicOnlyRoute() {
  const accessToken = localStorage.getItem("access_token");

  if (accessToken) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
