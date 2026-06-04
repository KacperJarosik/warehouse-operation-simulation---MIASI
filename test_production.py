"""Testy podprocesu Produkcja - weryfikacja wszystkich ścieżek BPMN."""

import production
from models import Order
from production import ProductionProcess, materials_warehouse


def print_results(results):
    for r in results:
        prefix = "OK" if r.success else "FAIL"
        print(f"  [{prefix}] {r.message}")


def reset_warehouse():
    """Resetuje magazyn surowców do stanu początkowego."""
    materials_warehouse.stock = {
        "stal": 100,
        "drewno": 50,
        "elektronika": 20,
        "tworzywo_sztuczne": 200,
        "szklo": 30,
    }
    materials_warehouse.reserved = {}
    materials_warehouse.pending_orders = {}


def test_stock_available():
    """Towar dostępny na magazynie - produkcja pomijana."""
    print("=== TEST 1: Towar na magazynie ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 1.0
    order = Order(order_id=1, customer_name="Test", total_value=100.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "production_done"
    assert order.production_stage == "completed"
    assert order.estimated_delivery is not None
    print(f"  -> Status: {order.status}, Dostawa: {order.estimated_delivery}")
    print("  PASSED\n")


def test_production_no_issues():
    """Brak towaru, produkcja przebiega bez problemów, surowce dostępne."""
    print("=== TEST 2: Produkcja bez problemów ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 0.0
    order = Order(order_id=2, customer_name="Test2", total_value=200.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "production_done"
    assert order.production_stage == "completed"
    assert order.estimated_delivery is not None
    print(f"  -> Status: {order.status}, Dostawa: {order.estimated_delivery}")
    print("  PASSED\n")


def test_missing_materials():
    """Brak surowców w magazynie - zamówienie brakujących, potem produkcja OK."""
    print("=== TEST 3: Brak surowców → zamówienie ===")
    reset_warehouse()
    # Opróżniamy magazyn surowców
    materials_warehouse.stock = {"stal": 0, "tworzywo_sztuczne": 0}
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 0.0
    order = Order(order_id=3, customer_name="Test3", total_value=300.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "production_done"
    assert order.production_stage == "completed"
    assert order.materials_ordered is True
    print(f"  -> Status: {order.status}, Materiały zamówione: {order.materials_ordered}")
    print("  PASSED\n")


def test_halt_delivery_on_time():
    """Wstrzymanie produkcji, ale dostawa zdąży - automatyczna kontynuacja."""
    print("=== TEST 4: Wstrzymanie, dostawa zdąży ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 1.0
    production.DELIVERY_ON_TIME_CHANCE = 1.0
    order = Order(order_id=4, customer_name="Test4", total_value=400.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "production_done"
    assert order.production_stage == "completed"
    print(f"  -> Status: {order.status}")
    print("  PASSED\n")


def test_halt_client_continues():
    """Wstrzymanie, dostawa nie zdąży, klient decyduje: kontynuuj."""
    print("=== TEST 5: Wstrzymanie, klient kontynuuje ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 1.0
    production.DELIVERY_ON_TIME_CHANCE = 0.0
    order = Order(order_id=5, customer_name="Test5", total_value=500.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "awaiting_client_decision"
    assert order.production_stage == "waiting_client"
    print(f"  -> Status po produkcji: {order.status}")

    # Klient kontynuuje
    print("  -> Klient: KONTYNUACJA")
    results2 = proc.handle_client_decision(True)
    print_results(results2)
    assert order.status == "production_done"
    assert order.production_stage == "completed"
    assert order.estimated_delivery is not None
    print(f"  -> Status: {order.status}, Dostawa: {order.estimated_delivery}")
    print("  PASSED\n")


def test_halt_client_cancels():
    """Wstrzymanie, dostawa nie zdąży, klient decyduje: anuluj."""
    print("=== TEST 6: Wstrzymanie, klient anuluje ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 1.0
    production.DELIVERY_ON_TIME_CHANCE = 0.0
    order = Order(order_id=6, customer_name="Test6", total_value=600.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "awaiting_client_decision"

    # Klient anuluje
    print("  -> Klient: ANULOWANIE")
    results2 = proc.handle_client_decision(False)
    print_results(results2)
    assert order.status == "cancelled"
    assert order.production_stage == "cancelled"
    print(f"  -> Status: {order.status}")
    print("  PASSED\n")


def test_missing_materials_and_halt():
    """Brak surowców + wstrzymanie produkcji (podwójny problem)."""
    print("=== TEST 7: Brak surowców + wstrzymanie ===")
    reset_warehouse()
    materials_warehouse.stock = {"stal": 0, "tworzywo_sztuczne": 0}
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 1.0
    production.DELIVERY_ON_TIME_CHANCE = 1.0
    order = Order(order_id=7, customer_name="Test7", total_value=700.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    # Po zamówieniu surowców i wstrzymaniu, ale dostawa zdąży
    assert order.status == "production_done"
    assert order.materials_ordered is True
    print(f"  -> Status: {order.status}, Materiały zamówione: {order.materials_ordered}")
    print("  PASSED\n")


def test_high_value_order():
    """Zamówienie o wysokiej wartości wymaga więcej surowców (elektronika, szkło)."""
    print("=== TEST 8: Zamówienie > 1000 PLN (rozszerzony BOM) ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 0.0
    order = Order(order_id=8, customer_name="Test8", total_value=2500.0)
    proc = ProductionProcess(order)
    results = proc.start()
    print_results(results)
    assert order.status == "production_done"
    # Sprawdź że wymagano elektroniki i szkła
    assert "elektronika" in proc.required_materials
    assert "szklo" in proc.required_materials
    print(f"  -> BOM: {proc.required_materials}")
    print("  PASSED\n")


def test_warehouse_state_after_production():
    """Sprawdza że magazyn surowców jest poprawnie aktualizowany po produkcji."""
    print("=== TEST 9: Stan magazynu po produkcji ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 0.0

    initial_stal = materials_warehouse.stock["stal"]
    initial_plastic = materials_warehouse.stock["tworzywo_sztuczne"]

    order = Order(order_id=9, customer_name="Test9", total_value=200.0)
    proc = ProductionProcess(order)
    proc.start()

    # Surowce powinny być zużyte
    assert materials_warehouse.stock["stal"] == initial_stal - 5
    assert materials_warehouse.stock["tworzywo_sztuczne"] == initial_plastic - 10
    # Rezerwacje powinny być zwolnione (zużyte)
    assert materials_warehouse.reserved.get("stal", 0) == 0
    assert materials_warehouse.reserved.get("tworzywo_sztuczne", 0) == 0
    print(f"  -> Stal: {initial_stal} -> {materials_warehouse.stock['stal']}")
    print(f"  -> Tworzywo: {initial_plastic} -> {materials_warehouse.stock['tworzywo_sztuczne']}")
    print("  PASSED\n")


def test_cancellation_releases_materials():
    """Sprawdza że anulowanie zwalnia zarezerwowane surowce."""
    print("=== TEST 10: Anulowanie zwalnia rezerwacje ===")
    reset_warehouse()
    production.STOCK_AVAILABILITY_CHANCE = 0.0
    production.PRODUCTION_HALT_CHANCE = 1.0
    production.DELIVERY_ON_TIME_CHANCE = 0.0

    initial_stal = materials_warehouse.stock["stal"]

    order = Order(order_id=10, customer_name="Test10", total_value=200.0)
    proc = ProductionProcess(order)
    proc.start()

    # Po wstrzymaniu surowce są zarezerwowane ale nie zużyte
    assert order.status == "awaiting_client_decision"

    # Anulowanie powinno zwolnić rezerwacje
    proc.handle_client_decision(False)
    assert materials_warehouse.reserved.get("stal", 0) == 0
    assert materials_warehouse.reserved.get("tworzywo_sztuczne", 0) == 0
    # Surowce powinny wrócić do puli (nie zostały zużyte)
    assert materials_warehouse.stock["stal"] == initial_stal
    print(f"  -> Stal po anulowaniu: {materials_warehouse.stock['stal']} (niezmieniona)")
    print("  PASSED\n")


if __name__ == "__main__":
    print("=" * 60)
    print("TESTY PODPROCESU PRODUKCJA")
    print("=" * 60)
    print()

    test_stock_available()
    test_production_no_issues()
    test_missing_materials()
    test_halt_delivery_on_time()
    test_halt_client_continues()
    test_halt_client_cancels()
    test_missing_materials_and_halt()
    test_high_value_order()
    test_warehouse_state_after_production()
    test_cancellation_releases_materials()

    print("=" * 60)
    print("WSZYSTKIE TESTY PRZESZŁY POMYŚLNIE!")
    print("=" * 60)
