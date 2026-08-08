class SafetyViolationError(Exception):
    """Raised when a safety constraint blocks an operation (e.g. assigning a
    Load to a vehicle that is status 'Grounded')."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message