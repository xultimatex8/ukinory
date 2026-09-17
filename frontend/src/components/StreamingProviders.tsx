import type { MovieRecommendation } from "../services/swipeSessions";

export interface StreamingProvider {
  id: number;
  name: string;
  logoUrl: string;
}

export interface StreamingCountry {
  code: string;
  name: string;
  providers: StreamingProvider[];
}

const COUNTRY_NAMES: Record<string, string> = {
  ES: "Spain",
  US: "United States",
  GB: "United Kingdom",
  FR: "France",
  DE: "Germany",
  IT: "Italy",
  CA: "Canada",
  AU: "Australia",
  MX: "Mexico",
  BR: "Brazil",
  AR: "Argentina",
  JP: "Japan",
  KR: "South Korea",
  IN: "India",
};

export function getStreamingCountries(
  movie: MovieRecommendation | null,
): StreamingCountry[] {
  if (!movie?.streaming_providers) {
    return [];
  }

  const countries: StreamingCountry[] = [];

  for (const [countryCode, countryData] of Object.entries(
    movie.streaming_providers,
  )) {
    if (!countryData || typeof countryData !== "object") {
      continue;
    }

    const data = countryData as {
      flatrate?: {
        provider_id?: number;
        provider_name?: string;
        logo_path?: string;
      }[];
      free?: {
        provider_id?: number;
        provider_name?: string;
        logo_path?: string;
      }[];
      ads?: {
        provider_id?: number;
        provider_name?: string;
        logo_path?: string;
      }[];
    };

    const allProviders = [
      ...(data.flatrate ?? []),
      ...(data.free ?? []),
      ...(data.ads ?? []),
    ];

    const uniqueProviders = new Map<number, StreamingProvider>();

    for (const provider of allProviders) {
      if (
        provider.provider_id !== undefined &&
        provider.provider_name &&
        provider.logo_path &&
        !uniqueProviders.has(provider.provider_id)
      ) {
        uniqueProviders.set(provider.provider_id, {
          id: provider.provider_id,
          name: provider.provider_name,
          logoUrl: `https://image.tmdb.org/t/p/w92${provider.logo_path}`,
        });
      }
    }

    if (uniqueProviders.size > 0) {
      countries.push({
        code: countryCode,
        name: COUNTRY_NAMES[countryCode] ?? countryCode,
        providers: Array.from(uniqueProviders.values()),
      });
    }
  }

  return countries.sort((a, b) => {
    if (a.code === "ES") return -1;
    if (b.code === "ES") return 1;

    return a.name.localeCompare(b.name);
  });
}
