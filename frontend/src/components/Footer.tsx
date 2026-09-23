import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faGithub,
  faLinkedin,
} from "@fortawesome/free-brands-svg-icons";
import { UserRound, GitBranch } from "lucide-react";
import { Link } from "react-router-dom";
import AppLogo from "./AppLogo";

export default function Footer() {
  return (
    <footer className="mt-10 border-t border-border bg-background">
      <div className="mx-auto w-full max-w-5xl px-6 py-10">
        <div className="grid gap-8 sm:grid-cols-3">
          <div className="flex flex-col items-center gap-3 text-center sm:items-start sm:text-left">
            <Link
              to="/"
              aria-label="Ukinory home"
              className="w-fit"
            >
              <AppLogo size="sm" />
            </Link>

            <p className="max-w-xs text-xs text-text-muted">
              Discover your next favorite movie.
            </p>
          </div>

          <div className="flex flex-col items-center gap-3 text-center sm:items-start sm:text-left">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
              Links
            </h2>

            <Link
              to="/legal?type=terms"
              className="w-fit text-xs text-text-muted transition hover:text-text"
            >
              Terms & Conditions
            </Link>

            <Link
              to="/legal?type=privacy"
              className="w-fit text-xs text-text-muted transition hover:text-text"
            >
              Privacy Policy
            </Link>

            <div className="mt-1 flex items-center justify-center gap-4 text-text-muted">
              <a
                href="https://github.com/xultimatex8"
                target="_blank"
                rel="noreferrer"
                aria-label="GitHub profile"
                title="GitHub profile"
                className="transition hover:text-text"
              >
                <FontAwesomeIcon
                  icon={faGithub}
                  className="h-5.5 w-5.5"
                />
              </a>

              <a
                href="https://github.com/xultimatex8/ukinory"
                target="_blank"
                rel="noreferrer"
                aria-label="Ukinory repository"
                title="Ukinory repository"
                className="transition hover:text-text"
              >
                <GitBranch
                  size={18}
                  strokeWidth={1.8}
                />
              </a>

              <a
                href="https://alejandro-gonzalez.vercel.app/en"
                target="_blank"
                rel="noreferrer"
                aria-label="Portfolio"
                title="Portfolio"
                className="transition hover:text-text"
              >
                <UserRound
                  size={18}
                  strokeWidth={1.8}
                />
              </a>

              <a
                href="https://www.linkedin.com/in/alejandro-gonzalez-macias-agm/"
                target="_blank"
                rel="noreferrer"
                aria-label="LinkedIn"
                title="LinkedIn"
                className="transition hover:text-text"
              >
                <FontAwesomeIcon
                  icon={faLinkedin}
                  className="h-5.5 w-5.5"
                />
              </a>
            </div>
          </div>

          <div className="flex flex-col items-center gap-3 text-center sm:items-start sm:text-left">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
              Data & Credits
            </h2>

            <p className="max-w-xs text-xs text-text-muted sm:max-w-none">
              Movie data displayed in Ukinory is sourced from TMDB, while
              additional metadata stored in the application is sourced from
              Wikidata.
            </p>

            <Link
              to="/instructions"
              className="w-fit max-w-xs text-xs text-primary underline-offset-4 transition hover:text-text sm:max-w-none"
            >
              Letterboxd exports can be imported into Ukinory.
            </Link>
          </div>
        </div>

        <div className="mt-8 border-t border-border pt-6">
          <div className="flex flex-col items-center gap-3 text-center sm:flex-row sm:items-start sm:gap-4 sm:text-left">
            <a
              href="https://www.themoviedb.org/"
              target="_blank"
              rel="noreferrer"
              aria-label="The Movie Database"
              className="shrink-0 pt-0.5 transition-opacity hover:opacity-80"
            >
              <img
                src="/logos/tmdb.svg"
                alt="The Movie Database"
                className="h-3.5 w-auto"
              />
            </a>

            <p className="max-w-3xl text-xs leading-relaxed text-text-muted">
              This website uses TMDB and the TMDB APIs but is not endorsed,
              certified, or otherwise approved by TMDB.
            </p>
          </div>

          <p className="mt-4 text-center text-xs leading-relaxed text-text-muted sm:text-left">
            Letterboxd is a trademark of Letterboxd Limited. Ukinory is not
            affiliated with or endorsed by Letterboxd.
          </p>
        </div>

        <div className="mt-6 flex flex-col items-center gap-2 border-t border-border pt-4 text-center sm:flex-row sm:items-center sm:justify-between sm:text-left">
          <p className="text-xs text-text-muted">
            © {new Date().getFullYear()} Ukinory. All rights reserved.
          </p>

          <p className="text-xs text-text-muted">
            Built with React, Django & PostgreSQL.
          </p>
        </div>
      </div>
    </footer>
  );
}