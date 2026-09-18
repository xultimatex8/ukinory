import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";

import { getCurrentUser } from "../services/user";

export default function GuestOnlyRoute() {
  const [isLoading, setIsLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    const checkGuest = async () => {
      const accessToken = localStorage.getItem("access_token");

      if (!accessToken) {
        setIsLoading(false);
        return;
      }

      try {
        const user = await getCurrentUser();
        setIsGuest(user.is_guest);
      } catch {
        setIsGuest(false);
      } finally {
        setIsLoading(false);
      }
    };

    void checkGuest();
  }, []);

  if (isLoading) {
    return null;
  }

  if (!isGuest) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}