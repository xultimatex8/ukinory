import { X } from "lucide-react";
import type { ReactNode } from "react";

const SIZES = {
  md: "max-h-[85vh] max-w-lg",
  lg: "max-h-[90vh] max-w-2xl",
};

interface ModalProps {
  title: string;
  onClose: () => void;
  size?: keyof typeof SIZES;
  titleClassName?: string;
  children: ReactNode;
}

export default function Modal({
  title,
  onClose,
  size = "lg",
  titleClassName = "text-sm font-semibold uppercase tracking-wider text-text-muted",
  children,
}: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6"
      onClick={onClose}
    >
      <div
        className={`w-full overflow-y-auto border border-border bg-surface ${SIZES[size]}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className={titleClassName}>{title}</h2>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="cursor-pointer p-1 text-text-muted transition hover:text-text"
          >
            <X size={19} />
          </button>
        </div>

        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}