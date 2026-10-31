from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import DomainError
from app.models.deployment import Deployment, DeploymentStatus
from tests.conftest import confirmed_event


def test_start_creates_provisioning_deployment_and_unfinished_operation(service, booking):
    """Запуск для подтверждённой брони: Booking вызван, развёртывание provisioning, операция не завершена."""
    booking_id = uuid4()
    dep, op = service.start_for_booking(booking_id)
    assert booking.calls == [booking_id] and dep.status == DeploymentStatus.PROVISIONING
    assert dep.user_id == booking.user_id and op.is_finished is False and op.result is None


@pytest.mark.parametrize("status", ["created", "awaiting_payment", "active", "finished", "cancelled"])
def test_start_requires_confirmed_booking(service, booking, status):
    """Развёртывание возможно только для брони в статусе confirmed (409 booking_not_confirmed)."""
    booking.status = status
    with pytest.raises(DomainError) as exc:
        service.start_for_booking(uuid4())
    assert exc.value.status == 409 and exc.value.code == "booking_not_confirmed"


def test_second_start_for_same_booking_is_conflict(service):
    """Повторный запуск для той же брони → 409 already_started."""
    booking_id = uuid4()
    service.start_for_booking(booking_id)
    with pytest.raises(DomainError) as exc:
        service.start_for_booking(booking_id)
    assert exc.value.status == 409 and exc.value.code == "already_started"


def test_start_for_unknown_booking_is_404(service, booking):
    """Booking Service не знает бронь → 404 booking_not_found."""
    booking.missing = True
    with pytest.raises(DomainError) as exc:
        service.start_for_booking(uuid4())
    assert exc.value.status == 404 and exc.value.code == "booking_not_found"


def test_booking_service_down_gives_503(service, booking, repo):
    """Booking Service недоступен → 503; развёртывание не создаётся."""
    booking.down = True
    with pytest.raises(DomainError) as exc:
        service.start_for_booking(uuid4())
    assert exc.value.status == 503 and repo.active_for_booking(uuid4()) is None


def test_complete_marks_running_closes_operation_and_publishes(service, publisher):
    """Завершение развёртывания: running, выдан адрес и порт, операция закрыта, отправлено deploy.completed."""
    dep, op = service.start_for_booking(uuid4())
    service.complete(dep.id)
    assert dep.status == DeploymentStatus.RUNNING and dep.ip.startswith("10.0.0.") and dep.port in (25565, 27015, 7777)
    assert op.is_finished is True and op.result["ip"] == dep.ip and op.result["status"] == "running"
    key, event = publisher.sent[-1]
    assert key == "deploy.completed" and event["booking_id"] == str(dep.booking_id) and event["port"] == dep.port


def test_complete_after_cancellation_does_nothing(service, publisher):
    """Если бронь отменили во время развёртывания, завершение не запускает сервер и не публикует событие."""
    dep, _ = service.start_for_booking(uuid4())
    service.handle_booking_released({"event_id": str(uuid4()), "booking_id": str(dep.booking_id)})
    service.complete(dep.id)
    assert dep.status == DeploymentStatus.STOPPED and publisher.sent == []


def test_stop_running_deployment(service):
    """Остановка запущенного сервера → статус stopped, проставлено время завершения."""
    dep, _ = service.start_for_booking(uuid4())
    service.complete(dep.id)
    stopped = service.stop(dep.id)
    assert stopped.status == DeploymentStatus.STOPPED and stopped.finished_at is not None


def test_stop_requires_running_status(service):
    """Остановить можно только запущенный сервер: provisioning и stopped → 409 invalid_status."""
    dep, _ = service.start_for_booking(uuid4())
    with pytest.raises(DomainError) as exc:
        service.stop(dep.id)
    assert exc.value.status == 409 and exc.value.code == "invalid_status"
    service.complete(dep.id)
    service.stop(dep.id)
    with pytest.raises(DomainError):
        service.stop(dep.id)


def test_booking_confirmed_event_creates_deployment_once(service, repo):
    """booking.confirmed создаёт развёртывание; повторная доставка того же события игнорируется."""
    event = confirmed_event()
    dep = service.handle_booking_confirmed(event)
    assert dep is not None and dep.status == DeploymentStatus.PROVISIONING
    assert service.handle_booking_confirmed(event) is None
    assert repo.active_for_booking(dep.booking_id) is dep


def test_booking_cancelled_or_finished_releases_server(service):
    """booking.cancelled / booking.finished освобождают сервер: активное развёртывание переходит в stopped."""
    dep = service.handle_booking_confirmed(confirmed_event())
    service.complete(dep.id)
    service.handle_booking_released({"event_id": str(uuid4()), "booking_id": str(dep.booking_id)})
    assert dep.status == DeploymentStatus.STOPPED


def test_unknown_deployment_and_operation(service):
    """Неизвестные развёртывание и операция → 404."""
    for call in (service.get_deployment, service.get_operation):
        with pytest.raises(DomainError) as exc:
            call(uuid4())
        assert exc.value.status == 404


def test_deployment_model_requires_fields():
    """Модель Deployment не создаётся без обязательных полей."""
    with pytest.raises(ValidationError):
        Deployment(id=uuid4())
