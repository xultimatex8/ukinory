import { CircleHelp, Compass, House, UserRound } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import AppLogo from "./AppLogo";

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
        <Link to="/" aria-label="Ukinory home">
          <AppLogo size="sm" />
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

          <div className="mx-2 h-5 w-px bg-border" />

          <NavLink
            to="/instructions"
            className={({ isActive }) =>
              `flex items-center gap-2 border px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-primary/20 text-primary hover:border-primary/40 hover:bg-primary/5"
              }`
            }
          >
            <CircleHelp size={17} strokeWidth={1.8} />
            <span className="hidden sm:inline">Import / Export</span>
          </NavLink>
        </nav>
      </div>
    </header>
  );
}