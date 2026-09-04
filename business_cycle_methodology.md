# Comprehensive Methodology for Business Cycle Analysis
## Multi-Country Animated Scatter Plot Visualization in Flourish Studio

---

## Executive Summary

This methodology describes a sophisticated econometric framework for decomposing macroeconomic time series into trend and cyclical components across multiple Euro Area countries. The analysis produces standardized cyclical indicators and momentum measures suitable for visualization as an animated scatter plot in Flourish Studio, where quadrants represent different stages of the business cycle (expansion, peak, contraction, recovery). The framework combines multiple statistical techniques—temporal disaggregation, seasonal adjustment, trend extraction, and cyclical decomposition—to transform raw economic data into interpretable business cycle indicators.

---

## 1. Data Collection and Sources

### 1.1 Data Sources

The analysis relies primarily on **Eurostat databases** as the authoritative source for harmonized macroeconomic statistics across European countries. Eurostat provides comprehensive, standardized economic indicators that enable cross-country comparisons while maintaining methodological consistency. For Croatia specifically, additional data sources include:

- **European Central Bank (ECB) Statistical Data Warehouse**: Non-performing loan ratios
- **Croatian Bureau of Statistics (DZS)**: Vehicle registration data
- **Croatian Pension Insurance Institute (HZMO)**: Insured persons data

### 1.2 Indicator Selection

The methodology incorporates **21 distinct macroeconomic indicators** for Croatia and **13-18 indicators** for other Euro Area countries (depending on data availability). These indicators are organized into five analytical categories:

**Leading Indicators** (anticipate future economic activity):
- Building permits for residential dwellings
- New business registrations
- First-time passenger vehicle registrations (Croatia only)
- First-time freight vehicle registrations (Croatia only)

**Supply/Production Indicators** (coincident with current economic activity):
- Gross Domestic Product (GDP) at constant prices
- Industrial production (sectors B-D)
- Construction production
- Total production excluding financial services
- Tourism overnight stays
- Number of insured persons (Croatia only)

**Demand/Consumption Indicators** (coincident with current economic activity):
- Retail trade volume
- Wholesale trade volume
- Household final consumption expenditure
- Gross fixed capital formation (investment)

**External Trade Indicators** (reflect international economic linkages):
- Exports of goods
- Exports of services
- Imports of goods
- Imports of services

**Lagging Indicators** (confirm economic trends after they occur):
- Bankruptcy declarations
- Unemployment (number of unemployed persons)
- Non-performing loan ratio (NPL)

### 1.3 Data Frequency and Time Coverage

The analysis covers data from **January 2015 onward**, providing approximately 10 years of business cycle history. This time span captures multiple economic phases including pre-COVID expansion, the 2020 pandemic shock, subsequent recovery, and recent inflationary pressures.

Data arrive at different frequencies:
- **Quarterly data**: GDP, household consumption, gross fixed capital formation, building permits, and NPL ratios
- **Monthly data**: All production indices, trade statistics, tourism, unemployment, registrations, and bankruptcies

This mixed-frequency structure necessitates temporal disaggregation techniques (described in Section 3) to create a unified monthly analytical framework.

### 1.4 Seasonal Adjustment Status

Most Eurostat data are accessed with **seasonal and calendar adjustment (SCA)** already applied by Eurostat's production systems. This means that regular seasonal patterns (Christmas shopping, summer tourism) and calendar effects (varying numbers of working days per month) have been removed by the data provider using X-13ARIMA-SEATS methodology.

However, two indicator categories require **additional seasonal adjustment** within the analytical pipeline:

1. **Tourism data** (overnight stays in accommodation establishments): Despite being labeled as seasonally adjusted by Eurostat, tourism data exhibit strong residual seasonal patterns due to the extreme amplitude of seasonal variation. The methodology applies custom X-13ARIMA-SEATS seasonal adjustment with conservative outlier detection.

2. **Balance of payments data** (exports and imports): These series are available only in non-seasonally adjusted form from Eurostat and therefore require full seasonal adjustment within the analytical framework.

The decision to re-adjust tourism data and apply seasonal adjustment to balance of payments data reflects the principle that seasonal adjustment should be tailored to each series' characteristics rather than accepting default adjustments that may be inadequate for series with extreme seasonal patterns.

---

## 2. Temporal Disaggregation: Denton-Cholette Method

### 2.1 The Quarterly-to-Monthly Conversion Problem

Four key macroeconomic indicators—GDP, household consumption, gross fixed capital formation, and building permits—are published only at quarterly frequency by Eurostat. To integrate these variables into a unified monthly business cycle analysis, they must be converted from quarterly to monthly observations through a process called **temporal disaggregation**.

Temporal disaggregation is fundamentally different from interpolation. Simple interpolation methods (linear, cubic spline) would create artificial monthly values that merely connect quarterly data points smoothly but contain no real information about within-quarter dynamics. In contrast, proper temporal disaggregation uses **related monthly indicator series** (called "indicators" or "related series") to distribute quarterly aggregates across the three months within each quarter in an economically meaningful way.

### 2.2 Why the Denton-Cholette Method?

The **Denton-Cholette** method was selected for temporal disaggregation based on several compelling theoretical and practical advantages:

**1. Movement Preservation**
The Denton-Cholette method prioritizes preserving the month-to-month movements of the related indicator series. When business cycles are characterized by turning points and momentum shifts, preserving these dynamics is more important than enforcing exact aggregate consistency in every period. The method allows for minor discrepancies between quarterly values and the sum of disaggregated monthly values to maintain realistic monthly patterns.

**2. Accounting Consistency Over Time**
While allowing period-by-period flexibility, Denton-Cholette ensures that cumulative discrepancies converge to zero over time. The sum of monthly values over the full sample period equals the sum of quarterly values, maintaining long-run accounting identity while permitting short-run flexibility.

**3. Smooth Corrections**
When adjustments are necessary to maintain consistency with quarterly aggregates, Denton-Cholette distributes these adjustments smoothly over time rather than creating abrupt breaks. This prevents artificial volatility in the monthly series that would distort cyclical analysis.

**4. Robustness to Data Revisions**
Eurostat quarterly national accounts data undergo regular revisions as source information improves. The Denton-Cholette method produces stable disaggregated monthly series that respond proportionally to quarterly revisions rather than exhibiting exaggerated month-to-month changes when quarterly data are revised.

### 2.3 Alternative Methods and Why They Were Rejected

**Chow-Lin Method**: The Chow-Lin procedure uses regression relationships between quarterly target series and monthly indicator series to perform disaggregation. This method was rejected because it requires strong assumptions about the stability of regression coefficients over time and can produce unrealistic monthly profiles when the relationship between the quarterly and monthly series changes, which is common during business cycle transitions.

**Boot-Feibes-Lisman Method**: This method uses proportional distribution but without considering indicator information. It was rejected because it ignores potentially valuable information contained in related monthly series, essentially performing a mechanical three-way split of each quarterly value.

**Fernández Method**: While mathematically elegant, the Fernández method enforces strict accounting constraints that can produce excessively volatile monthly series when quarterly data are subject to revisions or when within-quarter dynamics differ substantially from the smooth path implied by the quarterly aggregates.

### 2.4 Related Indicator Selection

For each quarterly series, an appropriate monthly related indicator is selected:

- **GDP** → Total production index (covers broad production sectors)
- **Household consumption** → Retail trade volume (direct measure of consumer purchases)
- **Gross fixed capital formation** → Construction production (captures significant investment activity)
- **Building permits** → Construction production (reflects building activity related to permit issuance)

These indicator relationships are economically motivated: the monthly series should exhibit a plausible causal or timing relationship with the quarterly target variable.

### 2.5 Implementation Details

The disaggregation is implemented using the **tempdisagg** package in R, which provides robust implementations of the Denton-Cholette method. The method is specified as follows:

```r
td(quarterly_series ~ 1, 
   to = "monthly", 
   method = "denton-cholette", 
   conversion = "average")
```

The `conversion = "average"` parameter specifies that the quarterly values represent flow variables whose quarterly total equals the average of the three monthly values multiplied by three (stock variables would use different conversion rules).

The disaggregation produces monthly series that:
1. Exhibit monthly patterns informed by the related indicator
2. Aggregate back to quarterly values with minimal cumulative discrepancy
3. Maintain smooth profiles without artificial breaks
4. Preserve the economic meaning of within-quarter dynamics

---

## 3. Seasonal Adjustment: X-13ARIMA-SEATS

### 3.1 Purpose and Scope of Seasonal Adjustment

Even when data are obtained with seasonal adjustment already applied by Eurostat, certain series require additional or alternative seasonal adjustment within the analytical framework. The X-13ARIMA-SEATS procedure, developed by the U.S. Census Bureau, represents the international standard for seasonal adjustment of economic time series.

### 3.2 Series Requiring Seasonal Adjustment

**Tourism Data (overnight stays)**: Croatia's tourism sector exhibits extreme seasonality with summer months (June-September) accounting for 70-80% of annual overnight stays. While Eurostat applies seasonal adjustment, the standard settings sometimes leave residual seasonal patterns that could distort business cycle analysis. The methodology applies custom X-13ARIMA-SEATS adjustment to fully eliminate these patterns.

**Balance of Payments (exports and imports)**: These series are available only in non-seasonally adjusted form and require full seasonal adjustment before inclusion in the business cycle framework.

### 3.3 Conservative Outlier Detection Settings

The X-13ARIMA-SEATS procedure includes automatic outlier detection to identify and adjust for unusual observations that do not represent regular seasonal or cyclical patterns. However, aggressive outlier detection can be counterproductive for business cycle analysis because genuine economic shocks (recessions, policy changes, external crises) may be incorrectly classified as outliers and adjusted away, eliminating the very cyclical variation the analysis seeks to measure.

To prevent this problem, the methodology employs **conservative outlier detection settings**:

```r
seas(series_ts,
     outlier.types = "AO",          # Only additive outliers
     outlier.critical = 4.0,         # Higher critical value (default is 3.0)
     regression.aictest = NULL)      # Disable automatic trading day/Easter tests
```

**Outlier Type Selection** (`outlier.types = "AO"`): The methodology detects only **additive outliers** (AO), which represent one-time spikes or dips that affect a single observation without changing the underlying level or pattern of the series. The alternative—level shifts (LS) and temporary changes (TC)—are excluded because genuine business cycle turning points often appear similar to level shifts, and their automatic detection would risk removing real cyclical variation.

**Critical Value Adjustment** (`outlier.critical = 4.0`): The critical value determines how extreme an observation must be to qualify as an outlier. The default value of 3.0 (standard deviations from expected) is appropriate for quality control but too aggressive for cyclical analysis. By raising the threshold to 4.0, the procedure only flags truly exceptional observations, preserving legitimate economic volatility.

**Trading Day Specification** (`regression.aictest = NULL`): Automatic testing for trading day and Easter effects is disabled because these adjustments have already been applied by Eurostat in the source data. Re-testing could lead to over-adjustment and removal of genuine within-month variation.

### 3.4 Fallback Strategy

The seasonal adjustment implementation includes a hierarchical fallback strategy to ensure all series receive some form of adjustment even when X-13ARIMA-SEATS encounters data irregularities:

1. **First attempt**: Standard X-13ARIMA-SEATS with conservative settings
2. **Second attempt**: Simpler ARIMA model specification if automatic model selection fails
3. **Third attempt**: Fixed random walk model without automatic procedures
4. **Final fallback**: If all parametric methods fail, apply a simple 12-month centered moving average

This strategy reflects the principle that approximate adjustment is preferable to no adjustment, even if sophisticated methods fail for certain problematic series.

---

## 4. Trend-Cycle Extraction: Henderson Filter (X-11 Decomposition)

### 4.1 The X-11 Decomposition Framework

After seasonal adjustment, the methodology applies **X-11 decomposition** to extract the trend-cycle component from each monthly series. X-11, developed by the U.S. Census Bureau in the 1960s and continuously refined since, remains the international standard for decomposing economic time series into their constituent components.

The classical decomposition assumes each time series can be expressed as:

**Observed = Trend-Cycle × Seasonal × Irregular** (multiplicative model)

or

**Observed = Trend-Cycle + Seasonal + Irregular** (additive model)

For economic variables measured as indices or volumes, the multiplicative model is typically more appropriate because cyclical and seasonal variations tend to scale with the level of the series.

### 4.2 The Henderson Filter

Within the X-11 framework, the **Henderson filter** performs the extraction of the trend-cycle component (designated **D12** in X-11 terminology). The Henderson filter is a **symmetric moving average filter** specifically designed for economic time series. Unlike simple moving averages that give equal weight to all observations in the window, the Henderson filter applies **declining weights** to observations further from the center, producing a smoother trend estimate that responds more gradually to changes in the data.

### 4.3 Why the Henderson Filter?

**Optimal for Economic Data**: The Henderson filter was designed specifically for economic time series based on extensive empirical research by Robert Henderson in the 1910s-1920s. Its weight structure minimizes the revision of trend estimates when new data arrive, a critical property for real-time economic monitoring.

**Preserves Turning Points**: Unlike some aggressive smoothing methods (e.g., polynomial trends, spline smoothing), the Henderson filter is sensitive enough to detect business cycle turning points without excessive lag. This responsiveness is essential for identifying when the economy transitions from expansion to contraction or vice versa.

**Controls Irregular Fluctuations**: The filter effectively reduces high-frequency noise and irregular movements (outliers, measurement errors, one-off events) while preserving medium-frequency cyclical oscillations that characterize business cycles.

**Finite Sample Properties**: The Henderson filter performs well even with relatively short time series (the methodology requires minimum 24 observations), unlike some asymptotic methods that need decades of data to produce stable estimates.

### 4.4 The D12 Component and Its Meaning

The output of the X-11 Henderson filter is the **D12 series**, representing the combined trend-cycle component. This component captures two distinct but related phenomena:

1. **Long-term structural trend**: Gradual changes in economic capacity, productivity, population, and technology that evolve over years or decades
2. **Business cycle fluctuations**: Medium-term oscillations around the trend reflecting expansions and contractions over months to years

Importantly, the D12 component has already had **seasonality, irregular fluctuations, and calendar effects removed** through earlier stages of the X-11 decomposition process. This means the D12 series is much smoother than the original data but still contains all the meaningful trend and cyclical variation.

### 4.5 Fallback Strategy for Problematic Series

The X-11 decomposition requires regular data patterns and sufficient observations to identify seasonal factors and trends. Some series may violate these requirements due to:
- Insufficient data length
- Structural breaks or regime changes
- Extreme volatility that defeats automatic model selection
- Irregular sampling or missing observations

To handle such cases, the methodology implements a hierarchical fallback approach:

**Attempt 1**: Standard X-11 with automatic ARIMA model selection
```r
seas(ts_data, x11 = "")
```

**Attempt 2**: X-11 with simplified ARIMA specification
```r
seas(ts_data, x11 = "", 
     arima.model = "(0 1 1)(0 1 1)",
     regression.aictest = NULL)
```

**Attempt 3**: X-11 with basic random walk model
```r
seas(ts_data, x11 = "",
     arima.model = "(0 1 0)(0 1 0)",
     automdl = NULL,
     outlier = NULL)
```

**Attempt 4**: Simple 12-month centered moving average
```r
rollapply(ts_data, width = 12, FUN = mean, 
          align = "center", fill = NA)
```

This progressive simplification ensures every series receives some form of trend-cycle extraction, maintaining the comprehensiveness of the business cycle indicator set even when individual series present challenges.

### 4.6 Alternative Methods Considered

**Band-Pass Filters (Baxter-King, Christiano-Fitzgerald)**: These frequency-domain filters isolate specific cycle frequencies (e.g., 2-8 years for business cycles) with mathematical precision. However, they were rejected because they discard substantial amounts of data at the beginning and end of the sample period (the filter must "look ahead" and "look back" symmetrically), resulting in loss of recent observations that are most policy-relevant.

**Unobserved Components Models**: State-space models that estimate trend and cycle as unobserved latent processes offer theoretical elegance but require strong parametric assumptions about the form of the trend (linear, random walk, local level with drift) and the cycle (specified ARMA process). The Henderson filter's non-parametric approach avoids these potentially restrictive assumptions.

**Polynomial Trends**: Fitting low-order polynomial functions (quadratic, cubic) to extract trends is computationally simple but often produces poor fits for economic data, particularly at the ends of the sample where polynomial functions can curve sharply away from recent observations.

---

## 5. Cyclical Decomposition: Hodrick-Prescott Filter

### 5.1 The Second Stage of Decomposition

After the Henderson filter extracts the trend-cycle component (D12), the methodology applies a second decomposition stage to separate the smooth **trend** from the **cyclical fluctuations** around that trend. This two-stage approach—Henderson first, then Hodrick-Prescott—provides superior cycle isolation compared to applying either method alone.

The **Hodrick-Prescott (HP) filter**, introduced by economists Robert Hodrick and Edward Prescott in 1997, has become one of the most widely used tools in macroeconomic analysis for trend-cycle decomposition. The filter represents the standard approach in academic research, central bank analysis, and international organization (OECD, IMF) economic surveillance.

### 5.2 Mathematical Foundation of the HP Filter

The HP filter solves an optimization problem that balances two competing objectives:

**Objective 1 - Trend should fit the data**: Minimize the sum of squared deviations between the observed series (y) and the trend (τ):

Σ(yₜ - τₜ)²

**Objective 2 - Trend should be smooth**: Minimize the sum of squared second differences of the trend (penalizing changes in the growth rate):

Σ[(τₜ₊₁ - τₜ) - (τₜ - τₜ₋₁)]²

The filter finds the trend path that minimizes:

Σ(yₜ - τₜ)² + λ × Σ[(τₜ₊₁ - τₜ) - (τₜ - τₜ₋₁)]²

The parameter **λ (lambda)** controls the trade-off between these objectives. A higher lambda penalizes trend variation more heavily, producing a smoother trend and attributing more variation to the cyclical component. A lower lambda allows the trend to follow the data more closely, producing a variable trend and smaller cyclical deviations.

### 5.3 Lambda Calibration: The Ravn-Uhlig Rule

The methodology uses **λ = 129,600** for monthly data, which is not an arbitrary choice but derives from a mathematical relationship ensuring consistent smoothing across different data frequencies.

**The Ravn-Uhlig (2002) Scaling Rule**: Thomas Ravn and Harald Uhlig demonstrated that to achieve equivalent smoothing properties across quarterly and monthly data, the lambda parameter should scale with the fourth power of the frequency ratio:

λ_monthly = λ_quarterly × (frequency_ratio)⁴

Starting from the standard quarterly lambda of 1,600 (established by Hodrick and Prescott based on U.S. quarterly GDP):

λ_monthly = 1,600 × 3⁴ = 1,600 × 81 = 129,600

**Why This Scaling Matters**: The Ravn-Uhlig rule ensures that a business cycle of the same duration (e.g., a 5-year expansion-contraction cycle) receives equivalent smoothing treatment whether the data are observed monthly or quarterly. Without this adjustment, monthly data would be over-smoothed (losing cyclical detail) or quarterly data would be under-smoothed (retaining excessive noise).

**Empirical Validation**: Ravn and Uhlig validated this scaling rule by comparing HP-filtered monthly and temporally aggregated quarterly data, confirming that λ = 129,600 produces monthly cycle estimates consistent with those from quarterly data at λ = 1,600.

### 5.4 Why the Hodrick-Prescott Filter?

**Standard Practice in Business Cycle Analysis**: The HP filter has been used in thousands of academic papers and central bank reports analyzing business cycles. This standardization facilitates comparison of results across studies and countries.

**Transparent and Non-Parametric**: Unlike structural time series models that require specification of stochastic processes for trend and cycle, the HP filter makes no distributional assumptions about the data-generating process. The smoothing parameter λ explicitly controls the trend-cycle separation.

**Preserves Cyclical Asymmetries**: While the trend must be smooth, the cyclical component can exhibit asymmetric patterns (sharp contractions followed by gradual expansions) commonly observed in real business cycles.

**No Data Loss**: Unlike band-pass filters that truncate observations from both ends of the sample, the HP filter produces trend and cycle estimates for all time periods, including the most recent observations critical for policy analysis.

**Computationally Efficient**: The HP filter is solved as a system of linear equations with unique solution, making it computationally fast even for long time series and enabling its application to multiple indicators across multiple countries.

### 5.5 Cyclical Component Interpretation

After HP filtering, each series is decomposed as:

**D12 Component = Smooth Trend + Cyclical Deviation**

The cyclical component is expressed as:

**Cycle(%) = [(D12 - Trend) / Trend] × 100**

This formula produces **percentage deviations from trend**, making cycles comparable across variables with different units and scales. A positive cycle value indicates the variable is above its trend (economic expansion), while a negative value indicates below-trend performance (economic contraction).

### 5.6 Why the Two-Stage Approach (Henderson + HP)?

The sequential application of Henderson filtering followed by HP filtering provides advantages over using either method alone:

**Cleaner Input to HP Filter**: The Henderson filter removes seasonality, irregular fluctuations, and calendar effects in the first stage. The HP filter then operates on the pre-cleaned D12 series where the trend-cycle distinction is more clear-cut, improving the precision of the final trend estimate.

**Reduced Endpoint Bias**: While both filters suffer from endpoint bias (trend estimates at the most recent observations are less reliable because the filter cannot "see" future data), the two-stage approach mitigates this problem. The Henderson filter's initial smoothing reduces extreme values that would otherwise cause large HP trend revisions when new data arrive.

**Complementary Strengths**: The Henderson filter excels at removing high-frequency noise while preserving turning points. The HP filter excels at smooth trend extraction with an explicit, calibrated smoothing parameter. Together they provide superior cycle isolation.

**Standard Practice for Monthly Data**: This two-stage decomposition approach is recommended by Eurostat, OECD, and national statistical offices for monthly economic indicators, reflecting decades of practical experience with real-world data challenges.

---

## 6. Standardization

### 6.1 The Need for Standardization

After extracting cyclical components, the raw cycle measures have different scales and variances depending on the underlying variable:
- GDP cycles might range from -3% to +3%
- Construction production cycles might range from -15% to +15%
- Tourism cycles might range from -30% to +30%

These different scales would create problems for both statistical analysis and visualization:
- Variables with larger natural variation would dominate composite indicators
- Scatter plots would be distorted by scale differences
- Cross-country comparisons would be confounded by different economic structures

### 6.2 Z-Score Standardization

The methodology applies **z-score standardization** to each cyclical series:

**Standardized Cycle = (Raw Cycle - Mean Cycle) / Standard Deviation of Cycle**

This transformation:
1. Centers each series at zero (mean of standardized values = 0)
2. Scales each series to unit variance (standard deviation of standardized values = 1)
3. Preserves the relative positions of observations within each series

### 6.3 Interpretation of Standardized Cycles

A standardized cycle value of:
- **+1.0** indicates the variable is one standard deviation above its average cyclical position (strong expansion)
- **0.0** indicates the variable is at its typical cyclical position (neutral)
- **-1.0** indicates the variable is one standard deviation below its average position (significant contraction)
- **+2.0** or higher indicates extreme expansion (beyond 95% of historical observations)
- **-2.0** or lower indicates extreme contraction (beyond 95% of historical observations)

### 6.4 Benefits for Cross-Country Analysis

Standardization is particularly important for the multi-country framework:

**Structural Differences**: Countries differ in volatility due to economic structure (small open economies are more volatile than large diversified ones), industry composition (manufacturing-heavy economies are more cyclical), and institutional factors (automatic stabilizers dampen cycles). Standardization removes these structural differences, focusing on cyclical position relative to each country's history.

**Visualization Compatibility**: When multiple countries appear on the same animated scatter plot, standardization ensures all countries occupy comparable positions in the two-dimensional space defined by cyclical position and momentum.

**Statistical Aggregation**: If composite indicators or average cycle measures are computed across countries, standardization prevents countries with naturally higher volatility from dominating the aggregate.

---

## 7. Counter-Cyclical Indicator Inversion

### 7.1 Identifying Counter-Cyclical Variables

Most economic indicators are **pro-cyclical**: they rise during expansions and fall during contractions. However, three indicators in the framework behave counter-cyclically:

1. **Bankruptcy declarations**: Increase during contractions (business stress) and decrease during expansions
2. **Unemployment**: Rises during contractions (job losses) and falls during expansions (hiring)
3. **Non-performing loan ratio**: Increases during and after contractions (loan quality deterioration) and decreases during expansions

For these variables, a positive cyclical deviation indicates economic weakness, the opposite of the interpretation for pro-cyclical variables.

### 7.2 Sign Inversion for Consistency

To maintain a consistent interpretation where **positive values always indicate economic strength** and **negative values always indicate economic weakness**, the methodology inverts the sign of counter-cyclical indicators:

**Inverted Indicator = -1 × Original Indicator**

This transformation is applied to both:
- The standardized cyclical component (deviation from trend)
- The standardized month-over-month growth rate

### 7.3 Interpretation After Inversion

After inversion:
- **Positive standardized cycle** for bankruptcies means bankruptcies are below trend (economic strength)
- **Negative standardized cycle** for bankruptcies means bankruptcies are above trend (economic weakness)
- **Positive MoM growth** for unemployment means unemployment is falling (economic strength)
- **Negative MoM growth** for unemployment means unemployment is rising (economic weakness)

This consistent interpretation enables direct comparison across all variables in visualizations and composite indicators without mental adjustments for counter-cyclical variables.

---

## 8. Month-over-Month Growth Rates

### 8.1 Measuring Economic Momentum

While the standardized cyclical component indicates **where** the economy is in the business cycle (above or below trend), it does not directly reveal the **direction and speed** of movement. The month-over-month (MoM) growth rate provides this complementary information.

### 8.2 Calculation Method

For each D12 trend-cycle series, the month-over-month percentage change is computed:

**MoM Growth(%) = [(D12ₜ - D12ₜ₋₁) / |D12ₜ₋₁|] × 100**

The absolute value in the denominator ensures the formula works correctly for variables that can take negative values (though most economic indicators in this framework are positive by definition).

### 8.3 Standardization of Growth Rates

Like the cyclical components, raw MoM growth rates are standardized:

**Standardized MoM = (Raw MoM - Mean MoM) / Standard Deviation of MoM**

This standardization:
- Removes the average growth rate (the trend growth component)
- Scales all variables to comparable variation
- Enables interpretation in terms of standard deviations from normal momentum

### 8.4 Interpreting the Momentum Dimension

The standardized MoM growth rate captures **acceleration or deceleration** of economic activity:

**Positive standardized MoM**: Activity is increasing faster than average (accelerating expansion or emerging from contraction)

**Negative standardized MoM**: Activity is slowing or declining (decelerating expansion or deepening contraction)

**Zero standardized MoM**: Activity is growing at its average historical rate (stable pace)

### 8.5 The Four-Quadrant Framework

Combining the standardized cycle (position) with standardized MoM (momentum) creates a **four-quadrant characterization** of business cycle phases:

**Quadrant I (Positive Cycle, Positive Momentum)**
- **Position**: Above trend (expansion)
- **Direction**: Accelerating
- **Phase**: Strong expansion, possible overheating
- **Example**: GDP growing at 4% annually, accelerating from 3% last quarter

**Quadrant II (Negative Cycle, Positive Momentum)**
- **Position**: Below trend (contraction)
- **Direction**: Improving
- **Phase**: Recovery, emerging from trough
- **Example**: GDP still 2% below pre-recession peak but growing at 3% annually

**Quadrant III (Negative Cycle, Negative Momentum)**
- **Position**: Below trend (contraction)
- **Direction**: Deteriorating
- **Phase**: Deep recession, possible crisis
- **Example**: GDP 4% below trend and declining at 2% annual rate

**Quadrant IV (Positive Cycle, Negative Momentum)**
- **Position**: Above trend (expansion)
- **Direction**: Slowing
- **Phase**: Late expansion, approaching peak
- **Example**: GDP 3% above trend but growth slowing from 4% to 2% annually

This framework enables precise diagnosis of current economic conditions and anticipation of likely near-term evolution. Movement through the quadrants typically follows a clockwise pattern: I → IV → III → II → I.

---

## 9. Visualization in Flourish Studio

### 9.1 The Animated Scatter Plot Concept

The final output of the methodology is designed for visualization as an **animated scatter plot** in Flourish Studio, where:

- **X-axis**: Standardized cyclical component (position relative to trend)
- **Y-axis**: Standardized month-over-month growth rate (momentum/direction)
- **Animation**: Time progression, showing how each indicator moves through business cycle phases
- **Points**: Individual economic indicators or countries
- **Quadrants**: Represent the four business cycle phases

### 9.2 Data Structure for Flourish

The methodology produces data in **long format** suitable for Flourish import:

| time | Varijabla (Variable) | Odstupanje od trenda (%) | Mjesečna promjena (%) |
|------|---------------------|-------------------------|----------------------|
| January 2015 | GDP | -0.523 | 0.234 |
| January 2015 | Industrial Production | -1.234 | -0.567 |
| February 2015 | GDP | -0.412 | 0.445 |
| ... | ... | ... | ... |

Each row represents one variable at one time point, with columns for:
- **time**: Month-year combination for animation sequencing
- **Varijabla**: Indicator name (GDP, Construction, Retail Trade, etc.)
- **Odstupanje od trenda**: Standardized cycle (X-axis position)
- **Mjesečna promjena**: Standardized MoM (Y-axis position)

### 9.3 Visual Interpretation

**Point Position**: Each indicator appears as a point whose position in the quadrant space indicates both cyclical position and momentum.

**Point Movement**: As time advances, points move through the space, tracing trajectories that reveal:
- Expansions: Rightward and upward movement (toward Quadrant I)
- Peaks: Movement from Quadrant I to Quadrant IV (slowing but still above trend)
- Contractions: Leftward and downward movement (toward Quadrant III)
- Troughs: Movement from Quadrant III to Quadrant II (improving but still below trend)

**Clustering**: When multiple indicators cluster in the same quadrant, the business cycle phase is well-defined and broadly based. When indicators scatter across quadrants, the economic situation is mixed or transitional.

**Leading Indicators**: Building permits and business registrations typically move first, signaling upcoming turning points. Their position relative to coincident indicators (GDP, production) indicates whether the broader economy will follow.

**Lagging Indicators**: Unemployment and bankruptcies move last, confirming that a turning point has occurred. They typically remain in their current quadrant even as leading indicators shift.

### 9.4 Cross-Country Comparisons

When multiple countries appear in the same visualization:

**Synchronized Cycles**: Countries clustering together indicate synchronized business cycles, often driven by common shocks (global recession, commodity price movements, monetary policy coordination).

**Divergent Cycles**: Countries spread across different quadrants indicate asynchronous cycles, suggesting idiosyncratic shocks or structural differences dominating over common factors.

**Relative Positions**: Within a quadrant, relative positions matter. A country at (+2.0, +1.0) is in a stronger expansion than one at (+0.5, +0.5), even though both are in Quadrant I.

---

## 10. Methodological Strengths

### 10.1 Multi-Stage Filtering Advantages

The sequential application of seasonal adjustment → Henderson filtering → HP decomposition provides superior cycle isolation compared to single-stage methods:

**Progressively cleaner signals**: Each stage removes different types of non-cyclical variation, producing a final cycle measure focused specifically on business cycle frequencies (approximately 2-8 year duration).

**Robustness to data peculiarities**: The multi-stage approach adapts to different data characteristics. Series with strong seasonality benefit from thorough seasonal adjustment; series with structural breaks benefit from the Henderson filter's outlier resistance; series with varying trend growth benefit from the HP filter's flexibility.

**Consistent treatment**: All variables undergo the same sequence of transformations, ensuring that differences in final cycle estimates reflect genuine differences in economic behavior rather than methodological artifacts.

### 10.2 Standardization for Comparability

Z-score standardization provides crucial analytical advantages:

**Scale-free interpretation**: A standardized value of +1.5 means "one and a half standard deviations above average" regardless of whether the variable is GDP (measured in billions), employment (measured in thousands), or an index (measured in points).

**Cross-country comparability**: Standardization within each country's historical distribution removes structural differences in volatility, enabling meaningful comparison of business cycle positions across diverse economies.

**Statistical compatibility**: Standardized variables can be legitimately averaged, correlated, or used in factor analysis without concerns about scale differences distorting results.

### 10.3 Hierarchical Fallback Strategy

The comprehensive fallback procedures for seasonal adjustment and trend extraction ensure:

**No data loss**: Every indicator that passes minimum data requirements (at least 24 observations) receives some form of seasonal adjustment and trend-cycle extraction, even if sophisticated automatic procedures fail.

**Transparency**: When fallback methods are used, the code logs which indicators required simpler approaches, enabling assessment of potential quality differences across indicators.

**Pragmatic balance**: The approach recognizes that approximate adjustment is preferable to excluding indicators entirely, while still prioritizing the best available methods.

### 10.4 Temporal Coverage of Recent Developments

Starting the analysis in January 2015 captures approximately 10 years of diverse economic conditions:

**Pre-COVID expansion** (2015-2019): Extended period of growth following the Great Financial Crisis
**COVID-19 shock** (2020-2021): Unprecedented synchronous global contraction and rapid recovery
**Post-COVID developments** (2022-present): Inflation surge, monetary tightening, energy crisis (particularly relevant for European economies)

This coverage ensures the standardization parameters (means and standard deviations) reflect a full business cycle spanning expansion, shock, and recovery phases.

---

## 11. Methodological Limitations and Considerations

### 11.1 End-Point Problem

Both the Henderson and Hodrick-Prescott filters are **two-sided filters** that use information from observations before and after each point to estimate the trend. For the most recent observations in the dataset, only past information is available, making trend estimates less reliable.

**Magnitude of Revision**: Empirical studies show that trend estimates for the final 6-12 months of a sample can be revised substantially (sometimes changing sign) as new data accumulate. The final year's cyclical indicators should therefore be interpreted with appropriate uncertainty.

**Mitigation Strategy**: The methodology's conservative outlier detection and two-stage filtering reduce (but do not eliminate) endpoint bias. For policy decisions requiring high certainty about current position, analysts should consider the range of possible revisions to recent trend estimates.

**Real-Time Constraints**: In real-time applications, the endpoint problem is inherent—policymakers must act on preliminary estimates. The standardized presentation (z-scores) helps by contextualizing recent observations within the full historical distribution, but substantial uncertainty remains about whether recent movements represent genuine cycle shifts or noise that will be revised away.

### 11.2 Lambda Parameter Sensitivity

The choice of λ = 129,600 reflects standard practice and the Ravn-Uhlig scaling rule, but embodies specific assumptions:

**Frequency Band**: This lambda focuses on fluctuations with periods between roughly 2 and 8 years—the traditional business cycle frequency band. Shorter cycles (inventory cycles around 1 year) are attributed to noise, while longer movements (demographic shifts, technological waves) are attributed to trend.

**Alternative Values**: Some analysts prefer λ = 14,400 (one order of magnitude lower) to retain more variation as cycle, producing a more variable trend that adapts faster to structural changes. Others prefer λ = 1,296,000 (one order of magnitude higher) to produce an extremely smooth trend, isolating only the most persistent cyclical swings.

**Trade-offs**: Lower lambda values produce larger, more variable cycle estimates that may include medium-term structural shifts incorrectly classified as cyclical. Higher lambda values produce smaller cycle estimates that may miss genuine cyclical variation by attributing it to trend.

**Comparability Concerns**: Deviating from the standard λ = 129,600 sacrifices direct comparability with the large body of existing research using this calibration. This methodology prioritizes consistency with international practice over alternative parameterizations.

### 11.3 Linear Decomposition Assumptions

The additive decomposition model assumes:

**Independence**: Trend, cycle, and irregular components evolve independently and do not interact. In reality, large cyclical shocks may have persistent effects on trend growth (hysteresis), and irregular shocks (financial crises) may trigger cyclical recessions.

**Symmetry**: The HP filter implicitly assumes symmetric cycles—expansions and contractions of similar magnitude and duration. Empirical evidence suggests contractions are often sharper and shorter than expansions (asymmetry), though standardization partially addresses this by allowing cycles to differ in shape even if the trend must be smooth.

**Stationarity**: Standardization using full-sample means and standard deviations assumes the distribution of cyclical deviations is stable over time. If business cycle volatility has changed structurally (the "Great Moderation" followed by the "Great Instability"), full-sample standardization may not reflect current typical behavior.

### 11.4 Data Availability Constraints

The methodology requires sufficiently long time series for reliable seasonal adjustment and trend-cycle decomposition:

**Minimum 24 months**: Two complete annual cycles are needed for X-13 seasonal adjustment
**Preferably 48+ months**: Four years of data improve the stability of trend estimates and seasonal factors
**Longer is better**: The HP filter's reliability increases with sample size, though gains diminish beyond 10 years

For countries or indicators with shorter histories, results should be interpreted cautiously, particularly for recent observations where the endpoint problem is compounded by limited historical context.

### 11.5 Structural Breaks

The methodology assumes economic relationships remain reasonably stable over the sample period. Structural breaks—shifts in trend growth, changes in cyclical volatility, regime changes in policy or regulation—can violate this assumption:

**COVID-19**: The 2020 pandemic represents the most obvious structural break, with some indicators experiencing drops of 15-30% followed by rapid rebounds. The seasonal adjustment and trend extraction procedures handle this as an extreme outlier, but the "normal" cycle distribution may have changed post-pandemic.

**Euro Adoption**: Countries joining the euro experienced significant structural changes in monetary policy frameworks, financial integration, and trade patterns. Analyzing cycles spanning pre- and post-euro periods combines distinct economic regimes.

**Financial Crisis**: The 2008-2009 Great Financial Crisis affected countries differently based on banking system exposure and fiscal space. Standardization using periods including this crisis may not reflect current typical cycle behavior.

---

## 12. Practical Applications and Interpretation Guidelines

### 12.1 Recession Dating

The framework provides systematic evidence for identifying recessions:

**Breadth of Weakness**: A recession is more convincingly identified when multiple indicators across different sectors (production, demand, external trade) all show negative standardized cycles. Weakness in one or two indicators may reflect sector-specific shocks rather than economy-wide contraction.

**Depth of Cyclical Deviations**: Standardized cycles below -1.5 indicate substantial weakness (bottom 10% of historical distribution). When several key indicators (GDP, industrial production, employment) simultaneously reach this threshold, severe recession is indicated.

**Duration of Below-Trend Performance**: Brief dips below trend may represent temporary pauses in expansion rather than genuine recessions. Persistent negative cycles (multiple consecutive months with standardized values below -0.5) provide stronger evidence of sustained contraction.

**Momentum Indicator**: Movement from Quadrant I to Quadrant IV (positive cycle but negative momentum) provides early warning of approaching peaks. Movement from Quadrant III to Quadrant II (negative cycle but positive momentum) signals trough passage and beginning of recovery.

### 12.2 Identifying Turning Points

Business cycle turning points—peaks and troughs—are critical for policy but notoriously difficult to identify in real-time:

**Leading Indicators First**: Building permits, business registrations, and confidence indices typically turn before the broader economy. When these indicators shift quadrants while coincident indicators (GDP, production) remain in expansion territory, a turning point is approaching.

**Coincident Confirmation**: Peaks and troughs are confirmed when GDP, industrial production, employment, and consumption indicators all transition to the new phase. This confirmation typically occurs 2-4 months after leading indicators signal the turn.

**Lagging Confirmation**: Unemployment and bankruptcies turn last, often remaining elevated (or suppressed) for months after the broader economy has shifted. Their movement confirms the previous turn but does not predict the next one.

**Quadrant Clustering**: When the majority of indicators cluster in a single quadrant, the current business cycle phase is unambiguous. When indicators spread across multiple quadrants, the economy is in a transitional phase where the next movement is uncertain.

### 12.3 Sector-Specific Analysis

The indicator groupings enable analysis of which sectors lead or lag the business cycle:

**Construction and Investment**: Building permits and gross fixed capital formation are volatile and leading. Their position indicates whether capacity expansion or contraction is underway, with implications for future production capacity.

**Manufacturing**: Industrial production provides a timely coincident indicator. Its position relative to GDP indicates whether manufacturing is stronger or weaker than the service-oriented overall economy.

**Consumer Sector**: Retail trade and household consumption reveal the strength of consumer demand, which comprises 50-60% of GDP in most advanced economies. Sustained consumption strength can sustain expansions even when investment weakens.

**External Sector**: Export and import patterns reveal whether external demand reinforces or counteracts domestic conditions. Export strength during domestic weakness can moderate contractions, while import surges during expansion can create current account pressures.

**Labor Market**: Unemployment lags the cycle but provides critical information about the social and political sustainability of economic conditions. High unemployment persisting into the statistically defined recovery phase indicates "jobless recovery" requiring continued policy support.

### 12.4 Cross-Country Synchronization

The multi-country framework reveals:

**Common Euro Area Cycles**: When most euro area countries cluster in the same quadrant, common monetary policy and financial integration produce synchronized cycles. This synchronization supports the viability of single monetary policy.

**Country-Specific Shocks**: When some countries occupy different quadrants than others, idiosyncratic shocks or structural differences dominate. This divergence complicates monetary policy formulation and may require country-specific fiscal responses.

**Leading and Lagging Economies**: Some countries may consistently lead the euro area cycle (often Germany, Netherlands) while others lag (often peripheral economies). Identifying these patterns helps predict how shocks propagate across the monetary union.

**Convergence and Divergence**: Observing whether countries are moving toward quadrant clustering (convergence) or spreading apart (divergence) indicates whether economic integration is strengthening or weakening.

---

## 13. Software Implementation

### 13.1 R Programming Environment

The methodology is implemented in **R**, a statistical programming language widely used in econometric analysis. R provides:

**Specialized Packages**: The analysis relies on several purpose-built packages:
- `eurostat`: Interface to Eurostat's database with automatic data retrieval
- `seasonal`: X-13ARIMA-SEATS seasonal adjustment
- `tempdisagg`: Temporal disaggregation methods including Denton-Cholette
- `hpfilter`: Hodrick-Prescott filter implementation
- `dplyr`, `tidyr`: Data manipulation and transformation
- `zoo`, `lubridate`: Time series handling and date operations

**Reproducibility**: The complete analysis pipeline from data download through final output is specified in documented code, enabling full replication and verification of results.

**Extensibility**: New indicators or countries can be added by modifying data retrieval specifications without changing the core analytical pipeline.

### 13.2 Data Retrieval and Preprocessing

**Automated Download**: The `get_eurostat()` function retrieves data directly from Eurostat servers with appropriate filters (country, frequency, seasonal adjustment status, economic classification).

**Error Handling**: The `safe_get_eurostat()` wrapper function catches errors (missing data, network failures) and continues processing available indicators rather than terminating the entire analysis.

**Date Standardization**: All time series are converted to R `Date` objects with consistent formatting (first day of each month) to enable proper temporal alignment.

### 13.3 Processing Pipeline

The code implements a systematic pipeline:

1. **Data Retrieval**: Download quarterly and monthly indicators from Eurostat
2. **Data Cleaning**: Select relevant columns, remove missing values, rename variables
3. **Disaggregation**: Convert quarterly series to monthly using Denton-Cholette
4. **Seasonal Adjustment**: Apply X-13ARIMA-SEATS to tourism and trade data
5. **Trend Extraction**: Apply X-11 decomposition to extract D12 components
6. **HP Filtering**: Separate trend from cycle with λ = 129,600
7. **Standardization**: Convert to z-scores for comparability
8. **MoM Calculation**: Compute month-over-month growth rates
9. **Counter-Cyclical Inversion**: Reverse signs for bankruptcies, unemployment, NPL
10. **Output Formatting**: Transform to long format for Flourish visualization

### 13.4 Quality Checks

The implementation includes multiple validation steps:

**Data Availability Checks**: Verify minimum 24 observations before attempting decomposition
**Convergence Verification**: Ensure seasonal adjustment and HP filter converge successfully
**Outlier Review**: Log series requiring fallback methods for manual review
**Summary Statistics**: Generate summary tables showing data coverage and processing success rates

---

## 14. Output Files and Documentation

### 14.1 Structured Output Files

The methodology produces separate Excel files for different analytical purposes:

**Individual Indicator Groups** (5 files per country):
1. `1_vodeci_indikatori.xlsx`: Leading indicators (building permits, registrations)
2. `2_podudarni_proizvodnja.xlsx`: Coincident production indicators (GDP, industrial production)
3. `3_podudarni_potrosnja_trgovina.xlsx`: Coincident demand indicators (consumption, retail)
4. `4_vanjska_trgovina.xlsx`: External trade indicators (exports, imports)
5. `5_kasni_indikatori_stecaj.xlsx`: Lagging indicators (unemployment, bankruptcies, NPL)

**Combined File**:
- `combined_standardized_MoM_and_Cycle_Croatia.xlsx`: All indicators in single file for comprehensive analysis

**Multi-Country File**:
- `Euro_Area_Business_Cycles_All_Countries.xlsx`: All countries and indicators for cross-country comparison

### 14.2 Data Dictionary

Each output file contains three columns:

**time**: Month-year label (e.g., "January 2015", "February 2015")
- Format: English month names for international compatibility with Flourish Studio
- Enables chronological sorting and time-slider functionality in visualizations

**Varijabla (Variable)**: Indicator name in Croatian
- Examples: "BDP" (GDP), "Industrijska proizvodnja" (Industrial production)
- Consistent naming facilitates filtering and selection in visualization tools

**Odstupanje od trenda (%)**: Standardized cyclical component
- Interpretation: Z-score representing position relative to historical average
- Positive values = above trend (expansion), negative values = below trend (contraction)

**Mjesečna promjena (%)**: Standardized month-over-month growth rate
- Interpretation: Z-score representing momentum relative to historical average
- Positive values = accelerating, negative values = decelerating

### 14.3 Metadata and Processing Logs

The code generates console output documenting:

**Data Retrieval**: Success/failure messages for each indicator and country
**Processing Steps**: Notifications when fallback methods are used
**Summary Statistics**: Tables showing data coverage, processing success rates, and date ranges
**File Locations**: Confirmations of output file creation

This documentation enables quality review and debugging of processing issues.

---

## 15. Theoretical Foundation and Academic References

### 15.1 Business Cycle Theory

The methodology is grounded in **classical business cycle theory**, which conceptualizes aggregate economic activity as oscillating around a long-term growth trend:

**Burns and Mitchell (1946)**: Defined business cycles as "expansions occurring at about the same time in many economic activities, followed by similarly general recessions, contractions, and revivals which merge into the expansion phase of the next cycle."

**Kydland and Prescott (1990)**: Established the "stylized facts" of business cycles, including:
- Cycles lasting 2-8 years
- Asymmetry (sharp contractions, gradual expansions)
- Leading, coincident, and lagging indicators

**NBER Business Cycle Dating**: The National Bureau of Economic Research's methodology emphasizes:
- Examination of multiple indicators (not just GDP)
- Identifying turning points based on breadth, depth, and duration of changes
- Distinguishing genuine cycles from temporary fluctuations

This methodology implements these theoretical principles through:
- Multiple indicators across economic sectors
- Standardized measures enabling assessment of breadth
- Cyclical components revealing depth
- Monthly frequency enabling examination of duration

### 15.2 Time Series Decomposition Literature

**Hodrick and Prescott (1997)**: "Postwar U.S. Business Cycles: An Empirical Investigation"
- Established λ = 1,600 as standard for quarterly data
- Demonstrated HP filter's effectiveness for isolating business cycle frequencies

**Ravn and Uhlig (2002)**: "On Adjusting the Hodrick-Prescott Filter for the Frequency of Observations"
- Derived the fourth-power scaling rule: λ_monthly = λ_quarterly × 3⁴
- Validated λ = 129,600 for monthly data through empirical tests

**Baxter and King (1999)**: "Measuring Business Cycles: Approximate Band-Pass Filters for Economic Time Series"
- Compared alternative filtering methods
- Established frequency bands for business cycle analysis (2-8 years)

**Christiano and Fitzgerald (2003)**: "The Band Pass Filter"
- Refined band-pass filtering techniques
- Discussed trade-offs between endpoint problems and frequency isolation

This methodology's choice of HP filtering over band-pass alternatives reflects:
- Preference for preserving all observations (including recent data)
- Acceptance of standard practice facilitating comparison with existing research
- Practical consideration of real-time policy applications requiring current estimates

### 15.3 Seasonal Adjustment Standards

**U.S. Census Bureau**: "X-13ARIMA-SEATS Reference Manual" (Version 1.1, 2017)
- Defines international standard for seasonal adjustment
- Specifies diagnostic tests and quality criteria

**Eurostat**: "ESS Guidelines on Seasonal Adjustment" (2015)
- Recommends two-stage approach: X-11 for trend-cycle, followed by HP filter
- Establishes best practices for monthly economic indicators

**Findley et al. (1998)**: "New Capabilities and Methods of the X-12-ARIMA Seasonal-Adjustment Program"
- Describes outlier detection algorithms and regression modeling
- Provides theoretical foundation for automatic seasonal adjustment

This methodology's conservative outlier detection (critical value 4.0, additive outliers only) reflects awareness that excessive outlier adjustment risks removing genuine cyclical variation.

### 15.4 Temporal Disaggregation Theory

**Denton (1971)**: "Adjustment of Monthly or Quarterly Series to Annual Totals: An Approach Based on Quadratic Minimization"
- Introduced movement-preservation principle in temporal disaggregation
- Established foundation for Denton-Cholette method

**Cholette (1979)**: "Adjusting Sub-annual Series to Yearly Benchmarks"
- Extended Denton's work to handle benchmark revisions
- Demonstrated superiority for economic time series over regression-based approaches

**Chow and Lin (1971)**: "Best Linear Unbiased Interpolation, Distribution, and Extrapolation of Time Series by Related Series"
- Developed regression-based disaggregation
- Established framework for indicator-based methods

**Dagum and Cholette (2006)**: "Benchmarking, Temporal Distribution, and Reconciliation Methods for Time Series"
- Comprehensive treatment comparing alternative methods
- Validated Denton-Cholette for preserving short-term dynamics

This methodology's choice of Denton-Cholette over Chow-Lin reflects preference for movement preservation over exact period-by-period consistency, appropriate for business cycle analysis where momentum matters.

---

## 16. Validation and Robustness

### 16.1 Historical Validation

The methodology's output can be validated against known business cycle episodes:

**COVID-19 Recession (2020 Q1-Q2)**: The cyclical indicators should show:
- Sharp negative deviations (below -2 standard deviations) for most indicators
- Movement from Quadrant I (expansion) through Quadrant IV (slowing) to Quadrant III (contraction)
- Tourism showing extreme drops (standardized cycles below -3)
- Exports contracting due to global trade collapse
- Lagging indicators (unemployment) rising with some delay

**Euro Crisis (2011-2013)**: For affected countries (Greece, Spain, Italy, Portugal):
- Prolonged negative cycles reflecting extended contraction or stagnation
- Manufacturing showing deeper weakness than services
- Unemployment remaining elevated (high lagging indicator values) into recovery
- Divergence from core Euro Area countries (Germany, Netherlands)

**Pre-COVID Expansion (2015-2019)**: Most countries should show:
- Generally positive cyclical positions (above-trend activity)
- Gradual transition through Quadrant I as expansion matures
- Leading indicators showing some moderation by 2019 (European slowdown)
- Lagging indicators improving gradually (unemployment falling)

### 16.2 Consistency Checks

Several internal consistency tests validate methodology reliability:

**Turning Point Concordance**: Leading indicators should turn before coincident indicators, which should turn before lagging indicators. The temporal ordering should match theoretical expectations.

**Cross-Indicator Correlation**: Within each group (production, demand, external), indicators should show strong positive correlation in their standardized cycles. Low correlation suggests methodological issues or data quality problems.

**Quadrant Consistency**: During well-defined recession or expansion phases, most indicators should cluster in the expected quadrant. Excessive dispersion suggests either methodological problems or genuinely mixed economic signals requiring careful interpretation.

**Revision Stability**: As new data arrive and the sample extends, previously calculated cycle estimates should remain relatively stable (changes under 0.3 standard deviations). Large revisions to distant past observations suggest potential issues with the filtering approach.

### 16.3 Sensitivity Analysis

Key methodological choices can be tested through sensitivity analysis:

**Lambda Variations**: Recomputing with λ = 14,400 and λ = 1,296,000 reveals how sensitive cyclical indicators are to the trend-cycle decomposition. If conclusions about recession timing or severity change substantially, additional caution is warranted.

**Seasonal Adjustment**: Comparing results with Eurostat's provided seasonal adjustment against custom X-13 adjustment reveals how much seasonal patterns affect cycle estimates. Large differences suggest potential seasonal adjustment issues requiring investigation.

**Disaggregation Method**: Testing Chow-Lin against Denton-Cholette for quarterly series reveals sensitivity to disaggregation approach. Agreement between methods increases confidence; disagreement requires careful examination of quarterly-monthly relationships.

**Standardization Period**: Computing standardization parameters using different time windows (e.g., only post-2010 data vs. full sample) reveals whether recent patterns differ from historical distribution. Changing z-score interpretations across time windows suggest potential structural breaks.

---

## 17. Extensions and Future Development

### 17.1 Potential Enhancements

**Real-Time Updating**: Automating monthly data retrieval and reprocessing enables continuous monitoring of business cycle evolution. Implementation would require scheduled execution and database storage of historical results.

**Forecast Incorporation**: Leading indicators enable short-term forecasting of coincident indicators. Statistical models (VAR, factor models) could formalize these relationships and generate probabilistic forecasts of near-term cycle evolution.

**Frequency-Specific Filters**: Applying separate filters for different cycle frequencies (growth cycles 2-8 years, medium-term structural shifts 8-20 years) would distinguish types of economic variation more precisely.

**Alternative Smoothing Parameters**: While λ = 129,600 reflects standard practice, country-specific calibration based on historical cycle durations could improve fit for countries with unusually short or long typical cycles.

**Composite Indicators**: Constructing weighted averages across indicators (respecting indicator groups) could produce single summary measures of cyclical position and momentum, simplifying communication though at cost of detail.

### 17.2 Additional Data Sources

**High-Frequency Data**: Incorporating weekly or daily indicators (credit card transactions, mobility data, energy consumption) would enable more timely cycle monitoring, particularly valuable during rapidly evolving situations.

**Survey Data**: Business and consumer confidence indices provide forward-looking information complementing backward-looking activity data. PMI (Purchasing Managers' Index) data, in particular, provide valuable leading information.

**Financial Indicators**: Stock market indices, credit spreads, yield curves contain information about market participants' economic expectations. Their cyclical patterns often lead real activity indicators.

**Regional Disaggregation**: National indicators mask regional heterogeneity. Analyzing cycles at NUTS-2 (regional) level would reveal whether national patterns reflect broad-based trends or concentration in specific regions.

### 17.3 Advanced Analytical Techniques

**Factor Models**: Extracting common factors from the multiple indicators would identify shared cycle components while distinguishing indicator-specific variation. Dynamic factor models could separate common Euro Area factors from country-specific factors.

**Regime-Switching Models**: Markov-switching specifications would explicitly model different business cycle regimes (expansion, recession) with estimated transition probabilities between states.

**Wavelet Analysis**: Time-frequency decomposition via wavelets would reveal how cyclical patterns evolve over time, identifying periods of increased or decreased volatility and changes in dominant cycle frequencies.

**Network Analysis**: Constructing networks based on cross-indicator and cross-country correlations would reveal contagion patterns and identify systemically important indicators whose movements predict broader changes.

---

## 18. Conclusion

This methodology provides a comprehensive, rigorous framework for business cycle analysis suitable for multi-country visualization. By combining internationally recognized statistical techniques—X-13ARIMA-SEATS seasonal adjustment, X-11 Henderson filtering, Hodrick-Prescott decomposition, and z-score standardization—the approach transforms diverse macroeconomic indicators into standardized cyclical measures with consistent interpretation.

The two-dimensional framework (cyclical position and momentum) enables precise characterization of business cycle phases through a four-quadrant visualization. The animated scatter plot format in Flourish Studio makes complex econometric analysis accessible to broad audiences while maintaining analytical rigor.

Key methodological strengths include:
- **Standardization ensuring comparability** across variables with different scales and countries with different structures
- **Hierarchical fallback procedures** maintaining comprehensive indicator coverage despite data challenges
- **Conservative parameter choices** (lambda, outlier detection) balancing smoothing with retention of genuine cyclical variation
- **Transparent, reproducible implementation** in well-documented R code

Important limitations requiring careful interpretation:
- **End-point bias** in most recent observations, requiring uncertainty acknowledgment
- **Structural break sensitivity**, particularly around major shocks like COVID-19
- **Parameter dependence**, with results reflecting specific smoothing choices
- **Linear decomposition assumptions** that may not fully capture cycle complexities

The methodology serves multiple practical purposes:
- **Recession identification** through breadth, depth, and duration of negative deviations
- **Turning point detection** via leading indicator movements and quadrant transitions
- **Sector analysis** revealing which economic dimensions lead or lag
- **Cross-country comparison** showing synchronization or divergence of cycles

This framework provides policymakers, analysts, and researchers with powerful tools for understanding and communicating business cycle dynamics in the Euro Area and beyond.

---

## References

Baxter, M., & King, R. G. (1999). Measuring business cycles: approximate band-pass filters for economic time series. *Review of Economics and Statistics*, 81(4), 575-593.

Burns, A. F., & Mitchell, W. C. (1946). *Measuring business cycles*. National Bureau of Economic Research.

Cholette, P. A. (1979). Adjusting sub-annual series to yearly benchmarks. *Statistics Canada Time Series Research and Analysis Division*.

Chow, G. C., & Lin, A. L. (1971). Best linear unbiased interpolation, distribution, and extrapolation of time series by related series. *The Review of Economics and Statistics*, 53(4), 372-375.

Christiano, L. J., & Fitzgerald, T. J. (2003). The band pass filter. *International Economic Review*, 44(2), 435-465.

Dagum, E. B., & Cholette, P. A. (2006). *Benchmarking, temporal distribution, and reconciliation methods for time series*. Springer Science & Business Media.

Denton, F. T. (1971). Adjustment of monthly or quarterly series to annual totals: an approach based on quadratic minimization. *Journal of the American Statistical Association*, 66(333), 99-102.

Eurostat (2015). *ESS guidelines on seasonal adjustment*. Publications Office of the European Union.

Findley, D. F., Monsell, B. C., Bell, W. R., Otto, M. C., & Chen, B. C. (1998). New capabilities and methods of the X-12-ARIMA seasonal-adjustment program. *Journal of Business & Economic Statistics*, 16(2), 127-152.

Hodrick, R. J., & Prescott, E. C. (1997). Postwar U.S. business cycles: an empirical investigation. *Journal of Money, Credit, and Banking*, 29(1), 1-16.

Kydland, F. E., & Prescott, E. C. (1990). Business cycles: real facts and a monetary myth. *Federal Reserve Bank of Minneapolis Quarterly Review*, 14(2), 3-18.

Ravn, M. O., & Uhlig, H. (2002). On adjusting the Hodrick-Prescott filter for the frequency of observations. *Review of Economics and Statistics*, 84(2), 371-376.

U.S. Census Bureau (2017). *X-13ARIMA-SEATS reference manual, version 1.1*. Washington, DC: U.S. Census Bureau.
