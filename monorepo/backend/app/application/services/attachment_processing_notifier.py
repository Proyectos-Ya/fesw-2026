"""Notificador de señal para la cola de procesamiento de anexos (plan 233, decisión 4)."""

from abc import ABC, abstractmethod


class IAttachmentProcessingNotifier(ABC):
    @abstractmethod
    def notify(self) -> None:
        """Despierta al bucle worker si está esperando en reposo."""
        ...


class NoopProcessingNotifier(IAttachmentProcessingNotifier):
    def notify(self) -> None:
        pass
