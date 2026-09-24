interface AppLogoProps {
  size?: "sm" | "lg";
}

export default function AppLogo({ size = "lg" }: AppLogoProps) {
  const sizeClass = size === "sm" ? "text-2xl" : "text-6xl";
  const lineClass = size === "sm" ? "h-0.5" : "h-1";
  const sideClass = size === "sm" ? "w-1.5" : "w-3";
  const gapClass = size === "sm" ? "gap-0.5" : "gap-1.5";

  return (
    <div className="inline-flex flex-col items-center">
      <h1 className={`${sizeClass} font-bold tracking-tight`}>
        <span className="text-text">U</span>

        <span className="relative text-primary">
          kino

          <span
            className={`absolute bottom-0 left-0 flex w-full items-center justify-center ${gapClass}`}
          >
            <span className={`${lineClass} ${sideClass} bg-primary`} />
            <span className={`${lineClass} flex-1 bg-primary`} />
            <span className={`${lineClass} ${sideClass} bg-primary`} />
          </span>
        </span>

        <span className="text-text">ry</span>
      </h1>
    </div>
  );
}