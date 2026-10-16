import { Loader2 } from "lucide-react";

interface WaitingProps {
  title: string;
  text: string;
}

export default function Waiting({ title, text }: WaitingProps) {
  return (
    <div className="flex flex-col items-center border border-border bg-surface px-6 py-12 text-center">
      <Loader2 size={26} className="animate-spin text-primary" />
      <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-text-muted">
        {text}
      </p>
    </div>
  );
}