"""Measure audio callback cost for representative synth configurations."""

import argparse
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import sleep
from types import SimpleNamespace
from typing import Optional

import numpy as np

from audio.engine import AudioEngine


SAMPLE_RATE = 44100
BUFFER_SIZE = 128


@dataclass(frozen=True)
class Scenario:
    name: str
    voices: int
    synthesis_mode: str = "waveform"
    unison: int = 1
    effects: bool = False
    recording: bool = False


SCENARIOS = (
    Scenario("waveform-1-voice", voices=1),
    Scenario("waveform-8-voices", voices=8),
    Scenario("unison-3", voices=8, unison=3),
    Scenario("unison-7", voices=8, unison=7),
    Scenario("additive-8-voices", voices=8, synthesis_mode="additive"),
    Scenario("fm-8-voices", voices=8, synthesis_mode="fm"),
    Scenario("all-effects-8v", voices=8, effects=True),
    Scenario("recording-8-voices", voices=8, recording=True),
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _measure(scenario: Scenario, iterations: int) -> dict[str, float]:
    engine = AudioEngine(
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        max_voices=32,
    )
    engine.mixer.set_synthesis_mode(scenario.synthesis_mode)
    engine.mixer.set_unison_parameters(
        scenario.unison,
        18.0 if scenario.unison > 1 else 0.0,
    )
    if scenario.effects:
        engine.mixer.set_delay(True, time_ms=250, feedback=0.3, mix=0.25)
        engine.mixer.set_chorus(True, rate_hz=0.8, depth_ms=6.0, mix=0.25)
        engine.mixer.set_reverb(True, decay_seconds=1.8, mix=0.3)

    for index in range(scenario.voices):
        engine.mixer.note_on(220.0 * 2 ** (index / 12), 0.25)

    output = np.zeros((BUFFER_SIZE, 1), dtype=np.float32)
    status = SimpleNamespace(output_underflow=False)
    warmup = min(128, max(32, iterations // 4))
    for _ in range(warmup):
        engine._audio_callback(output, BUFFER_SIZE, None, status)
    engine._reset_callback_metrics()

    recording_error: Optional[Exception] = None
    with TemporaryDirectory(prefix="musa-audio-benchmark-") as directory:
        if scenario.recording:
            recording_path = Path(directory) / "benchmark.wav"
            engine.start_recording(str(recording_path))

        for index in range(iterations):
            engine._audio_callback(output, BUFFER_SIZE, None, status)
            if scenario.recording and (index + 1) % 8 == 0:
                sleep(8 * BUFFER_SIZE / SAMPLE_RATE)

        metrics = engine.get_callback_performance()
        if scenario.recording:
            recording_error = engine.stop_recording()

    if recording_error is not None:
        raise RuntimeError(
            f"Recording benchmark failed: {recording_error}"
        ) from recording_error
    return metrics


def _run(scenario: Scenario, iterations: int, repeats: int) -> dict[str, float]:
    results = [_measure(scenario, iterations) for _ in range(repeats)]
    return {
        key: float(median(result[key] for result in results))
        for key in (
            "mean_ms",
            "p95_ms",
            "max_ms",
            "budget_ms",
            "p95_budget_percent",
            "deadline_misses",
        )
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=_positive_int, default=512)
    parser.add_argument("--repeats", type=_positive_int, default=3)
    args = parser.parse_args()

    print(
        f"44.1 kHz, {BUFFER_SIZE}-sample buffer, "
        f"{args.iterations} measured callbacks, median of {args.repeats} runs"
    )
    print(
        f"{'Scenario':<23} {'Mean ms':>9} {'P95 ms':>9} {'Max ms':>9} "
        f"{'Budget ms':>10} {'P95 %':>8} {'Misses':>8}"
    )
    for scenario in SCENARIOS:
        metrics = _run(scenario, args.iterations, args.repeats)
        print(
            f"{scenario.name:<23} "
            f"{metrics['mean_ms']:>9.3f} "
            f"{metrics['p95_ms']:>9.3f} "
            f"{metrics['max_ms']:>9.3f} "
            f"{metrics['budget_ms']:>10.3f} "
            f"{metrics['p95_budget_percent']:>7.0f}% "
            f"{metrics['deadline_misses']:>8.0f}"
        )
    print("Measurements omit audio-device scheduling and depend on host load.")


if __name__ == "__main__":
    main()
