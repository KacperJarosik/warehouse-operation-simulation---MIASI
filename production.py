"""
Moduł odpowiedzialny za logikę podprocesu Produkcja z diagramu BPMN.

Podproces Produkcja składa się z kroków (pełna implementacja):
1. Zaplanuj produkcję
2. Zarezerwuj surowce (boundary event: brak surowców → zamów brakujące)
3. Wyprodukuj towary (boundary event: wstrzymanie produkcji)

Elementy procesu głównego (poza podprocesem):
- check_stock() — sprawdzenie dostępności towaru na magazynie
- estimate_delivery_date() — oszacowanie daty dostawy
- check_delivery_deadline() — sprawdzenie czy dostawa zdąży przed terminem
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from models import Order


# ---------------------------------------------------------------------------
# Konfiguracja symulacji
# ---------------------------------------------------------------------------

# Prawdopodobieństwo, że towar jest dostępny na magazynie (POZA podprocesem)
STOCK_AVAILABILITY_CHANCE = 0.3
# Prawdopodobieństwo, że dostawa zdąży mimo opóźnienia (POZA podprocesem)
DELIVERY_ON_TIME_CHANCE = 0.5


# ---------------------------------------------------------------------------
# Wynik kroku produkcji
# ---------------------------------------------------------------------------

@dataclass
class ProductionStepResult:
    """Wynik pojedynczego kroku podprocesu Produkcja."""
    success: bool
    message: str
    data: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Magazyn surowców - stan wewnętrzny podprocesu
# ---------------------------------------------------------------------------

@dataclass
class MaterialsWarehouse:
    """
    Rejestr surowców dostępnych w magazynie.
    Podproces Produkcja operuje na tym stanie przy rezerwacji i zamawianiu.
    """
    # Słownik: nazwa_surowca -> ilość dostępna
    stock: dict[str, int] = field(default_factory=dict)
    # Słownik: nazwa_surowca -> ilość zarezerwowana (zablokowana)
    reserved: dict[str, int] = field(default_factory=dict)
    # Zamówienia w trakcie realizacji: nazwa_surowca -> ilość zamówiona
    pending_orders: dict[str, int] = field(default_factory=dict)


# Globalny stan magazynu surowców (współdzielony między zamówieniami)
materials_warehouse = MaterialsWarehouse(
    stock={
        "stal": 100,
        "drewno": 50,
        "elektronika": 20,
        "tworzywo_sztuczne": 200,
        "szklo": 30,
    }
)


# Definicja zapotrzebowania surowcowego na jednostkę produktu (BOM)
# Klucz: próg wartości zamówienia, wartość: wymagane surowce
def _get_required_materials(order: Order) -> dict[str, int]:
    """Wyznacza listę surowców potrzebnych do realizacji zamówienia (BOM)."""
    base_materials: dict[str, int] = {
        "stal": 5,
        "tworzywo_sztuczne": 10,
    }
    if order.total_value > 1000:
        base_materials["elektronika"] = 3
        base_materials["szklo"] = 2
    if order.total_value > 5000:
        base_materials["stal"] = 15
        base_materials["drewno"] = 8
    return base_materials


# ---------------------------------------------------------------------------
# Linia produkcyjna - stan wewnętrzny podprocesu
# ---------------------------------------------------------------------------

@dataclass
class ProductionLine:
    """Reprezentuje linię produkcyjną przetwarzającą zamówienie."""
    order_id: int
    plan_id: str
    status: str = "idle"  # idle, running, halted, completed
    progress_percent: int = 0
    halt_reason: str | None = None

    def start(self) -> None:
        self.status = "running"
        self.progress_percent = 0

    def advance(self, percent: int) -> None:
        self.progress_percent = min(100, self.progress_percent + percent)
        if self.progress_percent >= 100:
            self.status = "completed"

    def halt(self, reason: str) -> None:
        self.status = "halted"
        self.halt_reason = reason

    def resume(self) -> None:
        self.status = "running"
        self.halt_reason = None


# Aktywne linie produkcyjne
_active_lines: dict[int, ProductionLine] = {}

# Konfiguracja symulacji awarii produkcji (wewnątrz podprocesu)
PRODUCTION_HALT_CHANCE = 0.3


# ---------------------------------------------------------------------------
# Elementy procesu głównego (POZA podprocesem Produkcja)
# ---------------------------------------------------------------------------

def check_stock(order: Order) -> bool:
    """
    Sprawdzenie dostępności na magazynie (task z BPMN).
    Sprawdza czy GOTOWY towar jest dostępny w magazynie produktów.
    Jeśli tak - podproces Produkcja jest pomijany.
    """
    return random.random() < STOCK_AVAILABILITY_CHANCE


def check_delivery_deadline(order: Order) -> ProductionStepResult:
    """
    Sprawdź czy dostawa zdąży przed terminem klienta (task z BPMN).
    Wywoływane po boundary event 'Wstrzymanie produkcji' na podprocesie.
    Decyduje czy klient musi być poinformowany o opóźnieniu.
    """
    on_time = random.random() < DELIVERY_ON_TIME_CHANCE
    if on_time:
        return ProductionStepResult(
            success=True,
            message="Dostawa zdąży przed terminem klienta - kontynuacja produkcji.",
            data={"on_time": True},
        )
    else:
        return ProductionStepResult(
            success=False,
            message="Dostawa NIE zdąży przed terminem klienta - wymagana decyzja klienta.",
            data={"on_time": False},
        )


def estimate_delivery_date(order: Order) -> ProductionStepResult:
    """
    Oszacuj datę dostawy - data wyjazdu, data dostarczenia (task z BPMN).
    Wywoływane po zakończeniu podprocesu Produkcja lub gdy towar jest na magazynie.
    """
    days_to_ship = random.randint(1, 3)
    days_in_transit = random.randint(2, 5)
    ship_date = datetime.now() + timedelta(days=days_to_ship)
    delivery_date = ship_date + timedelta(days=days_in_transit)
    return ProductionStepResult(
        success=True,
        message=f"Szacowana data wyjazdu: {ship_date.strftime('%Y-%m-%d')}, "
                f"data dostarczenia: {delivery_date.strftime('%Y-%m-%d')}.",
        data={
            "ship_date": ship_date.strftime("%Y-%m-%d"),
            "delivery_date": delivery_date.strftime("%Y-%m-%d"),
        },
    )


# ---------------------------------------------------------------------------
# Silnik podprocesu Produkcja - PEŁNA IMPLEMENTACJA
# ---------------------------------------------------------------------------

class ProductionProcess:
    """
    Klasa zarządzająca przebiegiem podprocesu Produkcja dla jednego zamówienia.

    Podproces zawiera pełną logikę:
    - Planowanie produkcji (tworzenie planu, przypisanie linii)
    - Rezerwacja surowców (sprawdzenie BOM, blokowanie w magazynie)
    - Zamawianie brakujących surowców (aktualizacja magazynu)
    - Produkcja towarów (symulacja linii produkcyjnej z możliwością awarii)

    Etapy (production_stage w Order):
    - "check_stock"       : sprawdzanie magazynu (POZA podprocesem)
    - "planning"          : planowanie produkcji
    - "reserving"         : rezerwacja surowców
    - "ordering_materials": zamawianie brakujących surowców
    - "producing"         : produkcja towarów
    - "halted"            : wstrzymanie produkcji (boundary event)
    - "checking_deadline" : sprawdzanie czy zdąży przed terminem (POZA)
    - "waiting_client"    : oczekiwanie na decyzję klienta (POZA)
    - "estimating"        : oszacowanie daty dostawy (POZA)
    - "completed"         : podproces zakończony sukcesem
    - "cancelled"         : zamówienie anulowane przez klienta
    """

    def __init__(self, order: Order) -> None:
        self.order = order
        self.production_line: ProductionLine | None = None
        self.required_materials: dict[str, int] = {}
        self.plan_id: str | None = None

    def start(self) -> list[ProductionStepResult]:
        """Rozpoczyna przepływ: sprawdza magazyn i uruchamia podproces jeśli trzeba."""
        results: list[ProductionStepResult] = []

        # Krok POZA podprocesem: Sprawdzenie dostępności gotowego towaru
        self.order.production_stage = "check_stock"
        stock_available = check_stock(self.order)

        if stock_available:
            results.append(ProductionStepResult(
                success=True,
                message="Towar dostępny na magazynie - produkcja nie jest wymagana.",
                data={"stock_available": True},
            ))
            # Przeskakujemy do oszacowania daty dostawy (POZA podprocesem)
            self.order.production_stage = "estimating"
            estimate_result = estimate_delivery_date(self.order)
            results.append(estimate_result)
            if estimate_result.data:
                self.order.estimated_delivery = estimate_result.data.get("delivery_date")
            self.order.production_stage = "completed"
            self.order.status = "production_done"
        else:
            results.append(ProductionStepResult(
                success=True,
                message="Towar NIEDOSTĘPNY na magazynie - uruchamiam podproces Produkcja.",
                data={"stock_available": False},
            ))
            # === WEJŚCIE DO PODPROCESU PRODUKCJA ===
            production_results = self._subprocess_production()
            results.extend(production_results)

        return results

    # ===================================================================
    # PODPROCES PRODUKCJA - pełna implementacja
    # ===================================================================

    def _subprocess_production(self) -> list[ProductionStepResult]:
        """Cały podproces Produkcja: planowanie → rezerwacja → produkcja."""
        results: list[ProductionStepResult] = []

        # --- Krok 1: Zaplanuj produkcję ---
        planning_results = self._plan_production()
        results.extend(planning_results)

        if self.order.production_stage == "cancelled":
            return results

        # --- Krok 2: Zarezerwuj surowce ---
        reserve_results = self._reserve_materials()
        results.extend(reserve_results)

        if self.order.production_stage == "cancelled":
            return results

        # --- Krok 3: Wyprodukuj towary ---
        produce_results = self._produce_goods()
        results.extend(produce_results)

        return results

    def _plan_production(self) -> list[ProductionStepResult]:
        """
        Krok podprocesu: Zaplanuj produkcję.
        Tworzy plan produkcyjny na podstawie BOM i przypisuje linię produkcyjną.
        """
        results: list[ProductionStepResult] = []
        self.order.production_stage = "planning"
        self.order.status = "in_production"

        # Wyznacz wymagane surowce (Bill of Materials)
        self.required_materials = _get_required_materials(self.order)

        # Wygeneruj identyfikator planu
        self.plan_id = f"PLAN-{self.order.order_id}-{datetime.now().strftime('%H%M%S')}"

        # Utwórz i przypisz linię produkcyjną
        self.production_line = ProductionLine(
            order_id=self.order.order_id,
            plan_id=self.plan_id,
        )
        _active_lines[self.order.order_id] = self.production_line

        materials_summary = ", ".join(
            f"{name}: {qty}" for name, qty in self.required_materials.items()
        )
        results.append(ProductionStepResult(
            success=True,
            message=f"Zaplanowano produkcję [{self.plan_id}]. "
                    f"Wymagane surowce: {materials_summary}.",
            data={
                "plan_id": self.plan_id,
                "required_materials": self.required_materials,
            },
        ))
        return results

    def _reserve_materials(self) -> list[ProductionStepResult]:
        """
        Krok podprocesu: Zarezerwuj surowce.
        Sprawdza magazyn surowców, blokuje dostępne.
        Boundary event: jeśli brakuje surowców → zamów brakujące.
        """
        results: list[ProductionStepResult] = []
        self.order.production_stage = "reserving"

        warehouse = materials_warehouse
        missing: dict[str, int] = {}
        reserved_now: dict[str, int] = {}

        # Sprawdź dostępność każdego surowca
        for material, required_qty in self.required_materials.items():
            available = warehouse.stock.get(material, 0) - warehouse.reserved.get(material, 0)
            if available >= required_qty:
                reserved_now[material] = required_qty
            else:
                if available > 0:
                    reserved_now[material] = available
                    missing[material] = required_qty - available
                else:
                    missing[material] = required_qty

        # Zarezerwuj to co jest dostępne
        for material, qty in reserved_now.items():
            warehouse.reserved[material] = warehouse.reserved.get(material, 0) + qty

        if not missing:
            # Wszystkie surowce zarezerwowane pomyślnie
            reserved_summary = ", ".join(
                f"{name}: {qty}" for name, qty in reserved_now.items()
            )
            results.append(ProductionStepResult(
                success=True,
                message=f"Surowce zarezerwowane pomyślnie: {reserved_summary}.",
                data={"reserved": reserved_now, "missing": {}},
            ))
        else:
            # BOUNDARY EVENT: Brak wymaganych surowców
            missing_summary = ", ".join(
                f"{name}: {qty}" for name, qty in missing.items()
            )
            reserved_summary = ", ".join(
                f"{name}: {qty}" for name, qty in reserved_now.items()
            ) if reserved_now else "brak"
            results.append(ProductionStepResult(
                success=False,
                message=f"Brak wymaganych surowców! Brakuje: {missing_summary}. "
                        f"Zarezerwowano częściowo: {reserved_summary}.",
                data={"reserved": reserved_now, "missing": missing},
            ))

            # Zamów brakujące surowce
            order_results = self._order_missing_materials(missing)
            results.extend(order_results)

        return results

    def _order_missing_materials(self, missing: dict[str, int]) -> list[ProductionStepResult]:
        """
        Krok podprocesu: Zamów brakujące surowce.
        Składa zamówienie do dostawcy i aktualizuje stan magazynu po dostawie.
        """
        results: list[ProductionStepResult] = []
        self.order.production_stage = "ordering_materials"
        self.order.materials_ordered = True

        warehouse = materials_warehouse

        # Rejestruj zamówienie
        for material, qty in missing.items():
            warehouse.pending_orders[material] = (
                warehouse.pending_orders.get(material, 0) + qty
            )

        missing_summary = ", ".join(f"{name}: {qty}" for name, qty in missing.items())
        # Szacowany czas dostawy zależy od ilości materiałów
        total_missing = sum(missing.values())
        delivery_days = max(2, min(10, total_missing // 3))

        results.append(ProductionStepResult(
            success=True,
            message=f"Zamówiono brakujące surowce u dostawcy: {missing_summary}. "
                    f"Szacowany czas dostawy: {delivery_days} dni roboczych.",
            data={
                "ordered_materials": missing,
                "delivery_days": delivery_days,
            },
        ))

        # Symulacja dostawy: surowce trafiają do magazynu
        for material, qty in missing.items():
            warehouse.stock[material] = warehouse.stock.get(material, 0) + qty
            warehouse.pending_orders[material] = (
                warehouse.pending_orders.get(material, 0) - qty
            )

        results.append(ProductionStepResult(
            success=True,
            message="Surowce dostarczone przez dostawcę - przyjęto do magazynu.",
            data={"delivered": missing},
        ))

        # Ponowna rezerwacja brakujących surowców (teraz dostępne)
        self.order.production_stage = "reserving"
        for material, qty in missing.items():
            warehouse.reserved[material] = warehouse.reserved.get(material, 0) + qty

        reserved_summary = ", ".join(f"{name}: {qty}" for name, qty in missing.items())
        results.append(ProductionStepResult(
            success=True,
            message=f"Surowce zarezerwowane po dostawie: {reserved_summary}.",
            data={"reserved_after_delivery": missing},
        ))

        return results

    def _produce_goods(self) -> list[ProductionStepResult]:
        """
        Krok podprocesu: Wyprodukuj towary.
        Uruchamia linię produkcyjną, zużywa zarezerwowane surowce.
        Boundary event: możliwe wstrzymanie produkcji (awaria).
        """
        results: list[ProductionStepResult] = []
        self.order.production_stage = "producing"

        if self.production_line is None:
            results.append(ProductionStepResult(
                success=False,
                message="Błąd: brak przypisanej linii produkcyjnej.",
            ))
            return results

        # Uruchom linię produkcyjną
        self.production_line.start()
        results.append(ProductionStepResult(
            success=True,
            message=f"Linia produkcyjna uruchomiona [{self.plan_id}].",
            data={"line_status": "running"},
        ))

        # Symulacja postępu produkcji z możliwością awarii
        halt_occurred = random.random() < PRODUCTION_HALT_CHANCE

        if halt_occurred:
            # Produkcja przerwana w trakcie (boundary event)
            self.production_line.advance(40)
            halt_reason = random.choice([
                "awaria_maszyny",
                "brak_energii",
                "defekt_surowca",
                "przekroczenie_tolerancji",
            ])
            self.production_line.halt(halt_reason)

            # Zwolnij częściowo zużyte surowce (nie wszystkie zużyte)
            results.append(ProductionStepResult(
                success=False,
                message=f"WSTRZYMANIE PRODUKCJI! Przyczyna: {halt_reason}. "
                        f"Postęp: {self.production_line.progress_percent}%.",
                data={
                    "halted": True,
                    "reason": halt_reason,
                    "progress": self.production_line.progress_percent,
                },
            ))

            # Ustawiamy stan boundary event
            self.order.production_halted = True
            self.order.production_stage = "halted"
            self.order.status = "production_halted"

            # Sprawdzenie terminu (POZA podprocesem)
            deadline_results = self._handle_halt_boundary_event()
            results.extend(deadline_results)
        else:
            # Produkcja przebiega pomyślnie
            self.production_line.advance(100)

            # Zużyj zarezerwowane surowce z magazynu
            self._consume_reserved_materials()

            results.append(ProductionStepResult(
                success=True,
                message=f"Towary wyprodukowane pomyślnie. "
                        f"Postęp: {self.production_line.progress_percent}%. "
                        f"Surowce zużyte.",
                data={"produced": True, "progress": 100},
            ))

            # Zakończenie podprocesu → oszacowanie daty dostawy (POZA)
            self.order.production_stage = "estimating"
            estimate_result = estimate_delivery_date(self.order)
            results.append(estimate_result)
            if estimate_result.data:
                self.order.estimated_delivery = estimate_result.data.get("delivery_date")
            self.order.production_stage = "completed"
            self.order.status = "production_done"

            # Zwolnij linię
            _active_lines.pop(self.order.order_id, None)

        return results

    def _consume_reserved_materials(self) -> None:
        """Zużywa zarezerwowane surowce - usuwa je z magazynu."""
        warehouse = materials_warehouse
        for material, qty in self.required_materials.items():
            warehouse.stock[material] = max(0, warehouse.stock.get(material, 0) - qty)
            warehouse.reserved[material] = max(
                0, warehouse.reserved.get(material, 0) - qty
            )

    def _release_reserved_materials(self) -> None:
        """Zwalnia rezerwację surowców (przy anulowaniu)."""
        warehouse = materials_warehouse
        for material, qty in self.required_materials.items():
            warehouse.reserved[material] = max(
                0, warehouse.reserved.get(material, 0) - qty
            )

    # ===================================================================
    # POZA PODPROCESEM - obsługa boundary event i decyzji klienta
    # ===================================================================

    def _handle_halt_boundary_event(self) -> list[ProductionStepResult]:
        """
        Obsługa boundary event wstrzymania produkcji.
        Sprawdza czy dostawa zdąży (POZA podprocesem).
        """
        results: list[ProductionStepResult] = []
        self.order.production_stage = "checking_deadline"

        deadline_result = check_delivery_deadline(self.order)
        results.append(deadline_result)

        if deadline_result.success:
            # Dostawa zdąży → wznawiamy produkcję (powrót DO podprocesu)
            results.append(ProductionStepResult(
                success=True,
                message="Oczekiwanie na naprawę/dostawę, po czym wznowienie produkcji.",
            ))
            resume_results = self._resume_production()
            results.extend(resume_results)
        else:
            # Dostawa NIE zdąży → informujemy klienta (POZA podprocesem)
            self.order.production_stage = "waiting_client"
            self.order.status = "awaiting_client_decision"
            results.append(ProductionStepResult(
                success=False,
                message="Wymagana decyzja klienta: kontynuacja lub anulowanie zamówienia.",
                data={"needs_client_decision": True},
            ))

        return results

    def _resume_production(self) -> list[ProductionStepResult]:
        """Wznawia produkcję po wstrzymaniu (powrót do podprocesu)."""
        results: list[ProductionStepResult] = []

        self.order.production_halted = False
        self.order.production_stage = "producing"
        self.order.status = "in_production"

        if self.production_line is not None:
            self.production_line.resume()
            self.production_line.advance(60)  # dokańczamy pozostałe 60%

        results.append(ProductionStepResult(
            success=True,
            message=f"Produkcja wznowiona i zakończona pomyślnie. "
                    f"Postęp: 100%. Surowce zużyte.",
            data={"produced": True, "progress": 100},
        ))

        # Zużyj surowce
        self._consume_reserved_materials()

        # Zakończenie → oszacowanie daty (POZA podprocesem)
        self.order.production_stage = "estimating"
        estimate_result = estimate_delivery_date(self.order)
        results.append(estimate_result)
        if estimate_result.data:
            self.order.estimated_delivery = estimate_result.data.get("delivery_date")
        self.order.production_stage = "completed"
        self.order.status = "production_done"

        # Zwolnij linię
        _active_lines.pop(self.order.order_id, None)

        return results

    def handle_client_decision(self, continue_order: bool) -> list[ProductionStepResult]:
        """
        Obsługuje decyzję klienta po informacji o opóźnieniu (POZA podprocesem).
        Wywołać gdy klient odpowie na delay_notice.
        """
        results: list[ProductionStepResult] = []

        if not continue_order:
            # Klient anuluje zamówienie
            self.order.production_stage = "cancelled"
            self.order.status = "cancelled"

            # Zwolnij zarezerwowane surowce
            self._release_reserved_materials()

            # Zwolnij linię produkcyjną
            _active_lines.pop(self.order.order_id, None)
            self.production_line = None

            results.append(ProductionStepResult(
                success=True,
                message="Klient anulował zamówienie. Rezerwacje surowców zwolnione, "
                        "linia produkcyjna zwolniona.",
                data={"cancelled": True},
            ))
        else:
            # Klient kontynuuje → wznawiamy podproces produkcji
            results.append(ProductionStepResult(
                success=True,
                message="Klient zdecydował o kontynuacji - wznawianie podprocesu Produkcja.",
                data={"continue": True},
            ))
            resume_results = self._resume_production()
            results.extend(resume_results)

        return results
