from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from purposebench.models import BenchmarkCase, ExecutionResult


class Adapter(ABC):
    @abstractmethod
    def execute(
        self,
        case: BenchmarkCase,
        policy: dict[str, Any],
        model: dict[str, Any],
        condition: str,
        seed: int,
    ) -> ExecutionResult:
        raise NotImplementedError
