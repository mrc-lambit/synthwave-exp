"""Measure audio callback cost across legacy and newer synthesis workloads."""

import argparse
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from types import SimpleNamespace

import numpy as np

from audio.engine import AudioEngine


SAMPLE_RATE = 44100
BUFFER_SIZE = 128

SCENARIOS = (
    {
        "name": "waveform-1v-unison1-fx-off",
        "mode": "waveform",
        "voices": 1,
        "unison": 1,
        "effects": False,
    },
    {
        "name": "waveform-8v-unison1-fx-off",
        "mode": "waveform",
        "voices": 8,
        "unison": 1,
        "effects": False,
    },
    {
        "name": "waveform-8v-unison3-fx-off",
        "mode": "waveform",
        "voices": 8,
        "unison": 3,
        "effects": False,
    },
    {
        "name": "waveform-8v-unison7-fx-off",
        "mode": "waveform",
        "voices": 8,
        "unison": 7,
        "effects": False,
    },
    {
        "name": "additive-8v-unison1-fx-off",
        "mode": "additive",
        "voices": 8,
        "unison": 1,
        "effects": False,
    },
    {
        "name": "fm-8v-unison1-fx-off",
        "mode": "fm",
        "voices": 8,
        "unison": 1,
        "effects": False,
    },
    {
        "name": "waveform-8v-unison3-effects",
        "mode": "waveform",
        "voices": 8,
        "unison": 3,
        "effects": True,
    },
)


def measure_scenario(
    scenario: dict,
    recording: bool,
    warmup: int,
    iterations: int,
) -> tuple[float, float, float, int]:
    engine = AudioEngine(
        sample_rate=SAMPLE_RATE,
        buffer_size=BUFFER_SIZE,
        max_voices=scenario["voices"],
    )
    mixer = engine.mixer
    mixer.set_oscillator_type("triangle")
    mixer.set_synthesis_mode(scenario["mode"])
    mixer.set_synthesis_parameters(additive_partials=8)
    mixer.set_unison_parameters(scenario["unison"], detune_cents=12.0)
    mixer.set_adsr_parameters(0.002, 0.2, 0.7, 0.1)
    mixer.set_filter("lowpass", 1800.0, 0.0)

    if scenario["effects"]:
        mixer.set_distortion("soft_clip", drive=0.05, mix=0.2)
        mixer.set_delay(True, time_ms=320, feedback=0.25, mix=0.2)
        mixer.set_reverb(True, decay_seconds=3.2, mix=0.4)
    else:
        mixer.set_distortion("off", drive=0.0, mix=0.0)

    for index in range(scenario["voices"]):
        frequency = 220.0 * 2.0 ** (index / 12.0)
        mixer.note_on(frequency, amplitude=0.5)

    output = np.zeros((BUFFER_SIZE, 1), dtype=np.float32)
    status = SimpleNamespace(output_underflow=False)

    def callback() -> int:
        started = perf_counter_ns()
        engine._audio_callback(output, BUFFER_SIZE, None, status)
        return perf_counter_ns() - started

    recording_directory = None
    try:
        if recording:
            recording_directory = TemporaryDirectory()
            engine.start_recording(
                str(Path(recording_directory.name) / "baseline.wav")
            )

        for _ in range(warmup):
            callback()

        durations = sorted(callback() for _ in range(iterations))
        p95 = durations[max(0, int(np.ceil(0.95 * len(durations))) - 1)]
        budget_ns = BUFFER_SIZE * 1_000_000_000 // SAMPLE_RATE
        misses = sum(duration > budget_ns for duration in durations)
        return (
            mean(durations) / 1_000_000,
            p95 / 1_000_000,
            durations[-1] / 1_000_000,
            misses,
        )
    finally:
        engine.stop_recording()
        if recording_directory is not None:
            recording_directory.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup", type=int, default=32)
    parser.add_argument("--iterations", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.warmup < 0 or args.iterations < 1 or args.repeats < 1:
        parser.error(
            "--warmup must be >= 0; --iterations and --repeats must be >= 1"
        )

    budget_ms = BUFFER_SIZE * 1000 / SAMPLE_RATE
    print(
        f"sample_rate={SAMPLE_RATE}Hz buffer={BUFFER_SIZE} frames "
        f"budget={budget_ms:.3f}ms iterations={args.iterations} "
        f"repeats={args.repeats} (median of runs)",
        flush=True,
    )
    print(
        "scenario | recording | mean_ms | p95_ms | max_ms | "
        "deadline_misses"
    )
    for scenario in SCENARIOS:
        for recording in (False, True):
            runs = [
                measure_scenario(
                    scenario,
                    recording,
                    args.warmup,
                    args.iterations,
                )
                for _ in range(args.repeats)
            ]
            mean_ms, p95_ms, max_ms, misses = (
                median(run[index] for run in runs)
                for index in range(4)
            )
            print(
                f"{scenario['name']} | {'on' if recording else 'off'} | "
                f"{mean_ms:.3f} | {p95_ms:.3f} | {max_ms:.3f} | "
                f"{int(misses)}/{args.iterations}",
                flush=True,
            )


if __name__ == "__main__":
    main()
