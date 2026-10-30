class DomainError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message or self.code


class InvalidDates(DomainError):
    status, code = 400, "invalid_dates"


class NotFound(DomainError):
    status, code = 404, "not_found"


class Forbidden(DomainError):
    status, code = 403, "forbidden"


class SlotBusy(DomainError):
    status, code = 409, "slot_busy"


class InvalidStatus(DomainError):
    status, code = 409, "invalid_status"


class ServerUnavailable(DomainError):
    status, code = 409, "server_unavailable"


class DependencyUnavailable(DomainError):
    status, code = 503, "dependency_unavailable"
