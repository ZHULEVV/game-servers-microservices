class DomainError(Exception):
    """Доменная ошибка: HTTP-статус, машиночитаемый код и описание (формат {code, message} из ПР6)."""

    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message or code


def not_found(what: str) -> DomainError:
    return DomainError(404, "not_found", f"{what} не найден")


def forbidden(message: str) -> DomainError:
    return DomainError(403, "forbidden", message)


def unavailable(service: str, detail: str = "") -> DomainError:
    return DomainError(503, "dependency_unavailable", f"{service} недоступен" + (f": {detail}" if detail else ""))
