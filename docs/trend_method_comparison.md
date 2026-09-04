# Long-run trend methods compared

Date: 2026-09-04. Script: notebooks/trend_comparison.py; results: notebooks/trend_comparison_results.csv; charts: notebooks/figures/. Series: GDP and industrial production for Croatia, Germany and the euro area (EA20), full available history, seasonally adjusted and Henderson-smoothed exactly as in the monthly run. Cycle = 100 ln D12 minus the long-run trend of 100 ln SA.

## Methods

Two-sided HP (lambda 129,600, the published method); one-sided HP (the two-sided filter refitted every month and only its last value kept, so it never revises); Baxter-King and Christiano-Fitzgerald low-pass trends (the series minus its 2 to 96 month band; Baxter-King has no estimate for the last 36 months); the Hamilton regression filter (h = 24, p = 12); and the smoothed level of an unobserved-components model with a local linear trend and a damped cycle.

## Metrics

Revision: for each of the last 24 months, the cycle at that month as it would have been published then (sample ending there) against its value on the full sample; mean absolute difference in percentage points. Turning points: local extrema over a 13-month window; count, and mean absolute shift in months from the two-sided HP turning points (the Eurostat BCC chronology could not be verified during the review and is not used). Depth: the 2020 trough relative to the 2009 trough.

## Results

Mean over the six series:

| Method | Revision of the last 24 months (pp) | Peak shift vs HP (months) | Trough shift vs HP (months) | Turning points per series |
|---|---|---|---|---|
| HP two-sided | 0.39 | 0 | 0 | 15 |
| HP one-sided | 0 by construction | 4.6 | 1.7 | 13 |
| Baxter-King | undefined for the last 36 months | 0.6 | 1.0 | 13 |
| Christiano-Fitzgerald | 0.48 | 1.6 | 1.1 | 15 |
| Hamilton | 0.28 | 4.5 | 4.0 | 14 |
| UCM level | 0.21 | 6.5 | 6.2 | 30 |

Per series, the two-sided HP revises the last two years by 0.11 (German GDP) to 0.83 points (Croatian GDP), against a cycle standard deviation of 2 to 4 points. Christiano-Fitzgerald revises as much or more (1.6 points for Croatian industrial production). Hamilton's revisions come only from re-estimated coefficients but its turning points sit 3 to 6 months away from the HP ones, and the one-sided HP has the same displacement at peaks. The unobserved-components level produces twice as many turning points and a 2020 trough of only 2 to 3 points for GDP: it treats the pandemic as a level shift, which is not what the clock should show.

The 2020 to 2009 depth ratio exposes a property of every two-sided filter on Croatian data: the depression of 2009 to 2014 is long enough to be absorbed into the trend, so its trough measures only 2 to 3 points for GDP under HP, Baxter-King and Christiano-Fitzgerald, against 8 to 14 points under the one-sided HP and Hamilton, which do not see the later years. For Germany and the euro area the 2009 industrial trough exceeds the 2020 one under every method.

## Recommendation

Keep the two-sided HP as the published long-run trend. It anchors the turning points that the other frequency-domain filters reproduce within a month, its revisions over the last two years are a tenth to a quarter of a cycle standard deviation, and it is defined up to the latest month. Mark the last twelve months as provisional on the charts and report the empirical revision distribution from the vintage archive after a year. Do not switch to the one-sided HP or the Hamilton filter for the clock: they trade revisions for turning points that arrive three to six months late and for a different amplitude scale. Baxter-King cannot serve a monthly product; Christiano-Fitzgerald brings no gain; the unobserved-components model is unsuitable as specified.

State in the methodology that a prolonged recession, such as Croatia's after 2008, is partly absorbed into the HP trend and therefore understated on the cycle axis. A longer lambda would deepen it at the price of larger revisions and a longer implied cycle; that trade-off is not resolved here.

The Eurostat BCC turning-point chronology should be obtained and added to the script so that metric (b) compares with an external reference rather than with the HP baseline.
