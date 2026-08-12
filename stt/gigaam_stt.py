"""GigaAM STT adapter (on-prem). Stub fallback without installed weights."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

logger = logging.getLogger("max_tracker_agent.stt")


class STTClient(Protocol):
    async def transcribe(self, audio_path: str) -> str: ...


@dataclass
class GigaAMConfig:
    model: str = "v3_e2e_rnnt"
    device: str = "cuda"
    model_dir: str = "./models/gigaam"
    allow_stub: bool = True


class StubSTT:
    """For local demos without GPU/weights."""

    async def transcribe(self, audio_path: str) -> str:
        name = Path(audio_path).name
        logger.info("STT stub: fake transcript for %s", name)
        return (
            "Создай задачу: подготовить отчёт по инцидентам на Иванова до пятницы"
        )


class GigaAMSTT:
    """
    Wrapper around https://github.com/salute-developers/GigaAM

    Install on GPU host:
      git clone https://github.com/salute-developers/GigaAM.git
      cd GigaAM && pip install -e ".[torch]"
    """

    def __init__(self, config: GigaAMConfig):
        self._config = config
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            import gigaam  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Пакет gigaam не установлен. "
                "См. https://github.com/salute-developers/GigaAM или включите STT_ALLOW_STUB=1"
            ) from e
        logger.info(
            "Loading GigaAM model=%s device=%s dir=%s",
            self._config.model,
            self._config.device,
            self._config.model_dir,
        )
        self._model = gigaam.load_model(self._config.model)
        return self._model

    async def transcribe(self, audio_path: str) -> str:
        model = self._load()
        text = model.transcribe(audio_path)
        return (text or "").strip()


def build_stt(config: GigaAMConfig) -> STTClient:
    if config.allow_stub:
        # Prefer real GigaAM if importable, else stub.
        try:
            import gigaam  # noqa: F401

            return GigaAMSTT(config)
        except ImportError:
            logger.warning("gigaam not installed — using StubSTT")
            return StubSTT()
    return GigaAMSTT(config)
