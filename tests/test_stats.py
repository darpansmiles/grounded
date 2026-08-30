from evals.stats import bootstrap_rate_ci, mcnemar_exact, run_variance


def test_fixed_bootstrap_and_exact_mcnemar_values_are_deterministic():
    assert bootstrap_rate_ci([True, True, True]) == {"rate": 1.0, "lo": 1.0, "hi": 1.0}
    assert bootstrap_rate_ci([False, False, False]) == {"rate": 0.0, "lo": 0.0, "hi": 0.0}
    assert mcnemar_exact([True, True, True], [False, False, False]) == {"b": 0, "c": 3, "p_value": 0.25}
    assert run_variance([0.0, 0.5, 1.0]) == 1 / 6
