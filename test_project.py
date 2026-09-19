import pandas as pd
from project import (
    align_series,
    cagr,
    calculate_correlation,
    correlation_interval,
    describe_correlation,
    difference_series,
    most_influential_year,
    parse_macro_payload,
    real_returns,
    select_years,
)


def test_difference_series_converts_level_to_change():
    levels = pd.Series({2020: 5.0, 2021: 6.5, 2022: 4.0})
    result = difference_series(levels)
    assert len(result) == 2
    assert result[2021] == 1.5
    assert result[2022] == -2.5


def test_real_returns_subtracts_inflation():
    nominal = pd.Series({2020: 10.0})
    inflation = pd.Series({2020: 5.0})
    # (1.10 / 1.05) - 1 = 4.7619 %
    assert round(real_returns(nominal, inflation)[2020], 4) == 4.7619


def test_real_returns_drops_years_without_inflation():
    nominal = pd.Series({2020: 10.0, 2021: 8.0})
    inflation = pd.Series({2020: 5.0})
    assert list(real_returns(nominal, inflation).index) == [2020]


def test_cagr_matches_mean_when_returns_are_equal():
    assert round(cagr([10.0, 10.0, 10.0]), 4) == 10.0


def test_cagr_is_lower_than_arithmetic_mean_when_volatile():
    returns = [50.0, -50.0]
    arithmetic = sum(returns) / len(returns)
    assert arithmetic == 0.0
    assert round(cagr(returns), 2) == -13.40


def test_align_series_keeps_only_shared_years():
    columns = {
        "Nominal (%)": pd.Series({2020: 10.0, 2021: 5.0}),
        "GDP growth (%)": pd.Series({2021: 3.1, 2022: 4.0}),
    }
    result = align_series(columns)
    assert len(result) == 1
    assert 2021 in result.index


def test_select_years_keeps_only_the_range():
    series = pd.Series({2018: 1.0, 2019: 2.0, 2020: 3.0, 2021: 4.0})
    result = select_years(series, 2019, 2020)
    assert list(result.index) == [2019, 2020]


def test_parse_macro_payload_skips_missing_values():
    payload = [
        {"page": 1},
        [
            {"date": "2020", "value": 2.5},
            {"date": "2021", "value": None},
            {"date": "2022", "value": 4.0},
        ],
    ]
    result = parse_macro_payload(payload)
    assert list(result.index) == [2020, 2022]
    assert result[2022] == 4.0


def test_calculate_correlation_perfect_positive():
    data = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 2.0, 3.0, 4.0]})
    assert calculate_correlation(data, "a", "b") == 1.0


def test_calculate_correlation_perfect_negative():
    data = pd.DataFrame({"a": [4.0, 3.0, 2.0, 1.0], "b": [1.0, 2.0, 3.0, 4.0]})
    assert calculate_correlation(data, "a", "b") == -1.0


def test_correlation_interval_brackets_the_estimate():
    low, high = correlation_interval(0.5, 20)
    assert low < 0.5 < high
    assert -1.0 <= low and high <= 1.0


def test_correlation_interval_narrows_as_sample_grows():
    small_low, small_high = correlation_interval(0.5, 10)
    large_low, large_high = correlation_interval(0.5, 200)
    assert (large_high - large_low) < (small_high - small_low)


def test_correlation_interval_handles_tiny_sample():
    assert correlation_interval(0.9, 3) == (-1.0, 1.0)


def test_describe_correlation_admits_uncertainty():
    assert describe_correlation(0.35, -0.12, 0.69, 20) == \
        "cannot be distinguished from zero (n = 20)"


def test_describe_correlation_reports_strength_when_certain():
    assert describe_correlation(0.85, 0.61, 0.95, 40) == "strong positive (n = 40)"
    assert describe_correlation(-0.45, -0.68, -0.14, 40) == "moderate negative (n = 40)"
    assert describe_correlation(0.20, 0.02, 0.37, 120) == "weak positive (n = 120)"


def test_most_influential_year_finds_the_outlier():
    data = pd.DataFrame(
        {"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [1.0, 2.0, 3.0, 4.0, -50.0]},
        index=[2019, 2020, 2021, 2022, 2023],
    )
    year, shifted, shift = most_influential_year(data, "a", "b")
    assert year == 2023
    assert shifted == 1.0
    assert shift > 1.0
