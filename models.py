from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Message:
    # Uniwersalny komunikat wymieniany między klientem i serwerem.
    # event opisuje typ zdarzenia, a payload przenosi dane potrzebne
    # do obsługi konkretnego kroku procesu biznesowego.
    sender: str
    receiver: str
    event: str
    payload: dict[str, Any] = field(default_factory=dict)
    # Znacznik czasu pomaga śledzić kolejność zdarzeń w logach GUI.
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass(slots=True)
class Order:
    # Minimalna reprezentacja zamówienia na potrzeby sprintu 1.
    # W kolejnych sprintach ten model można rozszerzyć np. o termin,
    # listę produktów, status płatności albo etap produkcji.
    order_id: int
    customer_name: str
    total_value: float
    status: str = "new"
