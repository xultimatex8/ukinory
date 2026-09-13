interface AppHeaderProps {
  title: string;
  description: string;
}

export default function AppHeader({
  title,
  description,
}: AppHeaderProps) {
  return (
    <div className="text-center">
      <div className="mb-4 flex items-center justify-center gap-3">
        <span className="h-px w-16 bg-border" />

        <span className="flex gap-0.5">
          <span className="h-2 w-1 bg-primary" />
          <span className="h-2 w-1 bg-primary" />
          <span className="h-2 w-1 bg-primary" />
        </span>

        <span className="h-px w-16 bg-border" />
      </div>

      <div className="mb-4 inline-flex flex-col items-center">
        <h1 className="text-6xl font-bold tracking-tight">
          <span className="text-text">U</span>

          <span className="relative text-primary">
            kino

            <span className="absolute bottom-0 left-0 flex w-full items-center justify-center gap-1.5">
              <span className="h-1 w-3 bg-primary" />
              <span className="h-1 flex-1 bg-primary" />
              <span className="h-1 w-3 bg-primary" />
            </span>
          </span>

          <span className="text-text">ry</span>
        </h1>
      </div>

      <p className="mt-5 text-2xl font-medium text-text-secondary">
        {title}
      </p>

      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-text-muted">
        {description}
      </p>
    </div>
  );
}