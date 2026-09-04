# Ekonomski semafori: methodology

Version 2.0, September 2026. Faculty of Economics and Business, University of Zagreb (EFZG). Croatian version: metodologija.md.

## 1. What the clock shows

Each indicator is a dot on a two-axis chart, one frame per month. The vertical axis is the cycle: how far the indicator's trend-cycle component sits above or below its long-run trend. The horizontal axis is momentum: how much the cycle moved since the previous month. Both axes are standardised, so a value of 1 means one robust standard unit above the reference period.

The four quadrants are read in the growth-cycle sense of Mintz (1969): expansion (above trend and rising), slowdown (above trend and falling), contraction (below trend and falling), recovery (below trend and rising). Contraction therefore means below trend and slowing, not necessarily falling output. A dot moves clockwise through the quadrants over a typical cycle.

Croatia has 29 indicators, the other 20 countries have up to 26, depending on what Eurostat publishes for each. Each indicator carries a panel label: main for the coincident clock, confirmation for the lagging series, financial for the financial-cycle series, so that the charts can show them apart. The countries are the 19 euro area members other than Croatia plus Bulgaria.

## 2. Data

All series are taken at the longest history the source publishes. Eurostat series are fetched already seasonally and calendar adjusted (SCA) where such a version exists. The identifiers below are the dataset codes; the exact filters are in config/indicators.yaml.

| Category | Indicator (Croatian label) | Source and code | Frequency | Adjusted at source |
|---|---|---|---|---|
| Leading | Building permits (Građevinske dozvole) | Eurostat sts_cobp_q | quarterly | yes |
| Leading | Economic sentiment indicator (ESI) (Indeks ekonomskog raspoloženja) | Eurostat ei_bssi_m_r2 | monthly | yes |
| Leading | Consumer confidence (Pouzdanje potrošača) | Eurostat ei_bsco_m | monthly | yes |
| Leading | Industry order books (Knjige narudžbi u industriji) | Eurostat ei_bsin_m_r2 | monthly | yes |
| Leading | Euro area term spread (10Y minus 3M) (Kamatni raspon europodručja), same for all countries | ECB YC, monthly average of daily rates | monthly | not seasonal |
| Leading | Business registrations (Registracija novih poduzeća) | Eurostat sts_rb_m | monthly | yes |
| Leading | New passenger car registrations (DZS) (Novo registrirana osobna vozila), Croatia only | DZS, Excel input | monthly | no |
| Leading | New freight vehicle registrations (DZS) (Novo registrirana teretna vozila), Croatia only | DZS, Excel input | monthly | no |
| Supply | GDP (BDP), also under demand | Eurostat namq_10_gdp | quarterly | yes |
| Supply | Real gross value added (Realna bruto dodana vrijednost) | Eurostat namq_10_a10 | quarterly | yes |
| Supply | Capacity utilisation in industry (Iskorištenost kapaciteta u industriji), level | Eurostat ei_bsin_q_r2 | quarterly | yes |
| Supply | Industrial production (Industrijska proizvodnja) | Eurostat sts_inpr_m | monthly | yes |
| Supply | Construction (Građevinarstvo) | Eurostat sts_copr_m | monthly | yes |
| Supply | Total production (Ukupna proizvodnja) | Eurostat sts_tot_prod_m | monthly | yes |
| Supply | Overnight stays (Broj noćenja) | Eurostat tour_occ_nim | monthly | no |
| Supply | Insured persons (HZMO) (Broj osiguranika), Croatia only | HZMO, Excel input | monthly | no |
| Demand | Retail trade (Trgovina na malo) | Eurostat sts_trtu_m | monthly | yes |
| Demand | Wholesale trade (Veleprodaja) | Eurostat sts_trtu_m | monthly | yes |
| Demand | Household consumption (Potrošnja kućanstava) | Eurostat namq_10_fcs | quarterly | yes |
| Demand | Investment (Investicije) | Eurostat namq_10_an6 | quarterly | yes |
| External | Exports of goods (Izvoz dobara) | Eurostat bop_c6_m | monthly | no |
| External | Exports of services (Izvoz usluga) | Eurostat bop_c6_m | monthly | no |
| External | Imports of goods (Uvoz dobara) | Eurostat bop_c6_m | monthly | no |
| External | Imports of services (Uvoz usluga) | Eurostat bop_c6_m | monthly | no |
| Lagging | Bankruptcy declarations (Stečajne prijave), inverted | Eurostat sts_rb_m | monthly | yes |
| Lagging | Unemployment (Nezaposlenost), inverted | Eurostat une_rt_m | monthly | yes |
| Lagging | Non-performing loans (ECB) (Neprihodonosni krediti), inverted | ECB CBD2 | quarterly | no |
| Financial | House price index (Indeks cijena stambenih nekretnina) | Eurostat prc_hpi_q | quarterly | no |
| Financial | Loans to non-financial corporations (ECB) (Krediti nefinancijskim poduzećima) | ECB BSI | monthly | no |

The Croatian Excel inputs are updated by hand each month from the DZS table of first-time registered road vehicles and the HZMO monthly count of insured persons; data/README.md gives the procedure. The OVI business confidence index (EIZ) was dropped in September 2026 because it is no longer published.

Series arrive with different delays. Production and unemployment are available about one month after the reference month, balance of payments and national accounts about three months, NPL ratios longer. A frame for a given month therefore mixes series ending in different months; each dot shows the latest month its series has.

## 3. Processing

The steps below run for every (country, indicator) pair. Parameters are in config/settings.yaml; the code is in src/ekonomski_semafori.

Contiguity. Gaps of up to three periods inside a series are filled by linear interpolation. A longer gap cuts the history to the segment after it. A series whose last observation is more than 24 months old is skipped.

Quarterly to monthly. Quarterly series (GDP, consumption, investment, permits, NPL) are converted to months with the Denton-Cholette method and a constant indicator, so that the three months of a quarter average to the quarterly value and the monthly path is as smooth as possible (Denton 1971; with a constant indicator this is the Boot, Feibes and Lisman 1967 smoother). No related monthly indicator is used. The monthly path carries no information beyond the quarterly figures: within-quarter movements are interpolated, and the months after the last published quarter are extrapolated until the next quarter arrives.

Seasonal adjustment. Series that Eurostat does not publish adjusted (overnight stays, balance of payments flows, NPL, the Croatian Excel inputs) are adjusted with X-13ARIMA-SEATS (Census Bureau, version 1.1 build 60): additive outliers only with a critical value of 4.0, no automatic trading-day or Easter regressors, SEATS decomposition. Adjustment runs on levels. Series shorter than 36 months are used unadjusted.

Models. The transformation is set by series type: multiplicative (log) for growth series, additive for balances and spreads. An additive adjustment of a series that collapsed to near zero, as tourism did in 2020, produces negative adjusted values, which is why the choice is not left to the fit. The ARIMA orders, the constant term, the trading-day and Easter regressors and the outlier set for every series and step are identified once by X-13's automatic procedure and frozen in config/x13_models.yaml, together with the estimated coefficients, which the monthly run uses as starting values. The monthly run re-estimates the parameters with the model fixed and looks for new outliers only in the last twelve months, so month-to-month changes in the adjusted series and in the trend come from data, not from a different model being picked. The models are re-identified at an annual review and any change is recorded in the changelog. A series without a frozen model, or whose frozen model fails to estimate, falls back to automatic selection with a warning in the log.

Short-run trend. The X-11 Henderson trend-cycle (table D12) of the adjusted series. It removes the irregular component and keeps movements of a year or longer.

Long-run trend. For growth series (the ratio transform), the Hodrick-Prescott filter with lambda 129,600 applied to 100 times the natural logarithm of the adjusted series. The value follows Ravn and Uhlig (2002), who scale the quarterly 1,600 by the fourth power of the frequency ratio. At this lambda the trend absorbs movements of roughly ten years and longer. The survey indicators (economic sentiment, consumer confidence, order books) are stationary by construction, so their long-run trend is their mean over the reference window; the term spread is used as it is, because its level, not its deviation from a trend, carries the signal. These four use the difference transform. The term spread is the same euro area series for every country and skips the Henderson step.

Cycle. For growth series, 100 (ln D12 minus HP trend), the percentage gap between the trend-cycle and the long-run trend. For difference series, D12 minus the long-run trend in the series' own units.

Momentum. The change in the cycle from the previous month. It is positive when the indicator is gaining on its long-run trend, whatever the trend's own growth rate.

Sign. Unemployment, bankruptcies and non-performing loans are multiplied by minus one, so that up always means better.

Standardisation. Every observation is standardised with a location and a scale estimated on the reference window, which starts in January 2010 and is the same for every indicator and country. The location is the median and the scale is 1.4826 times the median absolute deviation, so the 2020 collapse does not compress the rest of the history. An indicator with fewer than 84 observations in the window is not published. The parameters are frozen once a year so that earlier frames do not move between releases. Published values are clipped at plus or minus 3 and flagged; the archived vintages keep the unclipped values.

Output. Files start in February 2015 for the animation, although every filter uses the full history. Each release is archived so that revisions can be measured.

## 4. What the numbers cannot tell you

The last months of every dot are provisional. The Henderson filter uses asymmetric weights for the last six months and the HP trend is effectively one-sided at the sample end, so both coordinates of the newest dot are revised for a year or more as data arrive. On GDP and industrial production for Croatia, Germany and the euro area, the cycle of the last two years moves by 0.1 to 0.8 points between its first publication and its full-sample value, against a cycle standard deviation of 2 to 4 points (docs/trend_method_comparison.md). One-sided filters would remove these revisions but place turning points three to six months later, so the two-sided HP is kept. Revision statistics from the archived releases will be published after a year.

A long recession is partly absorbed into the trend. Croatia's decline from 2009 to 2014 lasted long enough for the HP filter to treat much of it as trend, so the cycle axis understates that period; the 2009 trough measures 2 to 3 points for GDP where a one-sided filter shows 8 to 14.

Quarterly-origin dots move smoothly by construction. Their monthly momentum is interpolated and their newest months are extrapolated.

Between annual reviews the X-13 models are fixed. In testing with automatic selection every month, two model candidates with almost equal fit could flip on rounding differences and move the trend of a series by several percent; freezing removes that source of revision but not the end-point revisions above.

The financial-cycle series (house prices, loans) have cycles of fifteen to twenty years that the HP trend partly absorbs; they are shown on their own panel and their quadrant reading is not the business-cycle one.

The lagging series are slow and partly administrative. Bankruptcy filings depend on insolvency law and, in 2020 and 2021, on moratoria; NPL ratios fell through supervisory clean-ups; both lag the cycle by a year or more. Read them as confirmation of earlier turns.

Cycles are measured relative to each series' own history since 2010, so a dot at plus 1 means unusually high for that series, not high in any absolute sense. Sample lengths differ: some series start in the 1990s, others in 2010 or later.

## 5. Reproducibility

The pipeline is Python 3.12 (environment.yml). The R scripts that produced the earlier releases are kept in legacy/ and their output on 4 September 2026 is stored under tests/fixtures/; the Python code reproduces it to the rounding of the published files when run in the legacy configuration (git tag parity-r). Every published number can be regenerated from the configuration files and the archived data vintage.

## 6. Planned changes

Inflation as a further indicator, once the schema has a year-on-year transformation; a separate panel for lagging and financial-cycle series; a comparison with the Eurostat business cycle clock chronology once that chronology is obtained.

## References

Boot, J. C. G., Feibes, W., and Lisman, J. H. C. (1967). Further methods of derivation of quarterly figures from annual data. Applied Statistics, 16(1), 65-75.

Denton, F. T. (1971). Adjustment of monthly or quarterly series to annual totals: an approach based on quadratic minimization. Journal of the American Statistical Association, 66(333), 99-102.

Hodrick, R. J., and Prescott, E. C. (1997). Postwar U.S. business cycles: an empirical investigation. Journal of Money, Credit and Banking, 29(1), 1-16.

Mintz, I. (1969). Dating postwar business cycles: methods and their application to Western Germany, 1950-67. National Bureau of Economic Research.

Ravn, M. O., and Uhlig, H. (2002). On adjusting the Hodrick-Prescott filter for the frequency of observations. Review of Economics and Statistics, 84(2), 371-376.

U.S. Census Bureau (2017). X-13ARIMA-SEATS reference manual, version 1.1.
