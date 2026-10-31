from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import DomainError
from app.models.monitor import Alert, Monitor


def test_deploy_completed_starts_monitor_with_default_thresholds(service, monitor):
    """deploy.completed запускает монитор: статус active, пороги по умолчанию 90 %."""
    booking_id, user_id = monitor
    state = service.get_monitor(booking_id)
    assert state.status == "active" and state.user_id == user_id
    assert state.thresholds.cpu == 90 and state.thresholds.ram == 90


def test_duplicate_deploy_event_is_ignored(service):
    """Повторная доставка deploy.completed (тот же event_id) не пересоздаёт монитор и не сбрасывает его состояние."""
    booking_id, user_id = uuid4(), uuid4()
    event = {"event_id": str(uuid4()), "booking_id": str(booking_id), "user_id": str(user_id)}
    service.handle_deploy_completed(event)
    service.add_sample(booking_id, 10, 10)
    service.handle_deploy_completed(event)
    assert service.get_monitor(booking_id).cpu == 10


def test_sample_below_threshold_creates_no_alert(service, publisher, monitor):
    """Метрики ниже порога: оповещений и событий нет, значения запоминаются."""
    booking_id, _ = monitor
    assert service.add_sample(booking_id, 50, 60) == []
    assert publisher.sent == [] and service.get_monitor(booking_id).cpu == 50


def test_sample_above_threshold_creates_alert_and_event(service, publisher, monitor):
    """cpu=95 при пороге 90: создано оповещение и отправлено monitoring.load_exceeded."""
    booking_id, user_id = monitor
    alerts = service.add_sample(booking_id, 95, 40)
    key, event = publisher.sent[-1]
    assert len(alerts) == 1 and alerts[0].metric == "cpu" and alerts[0].threshold == 90
    assert key == "monitoring.load_exceeded" and event["user_id"] == str(user_id) and event["value"] == 95


def test_both_metrics_over_threshold_give_two_alerts(service, publisher, monitor):
    """Превышение и cpu, и ram даёт два оповещения и два события."""
    booking_id, _ = monitor
    assert len(service.add_sample(booking_id, 99, 99)) == 2 and len(publisher.sent) == 2


def test_alerts_are_listed_newest_first_with_pagination(service, monitor):
    """Журнал оповещений: новые первыми, offset/count и total."""
    booking_id, _ = monitor
    for value in (91, 92, 93):
        service.add_sample(booking_id, value, 10)
    items, total = service.alerts(booking_id, offset=0, count=2)
    assert total == 3 and [a.value for a in items] == [93, 92]


def test_set_thresholds_checks_booking_and_applies(service, booking, monitor):
    """Смена порогов: Booking Service вызван, пороги применены и влияют на новые метрики."""
    booking_id, _ = monitor
    service.set_thresholds(booking_id, 80, 70)
    assert booking.calls == [booking_id]
    assert len(service.add_sample(booking_id, 85, 10)) == 1


@pytest.mark.parametrize("cpu,ram", [(0, 50), (101, 50), (50, 0), (50, 150)])
def test_thresholds_must_be_in_range(service, monitor, cpu, ram):
    """Пороги вне диапазона 1–100 → 400 invalid_threshold."""
    with pytest.raises(DomainError) as exc:
        service.set_thresholds(monitor[0], cpu, ram)
    assert exc.value.status == 400 and exc.value.code == "invalid_threshold"


def test_thresholds_not_changed_for_closed_booking(service, booking, monitor):
    """Бронь завершена или отменена → 409 booking_closed."""
    booking.status = "finished"
    with pytest.raises(DomainError) as exc:
        service.set_thresholds(monitor[0], 80, 80)
    assert exc.value.status == 409 and exc.value.code == "booking_closed"


def test_booking_service_down_gives_503_and_thresholds_unchanged(service, booking, monitor):
    """Booking Service недоступен → 503; пороги остаются прежними."""
    booking.down = True
    with pytest.raises(DomainError) as exc:
        service.set_thresholds(monitor[0], 50, 50)
    assert exc.value.status == 503 and service.get_monitor(monitor[0]).thresholds.cpu == 90


def test_booking_finished_stops_monitor(service, monitor):
    """booking.finished останавливает монитор; новые метрики отвергаются (409 monitor_stopped)."""
    booking_id, user_id = monitor
    service.handle_booking_finished({"event_id": str(uuid4()), "booking_id": str(booking_id), "user_id": str(user_id)})
    assert service.get_monitor(booking_id).status == "stopped"
    with pytest.raises(DomainError) as exc:
        service.add_sample(booking_id, 99, 99)
    assert exc.value.status == 409 and exc.value.code == "monitor_stopped"


def test_unknown_monitor_is_404(service):
    """Монитор неизвестной брони → 404."""
    with pytest.raises(DomainError) as exc:
        service.get_monitor(uuid4())
    assert exc.value.status == 404


def test_models_validate_fields():
    """Модели Monitor и Alert не создаются без обязательных полей."""
    with pytest.raises(ValidationError):
        Monitor(booking_id=uuid4())
    with pytest.raises(ValidationError):
        Alert(metric="cpu")
