import { useLegalDocuments } from "../../hooks/useLegalDocuments";
import LegalLinks from "./LegalLinks";

export default function LegalNotice() {
  const { documents } = useLegalDocuments();

  if (!documents) return null;

  return (
    <p className="text-center text-xs leading-relaxed text-text-muted">
      You can review our <LegalLinks documents={documents} /> at any time.
    </p>
  );
}