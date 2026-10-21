from __future__ import annotations

from dataclasses import dataclass
import json
import re

from hmi.trainui.models import TrainingMetrics

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
STEP_RE = re.compile(r"Step\s+(\d+):\s*(.*)")
VALUE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")
DICT_VALUE_RE = re.compile(
    r"[\"'](loss|grad_norm|param_norm)[\"']\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
)
DICT_STEP_RE = re.compile(r"[\"']step[\"']\s*:\s*(\d+)")
PROGRESS_RE = re.compile(
    r"Progress on:\s*(?P<current>-|[\d,]+(?:\.\d+)?[kKmMgGtTpPeE]?)\s*(?:it)?\s*/\s*"
    r"(?P<total>[\d,]+(?:\.\d+)?[kKmMgGtTpPeE]?)\s*(?:it)?(?=\s|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TrainingProgress:
    completed: int
    total: int


@dataclass(frozen=True)
class ParsedLogRecord:
    line: str
    metrics: TrainingMetrics | None
    event: dict | None
    progress: TrainingProgress | None


class LogParser:
    """Parse OpenPI stdout/stderr without depending on one logging format.

    OpenPI currently emits two independent streams that matter to TrainUI:
    - metric lines from pbar.write(): ``Step N: loss=..., ...``
    - tqdm-loggable progress lines: ``Progress on: 3.00it/10.0it ...``

    Progress must not be inferred from metric lines because ``log_interval`` can
    be much larger than one. The UI therefore treats tqdm progress as the
    authoritative source for the progress bar and metric lines as the source
    for the loss curve.
    """

    def __init__(self):
        self._buffer = ""
        self._last_metric_step = 0

    def reset(self) -> None:
        self._buffer = ""
        self._last_metric_step = 0

    def feed(self, chunk: str) -> list[ParsedLogRecord]:
        text = ANSI_RE.sub("", chunk).replace("\r", "\n")
        self._buffer += text
        parts = self._buffer.split("\n")
        self._buffer = parts.pop()

        records: list[ParsedLogRecord] = []
        for raw in parts:
            line = raw.strip()
            if not line:
                continue
            records.append(
                ParsedLogRecord(
                    line=line,
                    metrics=self.parse_metrics(line),
                    event=self.parse_event(line),
                    progress=self.parse_progress(line),
                )
            )
        return records

    def parse_metrics(self, line: str) -> TrainingMetrics | None:
        # Native OpenPI format from module/openpi/scripts/train.py:
        # Step 100: loss=0.0123, grad_norm=0.4, param_norm=12.5
        match = STEP_RE.search(line)
        if match:
            step = int(match.group(1))
            self._last_metric_step = step
            values = {
                key: float(value)
                for key, value in VALUE_RE.findall(match.group(2))
            }
            return TrainingMetrics(step=step, values=values)

        # Defensive support for dictionary-style metric logging if OpenPI
        # changes its logger later. Checkpoint event dictionaries do not contain
        # these metric keys, so they are not mistaken for loss samples.
        values = {
            key: float(value)
            for key, value in DICT_VALUE_RE.findall(line)
        }
        if not values:
            return None

        step_match = DICT_STEP_RE.search(line)
        if step_match:
            self._last_metric_step = int(step_match.group(1))
        return TrainingMetrics(step=self._last_metric_step, values=values)

    @staticmethod
    def parse_progress(line: str) -> TrainingProgress | None:
        match = PROGRESS_RE.search(line)
        if not match:
            return None

        current = match.group("current")
        if current == "-":
            return None

        def parse_scaled_number(value: str) -> float:
            value = value.strip().replace(",", "")
            number_match = re.fullmatch(
                r"(?P<number>\d+(?:\.\d+)?)(?P<suffix>[kKmMgGtTpPeE]?)",
                value,
            )
            if number_match is None:
                raise ValueError(f"Invalid progress value: {value!r}")

            suffix = number_match.group("suffix").lower()
            multiplier = {
                "": 1,
                "k": 1_000,
                "m": 1_000_000,
                "g": 1_000_000_000,
                "t": 1_000_000_000_000,
                "p": 1_000_000_000_000_000,
                "e": 1_000_000_000_000_000_000,
            }[suffix]
            return float(number_match.group("number")) * multiplier

        completed = max(0, int(round(parse_scaled_number(current))))
        total = max(
            1,
            int(round(parse_scaled_number(match.group("total")))),
        )
        completed = min(completed, total)
        return TrainingProgress(completed=completed, total=total)

    @staticmethod
    def parse_event(line: str) -> dict | None:
        prefix = "TRAINUI_EVENT="
        if prefix not in line:
            return None
        payload = line.split(prefix, 1)[1].strip()
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def should_show(line: str) -> bool:
        # The dedicated progress bar already represents tqdm progress. Hiding
        # these high-frequency lines keeps the text console useful while the
        # raw subprocess output is still preserved in logs/trainui/*.log.
        return PROGRESS_RE.search(line) is None
