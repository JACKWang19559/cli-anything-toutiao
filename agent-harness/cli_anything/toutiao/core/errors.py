class ToutiaoError(Exception):
    """An actionable, safe-to-display CLI failure."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
