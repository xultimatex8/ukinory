import { BrowserRouter, Route, Routes } from "react-router-dom";

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

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/auth" element={<AuthScreen />} />
          <Route path="/login" element={<LoginScreen />} />
          <Route path="/register" element={<RegisterScreen />} />
        </Route>

        <Route element={<GuestOnlyRoute />}>
          <Route path="/register/claim" element={<RegisterScreen />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/discover" element={<DiscoverScreen />} />
          <Route path="/discover/:id" element={<DiscoverSessionScreen />} />
          <Route path="/profile" element={<ProfileScreen />} />
        </Route>

        <Route path="/500" element={<ServerErrorScreen />} />
        <Route path="*" element={<NotFoundScreen />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;