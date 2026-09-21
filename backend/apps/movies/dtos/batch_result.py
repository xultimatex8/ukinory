from dataclasses import dataclass
from typing import Optional


BATCH_DONE_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}


@dataclass(slots=True)
class BatchResult:
    state: str
    embeddings: Optional[list[Optional[list[float]]]] = None
    item_errors: Optional[list[Optional[str]]] = None
    error: Optional[str] = None

    @property
    def done(self) -> bool:
        return self.state in BATCH_DONE_STATES

    @property
    def succeeded(self) -> bool:
        return self.state == "JOB_STATE_SUCCEEDED"
