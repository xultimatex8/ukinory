import { BrowserRouter, Route, Routes } from "react-router-dom";

import AuthScreen from "./screens/auth";
import RegisterScreen from "./screens/register";
import LoginScreen from "./screens/login";
import ProtectedRoute from "./components/ProtectedRoute";
import PublicOnlyRoute from "./components/PublicOnlyRoute";
import HomeScreen from "./screens/home";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/auth" element={<AuthScreen />} />
          <Route path="/login" element={<LoginScreen />} />
          <Route path="/register" element={<RegisterScreen />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<HomeScreen />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;