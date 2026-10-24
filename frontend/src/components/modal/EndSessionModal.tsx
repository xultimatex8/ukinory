import ConfirmModal from "./ConfirmModal";

interface EndSessionModalProps {
  isEndingSession: boolean;
  error: string | null;
  onClose: () => void;
  onGoHome: () => void;
  onDownloadCsv: () => void;
}

export default function EndSessionModal({
  isEndingSession,
  error,
  onClose,
  onGoHome,
  onDownloadCsv,
}: EndSessionModalProps) {
  return (
    <ConfirmModal
      title="Leave session?"
      description={
        <>
          You can return home or leave the session and download your watchlist as
          a CSV file.
        </>
      }
      error={error}
      onClose={onClose}
      isProcessing={isEndingSession}
      actions={[
        {
          label: "Back to home",
          onClick: onGoHome,
          variant: "secondary",
        },
        {
          label: "Download CSV",
          loadingLabel: "Ending session...",
          onClick: onDownloadCsv,
          loading: isEndingSession,
        },
      ]}
    />
  );
}