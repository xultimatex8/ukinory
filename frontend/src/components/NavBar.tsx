import { Compass, House, UserRound } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

const navigation = [
  {
    label: "Home",
    to: "/",
    icon: House,
  },
  {
    label: "Discover",
    to: "/discover",
    icon: Compass,
  },
  {
    label: "Profile",
    to: "/profile",
    icon: UserRound,
  },
];

export default function Navbar() {
  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-6">
        <Link
          to="/"
          className="text-2xl font-bold tracking-tight"
          aria-label="Ukinory home"
        >
          <span className="text-text">U</span>
          <span className="text-primary">kino</span>
          <span className="text-text">ry</span>
        </Link>

        <nav className="flex items-center gap-1">
          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? "bg-surface text-primary"
                      : "text-text-muted hover:bg-surface hover:text-text"
                  }`
                }
              >
                <Icon size={17} strokeWidth={1.8} />
                <span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
