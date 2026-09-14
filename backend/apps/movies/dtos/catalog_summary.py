from dataclasses import dataclass


@dataclass(slots=True)
class CatalogSeedSummary:
    discovered: int = 0
    stored: int = 0
    without_metadata: int = 0
    pool_sizes: dict = None
    failed_pools: list = None

    def __post_init__(self) -> None:
        if self.pool_sizes is None:
            self.pool_sizes = {}
        if self.failed_pools is None:
            self.failed_pools = []
