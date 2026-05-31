import json
import socket
import threading
from dataclasses import asdict
from typing import Callable

from models import Message


# Wspólna konfiguracja połączenia dla obu aplikacji.
BUFFER_SIZE = 4096
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 50007


def message_to_wire(message: Message) -> bytes:
    # Każdy komunikat wysyłamy jako jedną linię JSON zakończoną "\n".
    # Dzięki temu odbiorca może łatwo rozdzielać kolejne wiadomości.
    return (json.dumps(asdict(message), ensure_ascii=False) + "\n").encode("utf-8")


def message_from_wire(raw_line: str) -> Message:
    # Odtwarzamy obiekt Message z tekstu odebranego z gniazda.
    data = json.loads(raw_line)
    return Message(
        sender=data["sender"],
        receiver=data["receiver"],
        event=data["event"],
        payload=data.get("payload", {}),
        created_at=data.get("created_at", ""),
    )


class LineSocketReader(threading.Thread):
    # Osobny wątek do odbioru danych z gniazda.
    # GUI tkinter nie powinno blokować się na recv(), dlatego komunikaty
    # odbieramy w tle i przekazujemy dalej przez callback.
    def __init__(
        self,
        sock: socket.socket,
        on_message: Callable[[Message], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        super().__init__(daemon=True)
        self.sock = sock
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self._running = True

    def run(self) -> None:
        # Buforujemy tekst aż do pojawienia się znaku końca linii.
        # To pozwala poprawnie obsłużyć sytuację, gdy jedna wiadomość
        # przyjdzie w kilku paczkach TCP.
        buffer = ""
        try:
            while self._running:
                data = self.sock.recv(BUFFER_SIZE)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    raw_line, buffer = buffer.split("\n", 1)
                    raw_line = raw_line.strip()
                    if raw_line:
                        self.on_message(message_from_wire(raw_line))
        except OSError:
            pass
        finally:
            self.on_disconnect()

    def stop(self) -> None:
        # Flaga zatrzymania jest sprawdzana w pętli odbiorczej.
        self._running = False


def send_message(sock: socket.socket, message: Message) -> None:
    # Funkcja pomocnicza do wysłania gotowego komunikatu.
    sock.sendall(message_to_wire(message))
