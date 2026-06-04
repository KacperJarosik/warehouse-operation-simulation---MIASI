# Changelog

## Sprint 2 - Podproces Produkcja

### Nowe pliki

#### `production.py`
Moduł zawierający pełną logikę podprocesu **Produkcja** z diagramu BPMN:

- **Klasa `ProductionProcess`** — orkiestracja kroków podprocesu dla jednego zamówienia:
  1. Sprawdzenie dostępności towaru na magazynie (`check_stock`)
  2. Zaplanuj produkcję (`_plan_production`) — BOM, plan, linia produkcyjna
  3. Zarezerwuj surowce (`_reserve_materials`) — sprawdzenie magazynu, blokowanie
  4. Boundary event: brak surowców → zamów brakujące (`_order_missing_materials`)
  5. Wyprodukuj towary (`_produce_goods`) — linia produkcyjna, postęp
  6. Boundary event: wstrzymanie produkcji → sprawdź termin (`check_delivery_deadline`)
  7. Oszacuj datę dostawy (`estimate_delivery_date`)

- **Klasa `ProductionStepResult`** — wynik pojedynczego kroku (success, message, data)
- **Klasa `MaterialsWarehouse`** — stan magazynu surowców (stock, reserved, pending_orders)
- **Klasa `ProductionLine`** — linia produkcyjna (status, progress, halt/resume)

- **Funkcje procesu głównego (poza podprocesem):**
  - `check_stock()` — sprawdzenie dostępności gotowego towaru na magazynie
  - `check_delivery_deadline()` — sprawdzenie czy dostawa zdąży przed terminem
  - `estimate_delivery_date()` — oszacowanie dat wyjazdu i dostarczenia

- **Stałe konfiguracyjne** do sterowania symulacją (prawdopodobieństwa zdarzeń)

#### `test_production.py`
Testy jednostkowe pokrywające wszystkie ścieżki BPMN podprocesu Produkcja:
1. Towar dostępny na magazynie (produkcja pomijana)
2. Produkcja bez problemów
3. Brak surowców → zamówienie brakujących
4. Wstrzymanie produkcji, dostawa zdąży (automatyczna kontynuacja)
5. Wstrzymanie, dostawa nie zdąży, klient kontynuuje
6. Wstrzymanie, dostawa nie zdąży, klient anuluje
7. Brak surowców + wstrzymanie (podwójny problem)
8. Zamówienie > 1000 PLN (rozszerzony BOM)
9. Weryfikacja stanu magazynu po produkcji
10. Anulowanie zwalnia rezerwacje surowców

### Zmodyfikowane pliki

#### `models.py`
Rozszerzono dataclass `Order` o pola stanu podprocesu Produkcja:
- `production_stage: str | None` — etap produkcji
- `materials_ordered: bool` — czy surowce zamówione
- `production_halted: bool` — czy produkcja wstrzymana
- `estimated_delivery: str | None` — szacowana data dostawy

#### `server_app.py`
- Import modułu `production` (`ProductionProcess`)
- Dodano słownik `self.productions` przechowujący procesy produkcji per zamówienie
- Nowy przycisk GUI: **„Uruchom produkcję (cały podproces)"**
- Metoda `run_production()` — uruchamia cały podproces, loguje każdy krok, automatycznie wysyła `delay_notice` gdy wymagana decyzja klienta
- Rozbudowano `_process_message()` — obsługa `delay_response` w kontekście produkcji (wznowienie lub anulowanie)
- Rozbudowano `_update_order_details()` — wyświetla etap produkcji, zamówione surowce, szacowaną dostawę
- Rozbudowano `send_quote()` — payload zawiera `estimated_delivery`

#### `client_app.py`
- Rozbudowano `_process_message()` — obsługa nowych eventów:
  - `quote_ready` — wyświetla szacowaną datę dostawy
  - `delay_notice` — wyraźniejszy komunikat z instrukcją dla użytkownika
  - `order_cancelled` — informacja o anulowaniu z powodem
  - `production_status` — informacja o statusie produkcji

### Jak testować

```bash
# Testy jednostkowe podprocesu Produkcja
python test_production.py

# Testowanie manualne (dwa terminale)
python server_app.py
python client_app.py
```

Scenariusz testowy w GUI:
1. Serwer → „Uruchom serwer", Klient → „Połącz"
2. Klient → „Wyślij zamówienie"
3. Serwer → zaznacz zamówienie → „Uruchom produkcję (cały podproces)"
4. Obserwuj logi — proces automatycznie przechodzi przez wszystkie etapy
5. Jeśli wymagana decyzja klienta → Klient klika „Kontynuuj" lub „Anuluj"
6. Po zakończeniu produkcji → Serwer → „Przygotuj wycenę" → Klient → „Wyślij płatność" → Serwer → „Potwierdź wysyłkę"
