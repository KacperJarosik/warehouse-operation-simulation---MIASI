import socket
import tkinter as tk
from tkinter import messagebox, ttk

from models import Message, Order
from network import DEFAULT_HOST, DEFAULT_PORT, LineSocketReader, send_message
from production import ProductionProcess


class ServerApp:
    # Okno serwera pozwala prowadzić prezentację "od zaplecza":
    # odbierać zamówienia i ręcznie uruchamiać kolejne kroki procesu.
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MIASI - Serwer")
        self.root.geometry("1100x720")

        self.server_socket: socket.socket | None = None
        self.client_socket: socket.socket | None = None
        self.reader: LineSocketReader | None = None
        self.orders: dict[int, Order] = {}
        self.productions: dict[int, ProductionProcess] = {}
        self.selected_order_id: int | None = None

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.connection_var = tk.StringVar(value="Serwer zatrzymany")
        self.order_details_var = tk.StringVar(value="Brak zamówienia")

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_layout(self) -> None:
        # Interfejs jest podzielony na trzy główne sekcje:
        # konfigurację połączenia, listę zamówień i akcje serwera.
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Aplikacja serwera", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            main,
            text="Serwer odbiera zamówienia od klienta i pozwala ręcznie sterować kolejnymi krokami procesu.",
        ).pack(anchor="w", pady=(4, 16))

        config = ttk.LabelFrame(main, text="Połączenie", padding=12)
        config.pack(fill="x")

        ttk.Label(config, text="Host").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(config, textvariable=self.host_var, width=18).grid(row=0, column=1, sticky="w")
        ttk.Label(config, text="Port").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Entry(config, textvariable=self.port_var, width=12).grid(row=0, column=3, sticky="w")
        ttk.Button(config, text="Uruchom serwer", command=self.start_server).grid(row=0, column=4, padx=(16, 8))
        ttk.Button(config, text="Zatrzymaj", command=self.stop_server).grid(row=0, column=5)
        ttk.Label(config, textvariable=self.connection_var).grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True, pady=(16, 0))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        orders_frame = ttk.LabelFrame(content, text="Zamówienia", padding=12)
        orders_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        orders_frame.rowconfigure(1, weight=1)

        self.orders_list = tk.Listbox(orders_frame, height=18)
        self.orders_list.grid(row=1, column=0, sticky="nsew")
        self.orders_list.bind("<<ListboxSelect>>", self._on_select_order)

        ttk.Label(orders_frame, textvariable=self.order_details_var, wraplength=280, justify="left").grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )

        actions = ttk.LabelFrame(content, text="Akcje serwera", padding=12)
        actions.grid(row=0, column=1, sticky="nsew")

        ttk.Label(actions, text="Podproces Produkcja:", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=(0, 4))
        ttk.Button(actions, text="Uruchom produkcję (cały podproces)", command=self.run_production).pack(fill="x", pady=(0, 8))

        ttk.Separator(actions, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(actions, text="Akcje po produkcji:", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=(0, 4))
        ttk.Button(actions, text="Przygotuj wycenę", command=self.send_quote).pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="Potwierdź wysyłkę", command=self.send_shipment).pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="Symuluj opóźnienie (ręcznie)", command=self.send_delay_notice).pack(fill="x")

        log_frame = ttk.LabelFrame(actions, text="Log serwera", padding=12)
        log_frame.pack(fill="both", expand=True, pady=(16, 0))
        self.log_text = tk.Text(log_frame, height=20, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def start_server(self) -> None:
        # Serwer uruchamia nasłuchiwanie tylko raz. Kolejne kliknięcia
        # nie tworzą nowych gniazd, jeśli serwer już działa.
        if self.server_socket is not None:
            return

        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Błąd", "Port musi być liczbą całkowitą.")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((host, port))
            self.server_socket.listen(1)
        except OSError as exc:
            self.server_socket = None
            messagebox.showerror("Błąd serwera", str(exc))
            return

        self.connection_var.set(f"Nasłuchiwanie na {host}:{port}")
        self._append_log(f"Serwer: uruchomiono nasłuchiwanie na {host}:{port}.")
        self.root.after(100, self._poll_for_client)

    def _poll_for_client(self) -> None:
        # Akceptowanie połączenia jest wykonywane małymi krokami
        # przez root.after(), żeby nie blokować okna tkinter.
        if self.server_socket is None or self.client_socket is not None:
            return

        self.server_socket.settimeout(0.1)
        try:
            client_socket, address = self.server_socket.accept()
        except TimeoutError:
            self.root.after(250, self._poll_for_client)
            return
        except OSError:
            return

        self.client_socket = client_socket
        self.connection_var.set(f"Połączono z klientem {address[0]}:{address[1]}")
        self._append_log(f"Serwer: połączono z klientem {address[0]}:{address[1]}.")
        self.reader = LineSocketReader(self.client_socket, self._handle_message, self._handle_disconnect)
        self.reader.start()

    def _handle_message(self, message: Message) -> None:
        # Otrzymany komunikat przekazujemy do pętli GUI.
        self.root.after(0, lambda: self._process_message(message))

    def _process_message(self, message: Message) -> None:
        # Serwer aktualizuje stan lokalny na podstawie komunikatów klienta.
        if message.event == "new_order":
            order = Order(
                order_id=int(message.payload["order_id"]),
                customer_name=str(message.payload["customer_name"]),
                total_value=float(message.payload["total_value"]),
                status="received",
            )
            self.orders[order.order_id] = order
            self._refresh_orders()
            self._append_log(f"Serwer: otrzymano zamówienie {order.order_id} od klienta {order.customer_name}.")
            return

        if message.event == "payment_received":
            order_id = int(message.payload["order_id"])
            order = self.orders.get(order_id)
            if order is None:
                self._append_log(f"Serwer: płatność dla nieznanego zamówienia {order_id}.")
                return
            order.status = "paid"
            self._refresh_orders()
            self._append_log(f"Serwer: klient opłacił zamówienie {order_id}.")
            return

        if message.event == "delay_response":
            order_id = int(message.payload["order_id"])
            continue_order = bool(message.payload["continue_order"])
            decision = "kontynuacja" if continue_order else "anulowanie"
            self._append_log(f"Serwer: klient odpowiedział '{decision}' dla zamówienia {order_id}.")

            # Obsługa decyzji klienta w kontekście podprocesu Produkcja
            production = self.productions.get(order_id)
            if production is not None and production.order.production_stage == "waiting_client":
                results = production.handle_client_decision(continue_order)
                for r in results:
                    self._append_log(f"  [Produkcja] {r.message}")
                self._refresh_orders()
                # Jeśli produkcja zakończona sukcesem, automatycznie wysyłamy wycenę
                if production.order.status == "production_done":
                    self._append_log(f"Serwer: produkcja zakończona - zamówienie {order_id} gotowe do wyceny.")
                elif production.order.status == "cancelled":
                    self._append_log(f"Serwer: zamówienie {order_id} anulowane przez klienta.")

    def run_production(self) -> None:
        # Uruchamia cały podproces Produkcja z BPMN dla wybranego zamówienia.
        order = self._selected_order()
        if order is None:
            return

        if order.production_stage == "completed":
            messagebox.showinfo("Informacja", "Produkcja już zakończona dla tego zamówienia.")
            return
        if order.production_stage == "waiting_client":
            messagebox.showinfo("Informacja", "Oczekiwanie na decyzję klienta - użyj przycisków w aplikacji klienta.")
            return

        # Tworzymy lub pobieramy proces produkcji
        if order.order_id not in self.productions:
            self.productions[order.order_id] = ProductionProcess(order)

        production = self.productions[order.order_id]
        self._append_log(f"--- Podproces PRODUKCJA dla zamówienia {order.order_id} ---")

        results = production.start()

        for r in results:
            prefix = "✓" if r.success else "✗"
            self._append_log(f"  {prefix} {r.message}")

        self._refresh_orders()

        # Sprawdzamy końcowy stan
        if order.status == "awaiting_client_decision":
            # Trzeba poinformować klienta o opóźnieniu
            self._append_log(f"Serwer: wysyłam informację o opóźnieniu do klienta...")
            if self.client_socket is not None:
                self._send(
                    Message(
                        sender="server",
                        receiver="client",
                        event="delay_notice",
                        payload={"order_id": order.order_id},
                    )
                )
            self._append_log(f"Serwer: oczekiwanie na decyzję klienta (kontynuacja/anulowanie).")
        elif order.status == "production_done":
            self._append_log(f"Serwer: podproces Produkcja zakończony sukcesem.")
            self._append_log(f"Serwer: zamówienie {order.order_id} gotowe do wyceny (kliknij 'Przygotuj wycenę').")

    def send_quote(self) -> None:
        # Akcja ręczna po stronie serwera: przygotowanie i wysłanie wyceny.
        order = self._selected_order()
        if order is None:
            return
        if self.client_socket is None:
            messagebox.showwarning("Brak połączenia", "Najpierw połącz klienta z serwerem.")
            return
        if not self._send(
            Message(
                sender="server",
                receiver="client",
                event="quote_ready",
                payload={
                    "order_id": order.order_id,
                    "total_value": order.total_value,
                    "estimated_delivery": order.estimated_delivery or "nieznana",
                },
            )
        ):
            return
        order.status = "quoted"
        self._refresh_orders()
        self._append_log(f"Serwer: wysłano wycenę dla zamówienia {order.order_id}.")

    def send_shipment(self) -> None:
        # Wysyłka jest potwierdzana osobnym komunikatem do klienta.
        order = self._selected_order()
        if order is None:
            return
        if self.client_socket is None:
            messagebox.showwarning("Brak połączenia", "Najpierw połącz klienta z serwerem.")
            return
        if not self._send(
            Message(
                sender="server",
                receiver="client",
                event="shipment_sent",
                payload={"order_id": order.order_id},
            )
        ):
            return
        order.status = "shipped"
        self._refresh_orders()
        self._append_log(f"Serwer: wysłano informację o wysyłce zamówienia {order.order_id}.")

    def send_delay_notice(self) -> None:
        # Symulacja ścieżki alternatywnej z BPMN: informacja o opóźnieniu.
        order = self._selected_order()
        if order is None:
            return
        if self.client_socket is None:
            messagebox.showwarning("Brak połączenia", "Najpierw połącz klienta z serwerem.")
            return
        if not self._send(
            Message(
                sender="server",
                receiver="client",
                event="delay_notice",
                payload={"order_id": order.order_id},
            )
        ):
            return
        order.status = "delayed"
        self._refresh_orders()
        self._append_log(f"Serwer: wysłano informację o opóźnieniu dla zamówienia {order.order_id}.")

    def _send(self, message: Message) -> bool:
        # Wspólna metoda wysyłki, żeby w jednym miejscu obsłużyć błędy sieciowe.
        if self.client_socket is None:
            messagebox.showwarning("Brak połączenia", "Najpierw połącz klienta z serwerem.")
            return False
        try:
            send_message(self.client_socket, message)
        except OSError as exc:
            messagebox.showerror("Błąd wysyłki", str(exc))
            self._handle_disconnect()
            return False
        return True

    def _refresh_orders(self) -> None:
        # Odtwarzamy listę na podstawie aktualnego słownika zamówień
        # i próbujemy zachować poprzedni wybór użytkownika.
        current_selection = self.selected_order_id
        self.orders_list.delete(0, "end")
        for order_id in sorted(self.orders):
            order = self.orders[order_id]
            self.orders_list.insert("end", f"{order.order_id} | {order.customer_name} | {order.status}")
        if current_selection is not None:
            for index in range(self.orders_list.size()):
                if self.orders_list.get(index).startswith(str(current_selection)):
                    self.orders_list.selection_set(index)
                    break
        self._update_order_details()

    def _selected_order(self) -> Order | None:
        # Serwer wykonuje akcje zawsze na zamówieniu wskazanym na liście.
        if self.selected_order_id is None:
            messagebox.showinfo("Informacja", "Wybierz zamówienie z listy.")
            return None
        return self.orders.get(self.selected_order_id)

    def _on_select_order(self, _event: tk.Event) -> None:
        # Odczytujemy ID z tekstu wiersza listy.
        selection = self.orders_list.curselection()
        if not selection:
            self.selected_order_id = None
            self._update_order_details()
            return
        item = self.orders_list.get(selection[0])
        self.selected_order_id = int(item.split("|")[0].strip())
        self._update_order_details()

    def _update_order_details(self) -> None:
        # Panel szczegółów ułatwia szybką prezentację statusu zamówienia.
        if self.selected_order_id is None or self.selected_order_id not in self.orders:
            self.order_details_var.set("Brak zamówienia")
            return
        order = self.orders[self.selected_order_id]
        details = (
            f"ID: {order.order_id}\n"
            f"Klient: {order.customer_name}\n"
            f"Kwota: {order.total_value:.2f} PLN\n"
            f"Status: {order.status}\n"
            f"Etap produkcji: {order.production_stage or 'brak'}\n"
            f"Surowce zamówione: {'tak' if order.materials_ordered else 'nie'}\n"
            f"Szac. dostawa: {order.estimated_delivery or 'brak'}"
        )
        self.order_details_var.set(details)

    def _handle_disconnect(self) -> None:
        # Po rozłączeniu wracamy do stanu gotowości na następnego klienta.
        def cleanup() -> None:
            self._append_log("Serwer: klient został rozłączony.")
            self.connection_var.set("Oczekiwanie na klienta")
            if self.reader is not None:
                self.reader.stop()
                self.reader = None
            if self.client_socket is not None:
                try:
                    self.client_socket.close()
                except OSError:
                    pass
                self.client_socket = None
            if self.server_socket is not None:
                self.root.after(250, self._poll_for_client)

        self.root.after(0, cleanup)

    def stop_server(self) -> None:
        # Zatrzymujemy zarówno aktywne połączenie klienta, jak i gniazdo nasłuchujące.
        if self.reader is not None:
            self.reader.stop()
            self.reader = None
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except OSError:
                pass
            self.client_socket = None
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None
        self.connection_var.set("Serwer zatrzymany")
        self._append_log("Serwer: zatrzymano.")

    def _append_log(self, text: str) -> None:
        # Log jest tylko do odczytu, więc chwilowo przełączamy kontrolkę w tryb zapisu.
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_close(self) -> None:
        # Zamknięcie okna ma zawsze zostawić port i sockety zwolnione.
        self.stop_server()
        self.root.destroy()


def main() -> None:
    # Standardowy punkt wejścia dla aplikacji serwera.
    root = tk.Tk()
    ServerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
