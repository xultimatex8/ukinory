import { useEffect } from "react";
import { ArrowLeft, ExternalLink, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";

import AppHeader from "../../components/LogoHeader";
import LegalNotice from "../../components/legal/LegalNotice";

const exportSteps = [
  {
    number: "01",
    title: "Open Letterboxd",
    description: "Sign in to your Letterboxd account.",
  },
  {
    number: "02",
    title: "Open your profile",
    description: 'Open the user menu and select "Profile".',
  },
  {
    number: "03",
    title: "Edit your profile",
    description: 'From your profile, select "Edit Profile".',
  },
  {
    number: "04",
    title: "Open Data",
    description: 'Select the "Data" section.',
  },
  {
    number: "05",
    title: "Export your data",
    description: 'Select "Export Your Data", then click "Export Data".',
  },
];

const watchlistSteps = [
  {
    number: "01",
    title: "Export Ukinory watchlist",
    description: "Export your watchlist from a session or your profile.",
  },
  {
    number: "02",
    title: "Open Letterboxd",
    description: "Sign in to your Letterboxd account.",
  },
  {
    number: "03",
    title: "Open your watchlist",
    description: 'Open the user menu and select "Watchlist".',
  },
  {
    number: "04",
    title: "Import your watchlist",
    description: 'Select "Import to Watchlist".',
  },
  {
    number: "05",
    title: "Select your CSV",
    description: "Select the CSV file exported from Ukinory.",
  },
];

export default function InstructionsScreen() {
  const navigate = useNavigate();

  useEffect(() => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }, []);

  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto min-h-screen w-full max-w-5xl px-6 pt-8 pb-10">
        <section>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="mb-8 flex cursor-pointer items-center gap-2 text-sm
                       font-medium text-text-muted transition hover:text-text"
          >
            <ArrowLeft size={17} strokeWidth={1.8} />
            <span>Back</span>
          </button>

          <AppHeader
            title="Letterboxd export integration"
            description="Import your Letterboxd data into Ukinory or export your Ukinory watchlist to Letterboxd."
          />

          <div className="mt-6 border border-border/60 bg-surface/50 px-5 py-4">
            <p className="text-sm leading-relaxed text-text-muted">
              Ukinory is not affiliated with, endorsed by, or officially
              connected to Letterboxd. Letterboxd is a separate service, and
              these instructions only explain how to use its data export and
              watchlist import features.
            </p>
          </div>

          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className="border border-border bg-surface">
              <div className="border-b border-border p-7">
                <h2 className="text-xl font-semibold text-text">
                  Download Letterboxd export
                </h2>

                <p className="mt-2 text-sm leading-relaxed text-text-muted">
                  Export your Letterboxd data to import your info into
                  Ukinory.
                </p>
              </div>

              <div>
                {exportSteps.map((step, index) => (
                  <div
                    key={step.number}
                    className={`flex gap-5 p-6 ${
                      index !== exportSteps.length - 1
                        ? "border-b border-border"
                        : ""
                    }`}
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-border text-sm font-medium text-primary">
                      {step.number}
                    </div>

                    <div>
                      <h3 className="font-semibold text-text">
                        {step.title}
                      </h3>

                      <p className="mt-1.5 text-sm leading-relaxed text-text-muted">
                        {step.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t border-border p-6">
                <p className="text-sm leading-relaxed text-text-muted">
                  Letterboxd will download a ZIP file containing your
                  data.
                </p>

                <a
                  href="https://letterboxd.com/settings/data/"
                  target="_blank"
                  rel="noreferrer"
                  className="group mt-5 flex w-fit items-center gap-2 border border-border bg-surface-hover px-5 py-3
                             text-sm font-medium text-text transition hover:border-primary hover:text-primary"
                >
                  Open Letterboxd
                  <ExternalLink size={16} strokeWidth={1.7} />
                </a>
              </div>
            </div>

            <div className="border border-border bg-surface">
              <div className="border-b border-border p-7">
                <h2 className="text-xl font-semibold text-text">
                  Export watchlist to Letterboxd
                </h2>

                <p className="mt-2 text-sm leading-relaxed text-text-muted">
                  Export your Ukinory watchlist and import it into Letterboxd.
                </p>
              </div>

              <div>
                {watchlistSteps.map((step, index) => (
                  <div
                    key={step.number}
                    className={`flex gap-5 p-6 ${
                      index !== watchlistSteps.length - 1
                        ? "border-b border-border"
                        : ""
                    }`}
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-border text-sm font-medium text-primary">
                      {step.number}
                    </div>

                    <div>
                      <h3 className="font-semibold text-text">
                        {step.title}
                      </h3>

                      <p className="mt-1.5 text-sm leading-relaxed text-text-muted">
                        {step.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t border-border p-6">
                <div className="flex items-start gap-3">
                  <Upload
                    size={21}
                    strokeWidth={1.6}
                    className="mt-0.5 shrink-0 text-primary"
                  />

                  <p className="text-sm leading-relaxed text-text-muted">
                    First, export your watchlist from Ukinory as a CSV file,
                    either after finishing swiping recommendations or from your
                    profile. Then{" "}
                    <a
                      href="https://letterboxd.com/"
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      open Letterboxd
                    </a>{" "}
                    and upload that file using Letterboxd's{" "}
                    <span className="text-text">Import to Watchlist</span>{" "}
                    option. Letterboxd only adds entries that are not already 
                    in your watchlist. Your existing watchlist is not overwritten.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-10">
            <LegalNotice />
          </div>
        </section>
      </div>
    </main>
  );
}