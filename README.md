# Business Cycle Analysis for Euro Area Countries

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![R Version](https://img.shields.io/badge/R-%3E%3D%204.0.0-blue)](https://www.r-project.org/)

Comprehensive econometric framework for decomposing macroeconomic time series into trend and cyclical components across Euro Area countries. The analysis produces standardized cyclical indicators and momentum measures suitable for animated scatter plot visualization in Flourish Studio.

## 📊 Overview

This repository contains R scripts that implement a sophisticated multi-stage filtering approach combining:
- **X-13ARIMA-SEATS** seasonal adjustment
- **Denton-Cholette** temporal disaggregation (quarterly to monthly)
- **Henderson filter** (X-11 decomposition) for trend-cycle extraction
- **Hodrick-Prescott filter** for cyclical decomposition
- **Z-score standardization** for cross-country comparability

The methodology transforms diverse macroeconomic indicators into a two-dimensional framework (cyclical position × momentum) that characterizes business cycle phases through four quadrants: expansion, peak, contraction, and recovery.

## 🎯 Key Features

- **22 indicators for Croatia** including unique local data sources (EIZ OVI index, vehicle registrations, insured persons)
- **13-15 indicators for 19 other Euro Area countries** (Austria, Belgium, Cyprus, Estonia, Finland, France, Germany, Greece, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Portugal, Slovakia, Slovenia, Spain)
- **Automated data retrieval** from Eurostat and ECB Statistical Data Warehouse
- **Robust error handling** with hierarchical fallback strategies
- **Publication-ready outputs** in Excel format for Flourish Studio visualization

## 📁 Repository Structure

```
business-cycle-analysis/
├── README.md                           # This file
├── samo_hrvatska.R                     # Croatia-specific analysis (22 indicators)
├── ostatak_zemalja.R          # Analysis for 19 other Euro Area countries
├── methodology/
│   ├── business_cycle_methodology.md  # Complete methodology (English)
│   └── metodologija_poslovni_ciklus_HR.md  # Methodology (Croatian)
├── output/                            # Generated Excel files (not tracked)
│   ├── 1_vodeci_indikatori.xlsx
│   ├── 2_podudarni_proizvodnja.xlsx
│   ├── 3_podudarni_potrosnja_trgovina.xlsx
│   ├── 4_vanjska_trgovina.xlsx
│   ├── 5_kasni_indikatori_stecaj.xlsx
│   └── combined_standardized_MoM_and_Cycle_*.xlsx
└── .gitignore
```

## 🔧 Installation

### Prerequisites

- **R** version ≥ 4.0.0
- **RStudio** (recommended)

### Required R Packages

```r
# Install required packages
install.packages(c(
  "readxl",
  "hpfilter",
  "eurostat",
  "dplyr",
  "tidyr",
  "seasonal",
  "lubridate",
  "tempdisagg",
  "zoo",
  "openxlsx",
  "ecb"
))
```

### Package Descriptions

| Package | Purpose |
|---------|---------|
| `eurostat` | Access to Eurostat database API |
| `ecb` | Access to ECB Statistical Data Warehouse |
| `seasonal` | X-13ARIMA-SEATS seasonal adjustment |
| `tempdisagg` | Temporal disaggregation (Denton-Cholette method) |
| `hpfilter` | Hodrick-Prescott filter implementation |
| `dplyr`, `tidyr` | Data manipulation and transformation |
| `zoo`, `lubridate` | Time series and date handling |
| `openxlsx` | Excel file creation |
| `readxl` | Excel file reading |

## 🐍 Python port (in progress)

The pipeline is being ported from R to Python (see `UPDATE_PLAN.md` and `TASKS.md`). The R scripts in `skripte/` remain the reference implementation until the parity check passes. Note: the file is `skripte/ostale_zemlje.R`, not `ostatak_zemalja.R` as written below.

### Environment

```bash
conda env create -f environment.yml
conda activate semafori          # or prefix commands with: conda run -n semafori
python -m pip install -e .
python -m pytest
```

### X-13ARIMA-SEATS binary

`environment.yml` installs the Census X-13 binary from conda-forge (package `x13as`, executable `x13as_ascii`) on Windows and Linux; statsmodels finds it on the environment PATH, so nothing else is needed. The environment must be activated (`conda activate semafori` or `conda run -n semafori`): calling the environment's `python.exe` directly does not put the binary on PATH and statsmodels will report X-13 as missing. Verify:

```bash
python -c "from statsmodels.tsa.x13 import _find_x12; print(_find_x12())"
```

Without conda: download the ASCII build from https://www.census.gov/data/software/x13as.html, unzip it into a folder whose path has no spaces (for example `C:\x13as` on Windows or `~/x13as` on Linux, then `chmod +x x13as` on Linux), and set `X13PATH` to that folder (`setx X13PATH C:\x13as` on Windows, `export X13PATH=~/x13as` on Linux). Re-run the check above.

### Local inputs

Croatian Excel inputs live in `data/` and are not tracked by git. See `data/README.md` for file names, columns, and the monthly update procedure.

## 🚀 Quick Start

### Running the Croatia Analysis

```r
# Set working directory
setwd("path/to/business-cycle-analysis")

# Load the script
source("samo_hrvatska.R")

# The script will:
# 1. Download data from Eurostat, ECB, and local sources
# 2. Apply seasonal adjustment and disaggregation
# 3. Extract trends and cycles
# 4. Generate 5 categorized Excel files + 1 combined file
```

### Running the Euro Area Analysis

```r
# Load the script
source("ostatak_zemalja.R")

# The script will:
# 1. Process all 19 Euro Area countries sequentially
# 2. Generate individual country files with separate sheets
# 3. Create a master file combining all countries
# 4. Display processing summary statistics
```

## 📈 Indicator Categories

### Leading Indicators
Anticipate future economic activity:
- Building permits for residential dwellings
- New business registrations
- **OVI business confidence index** (Croatia only)
- **First-time vehicle registrations** - passenger & freight (Croatia only)

### Supply/Production Indicators (Coincident)
Move simultaneously with current economic activity:
- GDP at constant prices
- Industrial production (sectors B-D)
- Construction production
- Total production (excluding finance)
- Tourism overnight stays
- **Number of insured persons** (Croatia only)

### Demand/Consumption Indicators (Coincident)
Reflect current consumption patterns:
- Retail trade volume
- Wholesale trade volume
- Household final consumption expenditure
- Gross fixed capital formation (investment)

### External Trade Indicators
Capture international economic linkages:
- Exports of goods
- Exports of services
- Imports of goods
- Imports of services

### Lagging Indicators
Confirm economic trends after they occur:
- Bankruptcy declarations
- Unemployment (number of unemployed persons)
- **Non-performing loan ratio** (from ECB)

## 🔬 Methodology

### 1. Temporal Disaggregation (Denton-Cholette)

Converts quarterly data (GDP, consumption, investment, building permits) to monthly frequency:

**Why Denton-Cholette?**
- Preserves month-to-month movements of related indicator series
- Maintains accounting consistency over time
- Distributes adjustments smoothly without artificial breaks
- Robust to data revisions

**Formula:**
```
Minimize: Σ[(mₜ - mₜ₋₁) - (rₜ - rₜ₋₁)]² + penalty × [Σmₜ - Qₜ]²
```
Where m = monthly series, r = related indicator, Q = quarterly aggregate

### 2. Seasonal Adjustment (X-13ARIMA-SEATS)

Applied with **conservative outlier detection settings** to preserve genuine cyclical variation:

```r
seas(series_ts,
     outlier.types = "AO",          # Only additive outliers
     outlier.critical = 4.0,         # Higher critical value (default is 3.0)
     regression.aictest = NULL)      # Disable automatic tests
```

**Rationale:**
- `outlier.critical = 4.0`: Prevents removal of genuine business cycle movements
- Additive outliers only: Avoids treating turning points as level shifts
- No automatic tests: Eurostat data already calendar-adjusted

### 3. Trend-Cycle Extraction (Henderson Filter / X-11)

Extracts the **D12 component** representing combined trend and cycle:
- Removes seasonality, irregular fluctuations, calendar effects
- Preserves turning points without excessive lag
- Optimal for economic time series

### 4. Cyclical Decomposition (Hodrick-Prescott Filter)

Separates smooth trend from cyclical deviations using **λ = 129,600** for monthly data.

**Ravn-Uhlig (2002) Scaling Rule:**
```
λ_monthly = λ_quarterly × (frequency_ratio)⁴
λ_monthly = 1,600 × 3⁴ = 1,600 × 81 = 129,600
```

**Why this λ?**
- Ensures consistent smoothing across data frequencies
- Focuses on 2-8 year business cycle frequencies
- International standard for monthly macroeconomic analysis

**Cycle Calculation:**
```r
Cycle (%) = [(D12 - Trend) / Trend] × 100
```

### 5. Standardization (Z-score)

Transforms all indicators to comparable scale:

```r
Standardized_Cycle = (Cycle - mean(Cycle)) / sd(Cycle)
```

**Interpretation:**
- `+1.0` = One standard deviation above average (strong expansion)
- `0.0` = Typical cyclical position (neutral)
- `-1.0` = One standard deviation below average (significant contraction)
- `±2.0` = Extreme values (beyond 95% of historical observations)

### 6. Counter-Cyclical Indicator Inversion

For consistent interpretation, counter-cyclical indicators are inverted:

```r
# Inverted indicators
- Bankruptcy declarations
- Unemployment
- Non-performing loan ratio

# Transformation
Inverted_Indicator = -1 × Original_Indicator
```

After inversion: positive values always indicate economic strength.

### 7. Month-over-Month Growth Rates

Measures economic momentum:

```r
MoM_Growth (%) = [(D12ₜ - D12ₜ₋₁) / |D12ₜ₋₁|] × 100
Standardized_MoM = (MoM - mean(MoM)) / sd(MoM)
```

### Four-Quadrant Framework

| Quadrant | Cycle | Momentum | Phase | Example |
|----------|-------|----------|-------|---------|
| **I** | Positive | Positive | Strong expansion | GDP growing and accelerating |
| **II** | Negative | Positive | Recovery | Below trend but improving |
| **III** | Negative | Negative | Deep recession | Below trend and deteriorating |
| **IV** | Positive | Positive | Late expansion | Above trend but slowing |

Movement through quadrants typically follows clockwise pattern: I → IV → III → II → I

## 📊 Output Files

### Individual Category Files (Croatia)
- `1_vodeci_indikatori.xlsx` - Leading indicators
- `2_podudarni_proizvodnja.xlsx` - Supply/production indicators
- `3_podudarni_potrosnja_trgovina.xlsx` - Demand/consumption indicators
- `4_vanjska_trgovina.xlsx` - External trade indicators
- `5_kasni_indikatori_stecaj.xlsx` - Lagging indicators

### Combined Files
- `combined_standardized_MoM_and_Cycle_Croatia.xlsx` - All Croatian indicators
- `Euro_Area_Business_Cycles_All_Countries.xlsx` - All countries combined
- `Business_Cycle_[Country].xlsx` - Individual country files (19 countries)

### Data Structure

Each file contains long-format data ready for Flourish Studio:

| Column | Description | Format |
|--------|-------------|--------|
| `time` | Month-year | "January 2015", "February 2015", ... |
| `Varijabla` | Indicator name | "BDP", "Industrijska proizvodnja", ... |
| `Odstupanje od trenda (%)` | Standardized cycle | Z-score (-3 to +3) |
| `Mjesečna promjena (%)` | Standardized MoM | Z-score (-3 to +3) |

## 🎨 Visualization in Flourish Studio

### Setup

1. Import the combined Excel file to Flourish
2. Create **Scatter plot** visualization
3. Configure axes:
   - **X-axis:** `Odstupanje od trenda (%)` (Cyclical position)
   - **Y-axis:** `Mjesečna promjena (%)` (Momentum)
4. Set **Time slider:** `time` column
5. Configure **Points:** `Varijabla` (each indicator as separate series)

### Interpretation

**Quadrant positioning:**
- **Quadrant I (top-right):** Expansion phase - above trend and accelerating
- **Quadrant II (top-left):** Recovery phase - below trend but improving  
- **Quadrant III (bottom-left):** Contraction phase - below trend and deteriorating
- **Quadrant IV (bottom-right):** Peak phase - above trend but slowing

**Point clustering:** When multiple indicators cluster in the same quadrant, the business cycle phase is well-defined and broad-based.

**Indicator movement:** Leading indicators move first, followed by coincident indicators 2-4 months later, and lagging indicators confirm the turn.

## 🔍 Example Usage

### Identifying Recession

A recession is identified when:

1. **Breadth:** Multiple indicators across sectors show negative standardized cycles
2. **Depth:** Key indicators (GDP, industrial production) below -1.5 standard deviations
3. **Duration:** Persistent negative cycles for 3+ consecutive months
4. **Momentum:** Movement from Quadrant I → IV → III indicates approaching/entering recession

### Detecting Turning Points

**Peak detection:**
- Leading indicators shift from Quadrant I to Quadrant IV
- Coincident indicators still in Quadrant I
- Lagging indicators at maximum positive values

**Trough detection:**
- Leading indicators shift from Quadrant III to Quadrant II
- Coincident indicators still in Quadrant III
- Lagging indicators remain elevated

## ⚙️ Configuration

### Time Period

Default: January 2015 onwards

To modify:
```r
# In both scripts, locate:
time_filter <- list(sinceTimePeriod = "2015-01")

# Change to desired start date:
time_filter <- list(sinceTimePeriod = "2020-01")  # Start from 2020
```

### Lambda Parameter

Default: λ = 129,600 (Ravn-Uhlig standard for monthly data)

To modify:
```r
# Locate HP filter section:
ytrend_group <- hp2(y_group, lambda = 129600)

# Alternative values:
ytrend_group <- hp2(y_group, lambda = 14400)    # More variable cycle
ytrend_group <- hp2(y_group, lambda = 1296000)  # Smoother cycle
```

**Note:** Changing λ sacrifices comparability with international research.

### Seasonal Adjustment Settings

To modify outlier detection:
```r
# Locate seasonal adjustment:
model <- seas(series_ts,
              outlier.types = "AO",
              outlier.critical = 4.0,      # Change this value
              regression.aictest = NULL)

# More aggressive: 3.0 (detects more outliers)
# More conservative: 5.0 (detects fewer outliers)
```

## 🐛 Troubleshooting

### Common Issues

**1. Package Installation Errors**

```r
# If eurostat fails, try:
install.packages("eurostat", dependencies = TRUE)

# If seasonal (X-13) fails on Windows, install Rtools first:
# Download from: https://cran.r-project.org/bin/windows/Rtools/
```

**2. Data Download Failures**

```r
# Check internet connection
# Eurostat servers occasionally timeout - simply re-run the script

# For persistent issues, check Eurostat API status:
# https://ec.europa.eu/eurostat/web/main/data/database
```

**3. Insufficient Data Error**

```
Error: Insufficient data for group: [name] - need at least 24 months
```

**Solution:** Some countries or indicators may have shorter data series. The script automatically skips these and continues processing other indicators.

**4. X-11 Decomposition Failures**

The script includes hierarchical fallback:
1. Standard X-11 → 2. Simplified ARIMA → 3. Random walk → 4. Moving average

Check console output for warnings about which series used fallback methods.

## 📚 References

### Key Publications

**Temporal Disaggregation:**
- Denton, F. T. (1971). Adjustment of monthly or quarterly series to annual totals. *Journal of the American Statistical Association*, 66(333), 99-102.
- Cholette, P. A. (1979). Adjusting sub-annual series to yearly benchmarks. *Statistics Canada*.

**Hodrick-Prescott Filter:**
- Hodrick, R. J., & Prescott, E. C. (1997). Postwar U.S. business cycles: an empirical investigation. *Journal of Money, Credit, and Banking*, 29(1), 1-16.
- Ravn, M. O., & Uhlig, H. (2002). On adjusting the Hodrick-Prescott filter for the frequency of observations. *Review of Economics and Statistics*, 84(2), 371-376.

**Seasonal Adjustment:**
- U.S. Census Bureau (2017). *X-13ARIMA-SEATS reference manual, version 1.1*. Washington, DC.
- Eurostat (2015). *ESS guidelines on seasonal adjustment*. Publications Office of the EU.

**Business Cycle Theory:**
- Burns, A. F., & Mitchell, W. C. (1946). *Measuring business cycles*. NBER.
- Kydland, F. E., & Prescott, E. C. (1990). Business cycles: real facts and a monetary myth. *Federal Reserve Bank of Minneapolis Quarterly Review*, 14(2), 3-18.

### Methodological Documentation

For complete methodological details, see:
- `methodology/business_cycle_methodology.md` (English)
- `methodology/metodologija_poslovni_ciklus_HR.md` (Croatian)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/NewIndicator`)
3. Commit your changes (`git commit -m 'Add new indicator'`)
4. Push to the branch (`git push origin feature/NewIndicator`)
5. Open a Pull Request

### Potential Contributions

- Additional country-specific indicators
- Real-time data update automation
- Short-term forecasting models
- Alternative filtering methods comparison
- Visualization templates for different tools

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👤 Author

**SilvioPokorni**
- GitHub: [@silviopokorniES](https://github.com/silviopokorniES)
- LinkedIn: [Silvio Pokorni](https://www.linkedin.com/in/silvio-pokorni-08076a254/)

## 🙏 Acknowledgments

- **Eurostat** for providing comprehensive harmonized macroeconomic statistics
- **European Central Bank** for financial sector data
- **Economic Institute Zagreb (EIZ)** for OVI business confidence index
- **R Core Team** and package maintainers for statistical computing tools
- **Ravn & Uhlig (2002)** for lambda scaling methodology
- **Denton & Cholette** for temporal disaggregation framework

## 📞 Support

For questions or issues:
- Open an [Issue](https://github.com/yourusername/business-cycle-analysis/issues)
- Email: your.email@example.com

## 🔄 Version History

### v1.0.0 (2025-01-21)
- Initial release
- 22 indicators for Croatia
- 13-15 indicators for 19 Euro Area countries
- Complete methodology documentation
- Flourish Studio-ready outputs

---

**Built with ❤️ using R, Eurostat data, and advanced econometric methods**

**Keywords:** business cycle, macroeconomic analysis, time series decomposition, Hodrick-Prescott filter, seasonal adjustment, Euro Area, Croatia, econometrics, R programming, data visualization
