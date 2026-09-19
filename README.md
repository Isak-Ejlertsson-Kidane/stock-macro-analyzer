# Stock & Macro Data Analyzer

A command-line tool that tests whether a listed company's returns actually move with
the economy around it — and says so plainly when they don't.

You give it a ticker, a country, a macroeconomic indicator and a range of years. It
fetches daily share prices from Yahoo Finance and annual figures from the World Bank,
converts prices into annual returns, aligns the two series on the years they share,
and prints a report: performance, the correlation with a confidence interval, and a
robustness check that names the single year doing the most work.

## Example

```
============================================================
  AAPL  vs  GDP growth  —  US
  Period 2006–2024   (19 years)
============================================================

  PERFORMANCE
    Nominal CAGR                +28.45 %
    Real CAGR                   +25.29 %
    Mean annual return          +37.58 %   (arithmetic — overstates)
    Volatility                   49.94 %

  RELATIONSHIP TO GDP GROWTH
    Correlation                -0.3457
    95% confidence interval   [-0.6914, +0.1287]
    Verdict                   cannot be distinguished from zero (n = 19)

  ROBUSTNESS
    Most influential year     2009
    Correlation without it     -0.0476   (moves 0.2981)
```

A correlation of −0.35 looks like a finding. It isn't: with nineteen annual
observations the confidence interval still straddles zero, and dropping 2009 alone
collapses it to −0.05. The program is built to say that out loud rather than print a
number and let the reader over-read it.

## Running it

```bash
pip install -r requirements.txt
python project.py
```

Then answer the five prompts — ticker (`AAPL`, `ERIC-B.ST`), country code (`US`, `SE`),
indicator, start year, end year. A range of at least five years is required.

## How it works

The central difficulty is that the two data sources do not speak the same language.
Share prices arrive as thousands of daily observations; World Bank figures arrive once
per year. Reconciling them is most of the work. Prices are resampled to year-end closes
and turned into percentage changes, and an unfinished final year is discarded so that
eight months of trading is never reported as a full year's return. The macro series is
fetched in full and then sliced to the requested range. Finally the series are joined
on their shared years and any incomplete rows are dropped.

Every analytical function is pure: it takes data and returns a value, touching neither
the network nor the filesystem. That separation is what makes the tests possible. For
the same reason, `yfinance` is imported inside `fetch_stock_data` rather than at the top
of the file, so running the tests never loads a heavy library they don't use.

## Design choices

**A result is described honestly, or not at all.** An earlier version printed phrases
like "strong positive correlation" based on the size of *r* alone. That is indefensible:
with twenty annual observations, a correlation below roughly 0.44 cannot be
distinguished from zero, so such a label states something the data does not support.
The program computes a 95% confidence interval using the Fisher z-transformation, and
returns "cannot be distinguished from zero" whenever that interval contains zero.

**Leave-one-out, because one year can manufacture a pattern.** The correlation is
recomputed with each year removed in turn, and the year that moves it most is named.
Over a twenty-year window a single crisis year can invent an entire apparent
relationship; naming it lets the reader judge. If the correlation changes sign when one
year is dropped, there was never a pattern to begin with.

**Real returns are always available.** Inflation is fetched on every run regardless of
which indicator was chosen. It is the one figure that genuinely requires both data
sources, and unlike a correlation it is arithmetic rather than inference, so a small
sample cannot undermine it. Compound growth is reported beside the arithmetic mean,
which is explicitly labelled as overstating: +50% followed by −50% averages to zero but
leaves an investor down 25%.

**Levels are differenced before use.** GDP growth and inflation are already rates of
change, but unemployment is a persistent level, and correlating a trending level against
stationary returns invites a spurious relationship. The `INDICATORS` table flags which
indicators are levels.

**Failing fast beats waiting.** The World Bank API answers from several servers and some
hang indefinitely, so requests use an eight-second timeout with five retries rather than
one long attempt. Successful responses are cached to disk, so the program still runs when
the API is unavailable and repeat runs are instant.

## Files

| File | |
|---|---|
| `project.py` | `main` plus seventeen functions: fetching, caching, alignment, analysis, report |
| `test_project.py` | 16 tests covering all ten pure functions, expected values worked out by hand |
| `requirements.txt` | pandas, requests, tabulate, yfinance |
| `cache/` | created at runtime; one CSV per country and indicator |

## Tests

```bash
pip install pytest && python -m pytest
```

16 passed in 0.34s. Because the analysis is separated from input and output, no test
mocks an API or touches the network.

---

Built as the final project for [CS50P](https://cs50.harvard.edu/python/) (HarvardX).
Video demo: https://youtu.be/-9FiqCjInOU
