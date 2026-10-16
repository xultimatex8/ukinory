import { useState } from "react";

import type { StreamingCountry } from "./StreamingProviders";

type Variant = "compact" | "regular";

const STYLES: Record<
  Variant,
  {
    section: string;
    headerGap: string;
    select: string;
    grid: string;
    tile: string;
    logo: string;
    empty: string;
    attribution: string;
  }
> = {
  compact: {
    section: "mt-6 border-t border-border pt-5",
    headerGap: "gap-3",
    select: "max-w-24 px-2 py-1 text-[10px]",
    grid: "grid-cols-3",
    tile: "p-2",
    logo: "h-8 w-8",
    empty: "mt-2",
    attribution: "Streaming availability powered by JustWatch.",
  },
  regular: {
    section: "mt-7 border-t border-border pt-5",
    headerGap: "gap-4",
    select: "px-2.5 py-1.5 text-xs",
    grid: "grid-cols-4",
    tile: "px-2 py-2.5",
    logo: "h-10 w-10",
    empty: "mt-3",
    attribution: "Streaming availability data provided by JustWatch.",
  },
};

interface WhereToWatchProps {
  countries: StreamingCountry[];
  variant?: Variant;
}

export default function WhereToWatch({
  countries,
  variant = "regular",
}: WhereToWatchProps) {
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);

  const styles = STYLES[variant];

  const defaultCountry =
    countries.find((country) => country.code === "ES") ?? countries[0];

  const selected =
    countries.find((country) => country.code === selectedCountry) ??
    defaultCountry;

  return (
    <section className={styles.section}>
      <div className={`flex items-center justify-between ${styles.headerGap}`}>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          Where to watch
        </h4>

        {countries.length > 0 && (
          <select
            value={selected?.code ?? ""}
            onChange={(event) => setSelectedCountry(event.target.value)}
            className={`cursor-pointer border border-border bg-background text-text-secondary outline-none focus:border-primary ${styles.select}`}
            aria-label="Select country"
          >
            {countries.map((country) => (
              <option key={country.code} value={country.code}>
                {country.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {selected ? (
        <div className={`mt-3 grid gap-2 ${styles.grid}`}>
          {selected.providers.map((provider) => (
            <div
              key={provider.id}
              className={`flex min-w-0 flex-col items-center border border-border bg-background ${styles.tile}`}
              title={provider.name}
            >
              <img
                src={provider.logoUrl}
                alt={provider.name}
                className={`${styles.logo} rounded object-cover`}
              />

              <span className="mt-1.5 line-clamp-2 w-full text-center text-[10px] leading-tight text-text-muted">
                {provider.name}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className={`${styles.empty} text-sm text-text-muted`}>
          No streaming information available.
        </p>
      )}

      <p className="mt-3 text-[10px] leading-relaxed text-text-muted">
        {styles.attribution}
      </p>
    </section>
  );
}