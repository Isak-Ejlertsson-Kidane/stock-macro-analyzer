import math
import os
import sys
import time

import pandas as pd
import requests
from tabulate import tabulate

CACHE_DIR = "cache"
INFLATION_CODE = "FP.CPI.TOTL.ZG"

# code, label, is_level (levels must be differenced before comparing to returns)
INDICATORS = {
    "1": ("NY.GDP.MKTP.KD.ZG", "GDP growth", False),
    "2": (INFLATION_CODE, "Inflation", False),
    "3": ("SL.UEM.TOTL.ZS", "Unemployment", True),
}


def main():
    print("=" * 60)
    print("           STOCK & MACRO DATA ANALYZER")
    print("=" * 60)

    ticker = input("Stock ticker (e.g. AAPL, MSFT, ERIC-B.ST): ").strip().upper()
    if not ticker:
        sys.exit("No ticker provided")

    country = input("Country code (e.g. US, SE, DE, GB): ").strip().upper()
    if len(country) not in (2, 3) or not country.isalpha():
        sys.exit("Country code must be 2 or 3 letters")

    print("\nMacro indicators:")
    for key, (_, label, _) in INDICATORS.items():
        print(f"  {key}. {label}")
    choice = input("Choose indicator (1-3): ").strip()
    if choice not in INDICATORS:
        sys.exit("Invalid choice — must be 1, 2, or 3")
    code, label, is_level = INDICATORS[choice]

    start = get_year("Start year (e.g. 2005): ")
    end = get_year("End year (e.g. 2024): ")
    if end - start < 5:
        sys.exit("Use a range of at least 5 years — shorter ranges cannot be analysed")

    print(f"\nFetching stock prices for {ticker}...")
    nominal = fetch_stock_data(ticker, start, end)

    print(f"Fetching inflation for {country}...")
    inflation = select_years(fetch_macro_data(INFLATION_CODE, country), start, end)

    if code == INFLATION_CODE:
        macro = inflation.copy()
    else:
        print(f"Fetching {label.lower()} for {country}...")
        macro = select_years(fetch_macro_data(code, country), start, end)

    if is_level:
        macro = difference_series(macro)
        label = f"{label} change"

    real = real_returns(nominal, inflation)

    columns = {"Nominal (%)": nominal, "Real (%)": real, f"{label} (%)": macro}
    data = align_series(columns)
    if len(data) < 5:
        sys.exit(f"Only {len(data)} usable year(s) — try a wider year range")

    generate_report(ticker, country, label, data)


def get_year(prompt):
    """Prompt for a year and validate it is a plausible four-digit year."""
    value = input(prompt).strip()
    if not value.isdigit() or not (1900 <= int(value) <= 2100):
        sys.exit("Invalid year — enter a number such as 2015")
    return int(value)


def fetch_stock_data(ticker, start_year, end_year):
    """Return annual percentage returns, indexed by year. Partial years are dropped."""
    import yfinance as yf

    history = yf.Ticker(ticker).history(
        start=f"{start_year}-01-01", end=f"{end_year}-12-31", auto_adjust=True
    )
    if history.empty:
        sys.exit(f"No stock data found for '{ticker}' — check the ticker symbol")

    yearly_close = history["Close"].resample("YE").last()

    # An unfinished final year would be reported as a full-year return, so drop it.
    if history.index[-1].month < 12:
        yearly_close = yearly_close.iloc[:-1]

    returns = yearly_close.pct_change().dropna() * 100
    returns.index = returns.index.year
    if returns.empty:
        sys.exit(f"Not enough price history for '{ticker}' in that period")
    return returns


def fetch_macro_data(indicator, country, attempts=5):
    """Return the full annual history of one World Bank indicator, indexed by year.

    The API answers from several servers and some of them hang, so requests use a
    short timeout and are retried. Successful responses are cached on disk, which
    also lets the program run without a network connection.
    """
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
    params = {"format": "json", "date": "1960:2030", "per_page": 500}

    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            payload = response.json()
            series = parse_macro_payload(payload)
            write_cache(indicator, country, series)
            return series
        except (requests.RequestException, ValueError, KeyError):
            print(f"  Attempt {attempt} failed, retrying...")
            time.sleep(1)

    cached = read_cache(indicator, country)
    if cached is not None:
        print("  API unavailable — using cached data")
        return cached
    sys.exit(f"Could not reach the World Bank API and no cached data for {country}")


def parse_macro_payload(payload):
    """Turn the World Bank JSON response into a Series indexed by year."""
    if len(payload) < 2 or not payload[1]:
        raise ValueError("no data in response")
    values = {
        int(row["date"]): row["value"]
        for row in payload[1]
        if row["value"] is not None
    }
    if not values:
        raise ValueError("no usable values in response")
    return pd.Series(values).sort_index()


def cache_path(indicator, country):
    """Where the cached copy of one country/indicator pair lives."""
    return os.path.join(CACHE_DIR, f"{country}_{indicator}.csv")


def write_cache(indicator, country, series):
    """Save a fetched series so the program still works when the API is down."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    series.rename("value").rename_axis("year").to_csv(cache_path(indicator, country))


def read_cache(indicator, country):
    """Load a previously cached series, or None if it was never fetched."""
    path = cache_path(indicator, country)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, index_col="year")["value"]


def select_years(series, start_year, end_year):
    """Keep only the years inside the requested range."""
    return series[(series.index >= start_year) & (series.index <= end_year)]


def difference_series(series):
    """Convert a level series into year-over-year change in percentage points."""
    return series.diff().dropna()


def real_returns(nominal, inflation):
    """Adjust nominal returns for inflation: (1 + r) / (1 + pi) - 1."""
    real = (1 + nominal / 100) / (1 + inflation / 100) - 1
    return (real * 100).dropna()


def align_series(columns):
    """Join annual series on their shared years, dropping incomplete rows."""
    combined = pd.DataFrame(columns).dropna()
    if combined.empty:
        sys.exit("No overlapping years between the stock and macro data")
    combined.index.name = "Year"
    return combined


def cagr(returns):
    """Compound annual growth rate from a list of annual percentage returns."""
    if len(returns) == 0:
        return 0.0
    growth = 1.0
    for value in returns:
        growth *= 1 + value / 100
    if growth <= 0:
        return -100.0
    return (growth ** (1 / len(returns)) - 1) * 100


def calculate_correlation(data, x_column, y_column):
    """Pearson correlation between two columns."""
    return round(data[x_column].corr(data[y_column]), 4)


def correlation_interval(r, n):
    """95% confidence interval for r using the Fisher z-transformation."""
    if n < 4 or abs(r) >= 1:
        return (-1.0, 1.0)
    z = math.atanh(r)
    margin = 1.96 / math.sqrt(n - 3)
    return (round(math.tanh(z - margin), 4), round(math.tanh(z + margin), 4))


def describe_correlation(r, low, high, n):
    """Describe a correlation honestly, including when it means nothing."""
    if low <= 0 <= high:
        return f"cannot be distinguished from zero (n = {n})"
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    direction = "positive" if r > 0 else "negative"
    return f"{strength} {direction} (n = {n})"


def most_influential_year(data, x_column, y_column):
    """Leave-one-out: find the year whose removal moves the correlation most."""
    baseline = calculate_correlation(data, x_column, y_column)
    worst_year, worst_value, largest_shift = None, baseline, 0.0

    for year in data.index:
        reduced = data.drop(index=year)
        shifted = calculate_correlation(reduced, x_column, y_column)
        if abs(shifted - baseline) > largest_shift:
            largest_shift = abs(shifted - baseline)
            worst_year, worst_value = year, shifted

    return worst_year, worst_value, round(largest_shift, 4)


def generate_report(ticker, country, label, data):
    """Print a formatted summary of the analysis."""
    nominal_col, real_col, macro_col = data.columns
    n = len(data)

    r = calculate_correlation(data, nominal_col, macro_col)
    low, high = correlation_interval(r, n)
    verdict = describe_correlation(r, low, high, n)
    year, shifted_r, shift = most_influential_year(data, nominal_col, macro_col)

    print("\n" + "=" * 60)
    print(f"  {ticker}  vs  {label}  —  {country}")
    print(f"  Period {data.index.min()}–{data.index.max()}   ({n} years)")
    print("=" * 60)

    print("\n  PERFORMANCE")
    print(f"    Nominal CAGR              {cagr(data[nominal_col]):+8.2f} %")
    print(f"    Real CAGR                 {cagr(data[real_col]):+8.2f} %")
    print(f"    Mean annual return        {data[nominal_col].mean():+8.2f} %"
          "   (arithmetic — overstates)")
    print(f"    Volatility                {data[nominal_col].std():8.2f} %")

    print(f"\n  RELATIONSHIP TO {label.upper()}")
    print(f"    Correlation               {r:+8.4f}")
    print(f"    95% confidence interval   [{low:+.4f}, {high:+.4f}]")
    print(f"    Verdict                   {verdict}")

    print("\n  ROBUSTNESS")
    print(f"    Most influential year     {year}")
    print(f"    Correlation without it    {shifted_r:+8.4f}   (moves {shift:.4f})")

    print("\n" + tabulate(data.round(2), headers="keys", tablefmt="grid",
                          floatfmt="+.2f"))
    print("\n  Correlation does not imply causation.\n")


if __name__ == "__main__":
    main()
