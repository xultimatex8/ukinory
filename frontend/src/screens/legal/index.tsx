import { useEffect, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import {
  getCurrentLegalDocuments,
  type LegalDocument,
  type LegalDocumentType,
} from "../../services/legal";

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

export default function LegalScreen() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const requestedType = searchParams.get("type");

  const selectedType: LegalDocumentType =
    requestedType === "privacy" ? "PRIVACY" : "TERMS";

  useEffect(() => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }, [selectedType]);

  useEffect(() => {
    let cancelled = false;

    const loadDocuments = async () => {
      try {
        setLoading(true);
        setError(false);

        const result = await getCurrentLegalDocuments();

        await new Promise((resolve) => setTimeout(resolve, 350));

        if (!cancelled) {
          setDocuments(result);
        }
      } catch {
        if (!cancelled) {
          setError(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadDocuments();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSelect = (type: LegalDocumentType) => {
    setSearchParams({
      type: type === "TERMS" ? "terms" : "privacy",
    });
  };

  const selected = documents.find(
    (document) => document.type === selectedType,
  );

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto w-full max-w-4xl px-6 py-10 sm:py-14">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-8 flex cursor-pointer items-center gap-2 text-sm
                     font-medium text-text-muted transition hover:text-text"
        >
          <ArrowLeft size={17} strokeWidth={1.8} />
          <span>Back</span>
        </button>

        <div className="text-center">
          <h1 className="text-2xl font-semibold text-text">
            Legal
          </h1>

          <p className="mt-2 text-sm text-text-muted">
            Terms and conditions and privacy policy.
          </p>
        </div>

        {documents.length > 1 && (
          <div
            className="mt-8 flex justify-center gap-2"
            role="tablist"
            aria-label="Legal documents"
          >
            {documents.map((document) => (
              <button
                key={document.id}
                type="button"
                role="tab"
                aria-selected={document.type === selectedType}
                onClick={() => handleSelect(document.type)}
                className={`cursor-pointer border px-4 py-2 text-sm
                            font-medium transition ${
                              document.type === selectedType
                                ? "border-primary text-primary"
                                : "border-border text-text-muted hover:text-text"
                            }`}
              >
                {TITLES[document.type]}
              </button>
            ))}
          </div>
        )}

        <section className="mt-8 border border-border bg-surface">
          {loading && (
            <div className="p-6 text-sm text-text-muted">
              Loading...
            </div>
          )}

          {error && !loading && (
            <div className="p-6 text-sm text-text-muted">
              Unable to load the legal documents.
            </div>
          )}

          {!loading && !error && documents.length === 0 && (
            <div className="p-6 text-sm text-text-muted">
              No legal documents are currently available.
            </div>
          )}

          {selected && !loading && !error && (
            <>
              <div className="border-b border-border px-6 py-5">
                <h2 className="text-xl font-semibold text-text">
                  {TITLES[selected.type]}
                </h2>

                <p className="mt-1 text-sm text-text-muted">
                  Version {selected.version} · Effective{" "}
                  {new Date(selected.effective_at).toLocaleDateString()}
                </p>
              </div>

              <article
                className="px-6 py-6 text-sm leading-relaxed text-text
                           [&>*:first-child]:mt-0"
              >
                <ReactMarkdown components={markdownComponents}>
                  {selected.content}
                </ReactMarkdown>
              </article>
            </>
          )}
        </section>
      </div>
    </main>
  );
}