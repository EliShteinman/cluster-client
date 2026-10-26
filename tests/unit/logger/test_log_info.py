import asyncio
import logging

import pytest
from pydantic import BaseModel

from app.logger import log_info


class Order(BaseModel):
    id: int
    city: str


class Receipt(BaseModel):
    total: int


@log_info(inputs=("order.id", "order.city"), outputs=("total",))
def charge(*, order: Order, card: str) -> Receipt:
    return Receipt(total=order.id * 10)


@log_info(inputs=("order.id",))
async def ship(*, order: Order) -> None:
    raise LookupError(order.city)


@log_info(inputs=("priority",))
def queue(*, order: Order, priority: int = 3) -> int:
    return order.id + priority


ORDER: Order = Order(id=7, city="Haifa")


def records_of(*, caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == __name__]


@pytest.fixture(autouse=True)
def info_level(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(level=logging.INFO, logger=__name__)


def test_one_line_is_logged_per_call(caplog: pytest.LogCaptureFixture) -> None:
    charge(order=ORDER, card="4111")

    assert len(records_of(caplog=caplog)) == 1


def test_line_shows_the_chosen_inputs_and_outputs(caplog: pytest.LogCaptureFixture) -> None:
    charge(order=ORDER, card="4111")

    assert records_of(caplog=caplog)[0].getMessage().startswith("charge 7 Haifa -> 70 in ")


def test_unchosen_arguments_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    charge(order=ORDER, card="4111")

    assert "4111" not in records_of(caplog=caplog)[0].getMessage()


def test_chosen_values_are_kept_as_fields(caplog: pytest.LogCaptureFixture) -> None:
    charge(order=ORDER, card="4111")

    assert records_of(caplog=caplog)[0].outputs == {"total": 70}


def test_error_is_logged_and_raised_again(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(LookupError):
        asyncio.run(ship(order=ORDER))

    assert records_of(caplog=caplog)[0].getMessage().startswith("ship 7 -> LookupError in ")


def test_records_are_info(caplog: pytest.LogCaptureFixture) -> None:
    charge(order=ORDER, card="4111")

    assert records_of(caplog=caplog)[0].levelno == logging.INFO


def test_defaulted_input_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    queue(order=ORDER)

    assert records_of(caplog=caplog)[0].inputs == {"priority": 3}
