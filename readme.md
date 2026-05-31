# Plan realizacji projektu w Pythonie

## Założenie
Implementujemy proces obsługi zamówienia pokazany na BPMN jako aplikację desktopową w Pythonie. Architektura będzie oparta o dwa osobne procesy i dwie osobne aplikacje desktopowe:

- aplikację `Klient`, która inicjuje zamówienie i reaguje na komunikaty,
- aplikację `Serwer`, która realizuje logikę magazynu, produkcji, wyceny, płatności i wysyłki.

Obie strony będą miały własne GUI. Komunikacja będzie realizowana w modelu klient-serwer przez gniazda TCP na `localhost`.

## Sprint 1 - Prototyp komunikacji i GUI
### Cel
Zbudować działający szkielet dwóch osobnych aplikacji z prostą komunikacją klient-serwer oraz interfejsami GUI po obu stronach.

### Zakres
- przygotowanie struktury projektu w Pythonie,
- uruchamianie dwóch osobnych aplikacji: `client_app.py` i `server_app.py`,
- komunikacja przez TCP na `localhost`,
- prosty model komunikatów: `new_order`, `quote_ready`, `payment_received`, `shipment_sent`,
- GUI klienta w `tkinter` z przyciskami do:
  - połączenia z serwerem,
  - wysłania nowego zamówienia,
  - wysłania płatności,
- GUI serwera w `tkinter` z przyciskami do:
  - uruchomienia nasłuchiwania,
  - przygotowania wyceny,
  - wysłania informacji o wysyłce,
  - zasymulowania opóźnienia,
- log zdarzeń pokazujący przepływ informacji między aplikacjami,
- podstawowe dane zamówienia: identyfikator, klient, kwota, status.

### Rezultat sprintu
Demonstrator pokazujący, że dwie osobne aplikacje potrafią się komunikować, a podczas prezentacji można aktywnie działać po stronie klienta i serwera.

## Sprint 2 - Odwzorowanie głównej ścieżki BPMN
### Cel
Rozszerzyć prototyp do głównego scenariusza biznesowego z magazynem, produkcją, wyceną i płatnością.

### Zakres
- sprawdzanie dostępności towaru,
- przejście: magazyn albo produkcja,
- uproszczona produkcja z etapami:
  - planowanie,
  - rezerwacja surowców,
  - produkcja,
- oszacowanie daty dostawy,
- wycena zamówienia i przekazanie jej klientowi,
- oczekiwanie na płatność,
- walidacja płatności,
- przejście do przygotowania przesyłki i wysyłki,
- reprezentacja statusów procesu w GUI.

### Rezultat sprintu
Możliwość przejścia przez podstawowy, poprawny scenariusz realizacji zamówienia zgodny z BPMN.

## Sprint 3 - Obsługa wyjątków, anulacje i dopracowanie
### Cel
Dodać alternatywne ścieżki procesu oraz poprawić jakość demonstratora.

### Zakres
- brak towaru i brak surowców,
- opóźnienie produkcji lub dostawy,
- komunikat do klienta o opóźnieniu,
- decyzja klienta: kontynuacja albo anulowanie,
- anulowanie przy braku płatności w terminie,
- anulowanie przy nieprawidłowej płatności,
- czytelniejsze GUI:
  - panel statusu,
  - historia komunikatów,
  - formularz parametrów zamówienia,
- porządki w kodzie i przygotowanie do prezentacji projektu.

### Rezultat sprintu
Prototyp dobrze odwzorowujący proces biznesowy wraz z wyjątkami i ścieżkami alternatywnymi.

## Proponowany podział techniczny
- `client_app.py` - aplikacja klienta,
- `server_app.py` - aplikacja serwera,
- `network.py` - komunikacja TCP i obsługa komunikatów,
- `models.py` - struktury danych komunikatów i zamówień,
- `plan_sprintow.md` - plan realizacji projektu.
