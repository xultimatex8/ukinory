class QuotaExceeded(Exception):
    def __init__(self, client: str, period: str, limit: int) -> None:
        self.client = client
        self.period = period
        self.limit = limit
        super().__init__(
            f"Quota for '{client}' exceeded: limit of {limit} per {period}."
        )
