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
    # Reprezentacja zamówienia rozszerzona o stan podprocesu Produkcja.
    order_id: int
    customer_name: str
    total_value: float
    status: str = "new"
    # Etap podprocesu produkcji (None = produkcja nierozpoczęta)
    production_stage: str | None = None
    # Flaga: czy surowce zostały zamówione (boundary event)
    materials_ordered: bool = False
    # Flaga: czy wystąpiło wstrzymanie produkcji
    production_halted: bool = False
    # Szacowana data dostawy (ustawiana po oszacowaniu)
    estimated_delivery: str | None = None
