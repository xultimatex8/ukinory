import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import AuthScreen from "./screens/auth";
import RegisterScreen from "./screens/register";
import LoginScreen from "./screens/login";
import ProtectedRoute from "./components/ProtectedRoute";
import PublicOnlyRoute from "./components/PublicOnlyRoute";
import HomeScreen from "./screens/home";
import DiscoverScreen from "./screens/discover";
import DiscoverSessionScreen from "./screens/discover/session";
import NotFoundScreen from "./screens/not-found";
import ServerErrorScreen from "./screens/server-error";
import ProfileScreen from "./screens/profile";
import GuestOnlyRoute from "./components/GuestOnlyRoute";
import Navbar from "./components/NavBar";
import EditProfileScreen from "./screens/profile/edit";
import Footer from "./components/Footer";
import LegalScreen from "./screens/legal";
import InstructionsScreen from "./screens/instructions";

function PublicLayout() {
  return (
    <>
      <Outlet />
      <Footer />
    </>
  );
}

function LegalLayout() {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");

  const isAuthenticated = accessToken && refreshToken;

  return (
    <>
      {isAuthenticated && <Navbar />}
      <Outlet />
      <Footer />
    </>
  );
}

function AppLayout() {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");

  if (!accessToken || !refreshToken) {
    return <Navigate to="/auth" replace />;
  }

  return (
    <>
      <Navbar />
      <Outlet />
      <Footer />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route element={<PublicOnlyRoute />}>
            <Route path="/auth" element={<AuthScreen />} />
            <Route path="/login" element={<LoginScreen />} />
            <Route path="/register" element={<RegisterScreen />} />
          </Route>
        </Route>

        <Route element={<LegalLayout />}>
          <Route path="/legal" element={<LegalScreen />} />
        </Route>

        <Route element={<AppLayout />}>
          <Route element={<GuestOnlyRoute />}>
            <Route path="/register/claim" element={<RegisterScreen />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<HomeScreen />} />
            <Route path="/discover" element={<DiscoverScreen />} />
            <Route path="/discover/:id" element={<DiscoverSessionScreen />} />
            <Route path="/profile" element={<ProfileScreen />} />
            <Route path="/profile/edit" element={<EditProfileScreen />} />
            <Route path="/instructions" element={<InstructionsScreen />} />
          </Route>

          <Route path="/500" element={<ServerErrorScreen />} />
          <Route path="*" element={<NotFoundScreen />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;