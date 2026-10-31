from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import DomainError
from app.models.server import ServerStatus
from tests.conftest import ARK, CS, MC, MC_LITE, NOW, OTHER_PROVIDER, PROVIDER, make_server


def names(items):
    return {s.name for s in items}


def test_filter_by_game_is_case_insensitive(service):
    """Фильтр по игре не зависит от регистра."""
    items, total = service.list_servers(game="Minecraft")
    assert total == 2 and names(items) == {"Minecraft 8 GB", "Minecraft Lite"}


def test_filter_by_region_and_max_price(service):
    """Фильтры region и max_price работают вместе."""
    items, total = service.list_servers(region="eu", max_price=200)
    assert total == 1 and names(items) == {"Minecraft 8 GB"}


def test_filter_by_min_slots(service):
    """Фильтр min_slots оставляет только серверы с достаточным числом слотов."""
    items, total = service.list_servers(min_slots=20)
    assert names(items) == {"Minecraft 8 GB", "ARK Survival"}


def test_pagination_sorted_by_price(service):
    """Список отсортирован по цене; offset/count вырезают страницу, total остаётся полным."""
    items, total = service.list_servers(offset=1, count=2)
    assert total == 4 and [s.name for s in items] == ["Minecraft 8 GB", "CS2 Competitive"]


def test_removed_servers_are_hidden(service, repo):
    """Снятые с каталога серверы не попадают в список."""
    server = repo.get_by_id(ARK)
    server.status = ServerStatus.REMOVED
    repo.update(server)
    items, total = service.list_servers()
    assert total == 3 and "ARK Survival" not in names(items)


def test_availability_returns_price(service):
    """Доступность: активный сервер доступен, возвращается цена за час."""
    available, price = service.availability(MC, NOW, NOW + timedelta(hours=3))
    assert available is True and price == 150


def test_availability_rejects_inverted_period(service):
    """Период, где окончание не позже начала → 400 invalid_dates."""
    with pytest.raises(DomainError) as exc:
        service.availability(MC, NOW, NOW - timedelta(hours=1))
    assert exc.value.status == 400 and exc.value.code == "invalid_dates"


def test_unknown_server_is_404(service):
    """Неизвестный сервер → 404."""
    with pytest.raises(DomainError) as exc:
        service.get_server(uuid4())
    assert exc.value.status == 404


@pytest.mark.parametrize("slots,price", [(0, 100), (10, 0), (-5, 100)])
def test_add_server_validates_numbers(service, slots, price):
    """slots и price_per_hour должны быть больше нуля (400 invalid_params)."""
    with pytest.raises(DomainError) as exc:
        service.add_server(PROVIDER, "X", "cs2", "eu", slots, price)
    assert exc.value.code == "invalid_params"


def test_add_server_normalizes_names(service):
    """Игра и регион сохраняются в нижнем регистре, статус active."""
    server = service.add_server(PROVIDER, " Rust PvP ", "RUST", "EU", 50, 300)
    assert server.name == "Rust PvP" and server.game == "rust" and server.region == "eu" and server.status == ServerStatus.ACTIVE


def test_change_price_publishes_old_and_new(service, publisher):
    """Изменение цены владельцем сохраняется и публикует catalog.price_changed со старой и новой ценой."""
    server = service.change_price(MC, 170.0, PROVIDER, privileged=False)
    key, event = publisher.sent[-1]
    assert server.price_per_hour == 170 and key == "catalog.price_changed"
    assert float(event["old_price"]) == 150 and float(event["new_price"]) == 170


def test_change_price_by_other_provider_is_forbidden(service, publisher):
    """Чужой провайдер не может менять цену (403); администратор – может."""
    with pytest.raises(DomainError) as exc:
        service.change_price(MC, 100, OTHER_PROVIDER, privileged=False)
    assert exc.value.status == 403 and publisher.sent == []
    assert service.change_price(MC, 100, OTHER_PROVIDER, privileged=True).price_per_hour == 100


def test_change_price_must_be_positive(service):
    """Нулевая или отрицательная цена → 400 invalid_price."""
    with pytest.raises(DomainError) as exc:
        service.change_price(MC, 0, PROVIDER, privileged=False)
    assert exc.value.code == "invalid_price"


def test_review_published_recalculates_average_rating(service):
    """review.published: средний рейтинг пересчитывается по накопленным оценкам (5 и 4 → 4.5)."""
    for rating in (5, 4):
        service.handle_review_published({"event_id": str(uuid4()), "server_id": str(MC), "rating": rating})
    server = service.get_server(MC)
    assert server.rating == 4.5 and server.rating_count == 2


def test_duplicate_review_event_is_ignored(service):
    """Повторная доставка review.published с тем же event_id не меняет рейтинг."""
    event = {"event_id": str(uuid4()), "server_id": str(CS), "rating": 3}
    service.handle_review_published(event)
    service.handle_review_published(event)
    assert service.get_server(CS).rating_count == 1


def test_server_model_requires_fields():
    """Модель Server не создаётся без обязательных полей."""
    with pytest.raises(ValidationError):
        make_server(MC_LITE, "X", "cs2", "eu", "много", 100)
