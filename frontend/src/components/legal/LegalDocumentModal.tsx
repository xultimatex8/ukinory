import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { X } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import type { LegalDocument, LegalDocumentType } from "../../services/legal";


const TITLES: Record<LegalDocumentType, string> = {
  TERMS: "Terms and Conditions",
  PRIVACY: "Privacy Policy",
};

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h3 className="mt-6 text-base font-semibold text-text">{children}</h3>
  ),
  h2: ({ children }) => (
    <h3 className="mt-6 text-base font-semibold text-text">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="mt-4 text-sm font-semibold text-text">{children}</h4>
  ),
  p: ({ children }) => <p className="mt-3">{children}</p>,
  ul: ({ children }) => (
    <ul className="mt-3 list-disc space-y-1 pl-5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mt-3 list-decimal space-y-1 pl-5">{children}</ol>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-text">{children}</strong>
  ),
  hr: () => <hr className="my-5 border-border" />,
  a: ({ href, children }) => {
    const isWebLink = href?.startsWith("http");

    return (
      <a
        href={href}
        {...(isWebLink
          ? { target: "_blank", rel: "noopener noreferrer" }
          : {})}
        className="font-medium text-primary underline underline-offset-2
                   transition hover:text-primary-hover"
      >
        {children}
      </a>
    );
  },
};

interface LegalDocumentModalProps {
  documents: LegalDocument[];
  initialType: LegalDocumentType;
  onClose: () => void;
}

export default function LegalDocumentModal({
  documents,
  initialType,
  onClose,
}: LegalDocumentModalProps) {
  const [selectedType, setSelectedType] = useState(initialType);

  const selected =
    documents.find((document) => document.type === selectedType) ??
    documents[0];

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!selected) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-5 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="legal-document-title"
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.2 }}
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-[85vh] w-full max-w-2xl flex-col border border-border bg-surface p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              id="legal-document-title"
              className="text-xl font-semibold text-text"
            >
              {TITLES[selected.type]}
            </h2>

            <p className="mt-1 text-sm text-text-muted">
              Version {selected.version} · Effective{" "}
              {new Date(selected.effective_at).toLocaleDateString()}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 shrink-0 cursor-pointer items-center
                       justify-center border border-border text-text-muted
                       transition hover:border-primary hover:text-primary"
          >
            <X size={18} />
          </button>
        </div>

        {documents.length > 1 && (
          <div className="mt-5 flex gap-2" role="tablist">
            {documents.map((document) => (
              <button
                key={document.id}
                type="button"
                role="tab"
                aria-selected={document.type === selected.type}
                onClick={() => setSelectedType(document.type)}
                className={`cursor-pointer border px-3 py-2 text-sm font-medium transition ${
                  document.type === selected.type
                    ? "border-primary text-primary"
                    : "border-border text-text-muted hover:text-text"
                }`}
              >
                {TITLES[document.type]}
              </button>
            ))}
          </div>
        )}

        <div
          className="mt-5 min-h-0 flex-1 overflow-y-auto border border-border
                     bg-background p-4 text-sm leading-relaxed text-text
                     [&>*:first-child]:mt-0"
        >
          <ReactMarkdown components={markdownComponents}>
            {selected.content}
          </ReactMarkdown>
        </div>

        <div className="mt-5">
          <button
            type="button"
            onClick={onClose}
            className="w-full cursor-pointer border border-border px-4 py-3
                       text-sm font-medium text-text transition
                       hover:bg-surface-hover"
          >
            Close
          </button>
        </div>
      </motion.div>
    </div>,
    document.body,
  );
}