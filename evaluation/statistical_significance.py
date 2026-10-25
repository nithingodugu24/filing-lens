import random
import statistics


def paired_bootstrap(first, second, iterations=5000, seed=42):
    if len(first) != len(second) or not first:
        raise ValueError("Paired samples must be nonempty and have equal length")
    differences = [b - a for a, b in zip(first, second, strict=True)]
    rng = random.Random(seed)
    samples = sorted(
        statistics.mean(rng.choices(differences, k=len(differences)))
        for _ in range(iterations)
    )
    observed = statistics.mean(differences)
    # Center the paired differences to simulate the null, not a sign test on uncentered resamples.
    centered = [x - observed for x in differences]
    null = [
        statistics.mean(rng.choices(centered, k=len(centered)))
        for _ in range(iterations)
    ]
    return {
        "mean_difference": observed,
        "confidence_interval_95": [
            samples[int(iterations * 0.025)],
            samples[min(iterations - 1, int(iterations * 0.975))],
        ],
        "p_value_two_sided": (1 + sum(abs(x) >= abs(observed) for x in null))
        / (iterations + 1),
        "pairs": len(first),
        "iterations": iterations,
        "seed": seed,
    }
