import socket
import tkinter as tk
from tkinter import messagebox, ttk

from models import Message
from network import DEFAULT_HOST, DEFAULT_PORT, LineSocketReader, send_message


class ClientApp:
    # Okno klienta reprezentuje uczestnika procesu BPMN,
    # który wysyła zamówienie i odpowiada na komunikaty z serwera.
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MIASI - Klient")
        self.root.geometry("940x620")

        self.sock: socket.socket | None = None
        self.reader: LineSocketReader | None = None
        self.next_order_id = 1001
        self.last_order_id: int | None = None

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.connection_var = tk.StringVar(value="Brak połączenia")
        self.status_var = tk.StringVar(value="Ostatnie zamówienie: brak")
        self.customer_var = tk.StringVar(value="Jan Kowalski")
        self.value_var = tk.StringVar(value="2499.99")

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_layout(self) -> None:
        # Budujemy wszystkie sekcje GUI w jednym miejscu, żeby łatwo
        # było później przenosić lub rozbudowywać interfejs.
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Aplikacja klienta", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            main,
            text="Klient wysyła zamówienie do serwera, opłaca je i odbiera komunikaty o wycenie, opóźnieniu i wysyłce.",
        ).pack(anchor="w", pady=(4, 16))

        connection = ttk.LabelFrame(main, text="Połączenie", padding=12)
        connection.pack(fill="x")

        ttk.Label(connection, text="Host").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(connection, textvariable=self.host_var, width=18).grid(row=0, column=1, sticky="w")
        ttk.Label(connection, text="Port").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Entry(connection, textvariable=self.port_var, width=12).grid(row=0, column=3, sticky="w")
        ttk.Button(connection, text="Połącz", command=self.connect_to_server).grid(row=0, column=4, padx=(16, 8))
        ttk.Button(connection, text="Rozłącz", command=self.disconnect).grid(row=0, column=5)
        ttk.Label(connection, textvariable=self.connection_var).grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        form = ttk.LabelFrame(main, text="Dane zamówienia", padding=12)
        form.pack(fill="x", pady=(16, 0))

        ttk.Label(form, text="Klient").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(form, textvariable=self.customer_var, width=32).grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="Kwota [PLN]").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(form, textvariable=self.value_var, width=32).grid(row=1, column=1, sticky="w")

        buttons = ttk.Frame(main, padding=(0, 16, 0, 16))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Wyślij zamówienie", command=self.send_order).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Wyślij płatność", command=self.send_payment).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Kontynuuj mimo opóźnienia", command=lambda: self.send_delay_response(True)).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Anuluj po opóźnieniu", command=lambda: self.send_delay_response(False)).pack(
            side="left"
        )

        ttk.Label(main, textvariable=self.status_var, font=("Segoe UI", 10, "italic")).pack(anchor="w", pady=(0, 8))

        log_frame = ttk.LabelFrame(main, text="Log klienta", padding=12)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=20, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def connect_to_server(self) -> None:
        # Klient inicjuje połączenie TCP z aplikacją serwera.
        if self.sock is not None:
            return

        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Błąd", "Port musi być liczbą całkowitą.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
        except OSError as exc:
            self.sock = None
            messagebox.showerror("Błąd połączenia", str(exc))
            return

        self.connection_var.set(f"Połączono z serwerem {host}:{port}")
        self._append_log(f"Klient: połączono z serwerem {host}:{port}.")
        self.reader = LineSocketReader(self.sock, self._handle_message, self._handle_disconnect)
        self.reader.start()

    def send_order(self) -> None:
        # To jest główny punkt startu prezentacji:
        # klient tworzy zamówienie i wysyła je do serwera.
        if self.sock is None:
            messagebox.showwarning("Brak połączenia", "Najpierw połącz z serwerem.")
            return

        customer_name = self.customer_var.get().strip()
        if not customer_name:
            messagebox.showerror("Błąd", "Podaj nazwę klienta.")
            return

        try:
            total_value = float(self.value_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Błąd", "Kwota musi być liczbą.")
            return

        order_id = self.next_order_id
        self.next_order_id += 1
        self.last_order_id = order_id
        self.status_var.set(f"Ostatnie zamówienie: {order_id}")
        send_message(
            self.sock,
            Message(
                sender="client",
                receiver="server",
                event="new_order",
                payload={
                    "order_id": order_id,
                    "customer_name": customer_name,
                    "total_value": total_value,
                },
            ),
        )
        self._append_log(f"Klient: wysłano zamówienie {order_id} dla klienta {customer_name}.")

    def send_payment(self) -> None:
        # W sprincie 1 płatność to osobny komunikat uruchamiany ręcznie z GUI.
        order_id = self._require_order_id()
        if order_id is None or self.sock is None:
            return

        send_message(
            self.sock,
            Message(
                sender="client",
                receiver="server",
                event="payment_received",
                payload={"order_id": order_id},
            ),
        )
        self._append_log(f"Klient: wysłano płatność dla zamówienia {order_id}.")

    def send_delay_response(self, continue_order: bool) -> None:
        # Odpowiedź klienta na informację o opóźnieniu.
        # Dzięki temu już w 1. sprincie widać dwukierunkową komunikację.
        order_id = self._require_order_id()
        if order_id is None or self.sock is None:
            return

        decision = "kontynuacja" if continue_order else "anulowanie"
        send_message(
            self.sock,
            Message(
                sender="client",
                receiver="server",
                event="delay_response",
                payload={"order_id": order_id, "continue_order": continue_order},
            ),
        )
        self._append_log(f"Klient: wysłano decyzję '{decision}' dla zamówienia {order_id}.")

    def _require_order_id(self) -> int | None:
        # Większość akcji klienta odnosi się do ostatnio wysłanego zamówienia.
        if self.last_order_id is None:
            messagebox.showinfo("Informacja", "Najpierw wyślij zamówienie.")
            return None
        return self.last_order_id

    def _handle_message(self, message: Message) -> None:
        # Odbiór przychodzi z wątku sieciowego, więc przekazujemy go
        # do głównej pętli tkinter przez root.after().
        self.root.after(0, lambda: self._process_message(message))

    def _process_message(self, message: Message) -> None:
        # Tutaj mapujemy typ komunikatu na zachowanie GUI klienta.
        order_id = message.payload.get("order_id", "?")
        if message.event == "quote_ready":
            total_value = float(message.payload["total_value"])
            self._append_log(f"Klient: otrzymano wycenę dla zamówienia {order_id} na kwotę {total_value:.2f} PLN.")
            return
        if message.event == "shipment_sent":
            self._append_log(f"Klient: otrzymano informację o wysyłce zamówienia {order_id}.")
            return
        if message.event == "delay_notice":
            self._append_log(f"Klient: otrzymano informację o opóźnieniu dla zamówienia {order_id}.")

    def _handle_disconnect(self) -> None:
        # Sprzątanie po utracie połączenia jest wykonywane bezpiecznie
        # w wątku GUI, żeby nie mieszać operacji tkinter między wątkami.
        def cleanup() -> None:
            if self.reader is not None:
                self.reader.stop()
                self.reader = None
            if self.sock is not None:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
            self.connection_var.set("Brak połączenia")
            self._append_log("Klient: rozłączono z serwerem.")

        self.root.after(0, cleanup)

    def disconnect(self) -> None:
        self._handle_disconnect()

    def _append_log(self, text: str) -> None:
        # Log jest tylko do odczytu, aktualizujemy go chwilowo w trybie editable.
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_close(self) -> None:
        # Przy zamknięciu okna chcemy zwolnić socket i zatrzymać wątek odbiorczy.
        self.disconnect()
        self.root.destroy()


def main() -> None:
    # Standardowy punkt wejścia dla aplikacji klienta.
    root = tk.Tk()
    ClientApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
