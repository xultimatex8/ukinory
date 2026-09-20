import { useState } from "react";

import LegalDocumentModal from "./LegalDocumentModal";
import type { LegalDocument, LegalDocumentType } from "../../services/legal";

const linkClass =
  "cursor-pointer font-medium text-primary transition " +
  "hover:text-primary-hover disabled:cursor-not-allowed disabled:opacity-50";

interface LegalLinksProps {
  documents: LegalDocument[] | null;
}

export default function LegalLinks({ documents }: LegalLinksProps) {
  const [openType, setOpenType] = useState<LegalDocumentType | null>(null);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpenType("TERMS")}
        disabled={!documents}
        className={linkClass}
      >
        Terms and Conditions
      </button>{" "}
      and the{" "}
      <button
        type="button"
        onClick={() => setOpenType("PRIVACY")}
        disabled={!documents}
        className={linkClass}
      >
        Privacy Policy
      </button>

      {documents && openType && (
        <LegalDocumentModal
          documents={documents}
          initialType={openType}
          onClose={() => setOpenType(null)}
        />
      )}
    </>
  );
}