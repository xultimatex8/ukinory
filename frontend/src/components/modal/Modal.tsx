import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { MouseEvent, ReactNode } from "react";

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
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    dialog.showModal();

    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  const handleBackdropClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <dialog
      ref={dialogRef}
      onClick={handleBackdropClick}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      aria-labelledby="modal-title"
      className="fixed inset-0 m-0 flex h-full w-full max-h-none max-w-none items-center justify-center border-0 bg-black/70 px-4 py-6 text-inherit backdrop:bg-transparent"
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full overflow-y-auto border border-border bg-surface ${SIZES[size]}`}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 id="modal-title" className={titleClassName}>
            {title}
          </h2>

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
      </section>
    </dialog>
  );
}