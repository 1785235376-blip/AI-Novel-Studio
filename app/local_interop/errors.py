class InteropFailure(Exception):
    """Safe machine-readable error; never retain upstream bodies or source text."""
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)
