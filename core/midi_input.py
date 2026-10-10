from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal


class MidiInput(QObject):
    note_on = pyqtSignal(int, int, int)  # channel, note, velocity
    note_off = pyqtSignal(int, int)  # channel, note
    control_change = pyqtSignal(int, int, int)  # channel, controller, value
    pitch_bend = pyqtSignal(int, int)  # channel, pitch (-8192..8191)
    channel_pressure = pyqtSignal(int, int)  # channel, pressure
    poly_pressure = pyqtSignal(int, int, int)  # channel, note, pressure

    def __init__(self) -> None:
        super().__init__()
        self._port: Optional[Any] = None

    @staticmethod
    def input_ports() -> list[str]:
        import mido

        return mido.get_input_names()

    def open_port(self, name: str) -> None:
        self.close()
        import mido

        self._port = mido.open_input(name, callback=self._handle_message)

    def close(self) -> None:
        port = self._port
        self._port = None
        if port is not None:
            port.close()

    def _handle_message(self, message: Any) -> None:
        if message.type == "note_on" and message.velocity > 0:
            self.note_on.emit(message.channel, message.note, message.velocity)
        elif message.type == "note_off" or message.type == "note_on":
            self.note_off.emit(message.channel, message.note)
        elif message.type == "control_change":
            self.control_change.emit(
                message.channel, message.control, message.value
            )
        elif message.type == "pitchwheel":
            self.pitch_bend.emit(message.channel, message.pitch)
        elif message.type == "aftertouch":
            self.channel_pressure.emit(message.channel, message.value)
        elif message.type == "polytouch":
            self.poly_pressure.emit(
                message.channel, message.note, message.value
            )