from collections import deque
from decimal import Decimal


class WeightBuffer:
    """Mantém as últimas N leituras de peso e decide se estão estáveis."""

    def __init__(self, samples: int, tolerance_g: Decimal):
        self._samples = samples
        self._tolerance = Decimal(str(tolerance_g))
        self._buf: deque[Decimal] = deque(maxlen=samples)

    def add(self, peso_g: Decimal) -> None:
        self._buf.append(Decimal(str(peso_g)))

    def is_stable(self) -> bool:
        if len(self._buf) < self._samples:
            return False
        return (max(self._buf) - min(self._buf)) <= self._tolerance

    def stable_value(self) -> Decimal | None:
        if not self.is_stable():
            return None
        return sum(self._buf) / len(self._buf)
