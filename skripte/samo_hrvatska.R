library(readxl)
library(hpfilter)
library(eurostat)
library(dplyr)
library(tidyr)
library(seasonal)
library(lubridate)
library(tempdisagg)
library(zoo)
library(openxlsx)
library(ecb)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Set time filter for all Eurostat data (from 2015-01 onwards)
time_filter <- list(sinceTimePeriod = "2015-01")

# Base date for indexing (consistent across all variables)
base_date <- as.Date("2021-01-01")

# HP filter lambda for monthly data (Ravn-Uhlig rule: 1600 * 12^4 = 129600)
hp_lambda <- 129600

# Minimum observations required for processing
min_observations <- 24
min_seasonal_obs <- 36

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Safe file reading function with error handling
safe_read_excel <- function(filepath, description) {
   if (!file.exists(filepath)) {
      warning(paste("File not found:", filepath, "-", description, "will be NULL"))
      return(NULL)
   }
   tryCatch({
      read_excel(filepath) %>%
         mutate(time = as.Date(time)) %>%
         mutate(across(.cols = -time, .fns = ~ round(.x, 3)))
   }, error = function(e) {
      warning(paste("Error reading", filepath, ":", e$message))
      return(NULL)
   })
}

# Function for seasonal adjustment (X-13) with error handling
adjust_series_x13 <- function(numeric_vector, start_date, frequency = 12) {
   tryCatch({
      start_vector <- c(year(start_date), 
                        if(frequency == 12) month(start_date) else quarter(start_date))
      series_ts <- ts(numeric_vector, start = start_vector, frequency = frequency)
      
      # Use conservative outlier detection settings
      model <- seas(series_ts,
                    outlier.types = "AO",
                    outlier.critical = 4.0,
                    regression.aictest = NULL)
      return(as.numeric(final(model)))
   }, error = function(e) {
      message(paste("Seasonal adjustment failed, using original data:", e$message))
      return(numeric_vector)
   })
}

# Function to disaggregate quarterly to monthly using Denton-Cholette
disaggregate_q_to_m <- function(df_quarterly, value_col_name) {
   # Input validation
   if (is.null(df_quarterly)) return(NULL)
   if (!is.data.frame(df_quarterly)) {
      warning("Input must be a data frame")
      return(NULL)
   }
   if (nrow(df_quarterly) == 0) return(NULL)
   if (!value_col_name %in% names(df_quarterly)) {
      warning(paste("Column", value_col_name, "not found in data"))
      return(NULL)
   }
   if (!"time" %in% names(df_quarterly)) {
      warning("Data must contain a 'time' column")
      return(NULL)
   }
   
   tryCatch({
      start_date_q <- min(df_quarterly$time)
      start_year <- year(start_date_q)
      start_qtr <- quarter(start_date_q)
      
      ts_q <- ts(df_quarterly[[value_col_name]], 
                 start = c(start_year, start_qtr), 
                 frequency = 4)
      
      ts_m <- tempdisagg::td(ts_q ~ 1, 
                             to = "monthly", 
                             method = "denton-cholette", 
                             conversion = "average")
      
      values_m <- as.numeric(predict(ts_m))
      start_date_m <- floor_date(start_date_q, "quarter")
      num_months <- length(values_m)
      time_m <- seq.Date(from = start_date_m, by = "month", length.out = num_months)
      
      df_monthly <- data.frame(time = time_m, values = values_m)
      names(df_monthly)[2] <- value_col_name
      return(df_monthly)
   }, error = function(e) {
      message(paste("Disaggregation failed for", value_col_name, ":", e$message))
      return(NULL)
   })
}

# Function to extract D12 trend using X-11 Henderson filter (FIXED SCOPING)
extract_d12_trend <- function(data, value_col) {
   # Input validation
   if (is.null(data) || nrow(data) == 0) return(NULL)
   if (!value_col %in% names(data)) {
      warning(paste("Column", value_col, "not found"))
      return(NULL)
   }
   
   start_date <- min(data$time)
   start_year <- year(start_date)
   start_month <- month(start_date)
   
   ts_data <- ts(data[[value_col]], 
                 start = c(start_year, start_month), 
                 frequency = 12)
   
   # Initialize result as NULL
   d12_series <- NULL
   
   # First attempt: default X-11 settings
   d12_series <- tryCatch({
      model <- seas(ts_data, x11 = "")
      series(model, "x11.trend")
   }, error = function(e) {
      message(paste("First attempt failed for", value_col, ". Trying alternative approach..."))
      NULL
   })
   
   # Second attempt: with simple ARIMA model
   if (is.null(d12_series)) {
      d12_series <- tryCatch({
         model <- seas(ts_data, x11 = "", 
                       arima.model = "(0 1 1)(0 1 1)",
                       regression.aictest = NULL)
         series(model, "x11.trend")
      }, error = function(e) {
         message(paste("Second attempt failed for", value_col, ". Trying without automdl..."))
         NULL
      })
   }
   
   # Third attempt: minimal settings
   if (is.null(d12_series)) {
      d12_series <- tryCatch({
         model <- seas(ts_data, x11 = "",
                       arima.model = "(0 1 0)(0 1 0)",
                       automdl = NULL,
                       outlier = NULL,
                       regression.aictest = NULL)
         series(model, "x11.trend")
      }, error = function(e) {
         message(paste("Third attempt failed for", value_col))
         NULL
      })
   }
   
   # Final fallback: centered moving average
   if (is.null(d12_series)) {
      message(paste("All X-11 attempts failed for", value_col, ". Using 12-month moving average."))
      d12_series <- rollapply(ts_data, width = 12, FUN = mean, 
                              align = "center", fill = NA)
   }
   
   result <- data.frame(
      time = data$time,
      trend = as.numeric(d12_series)
   )
   names(result)[2] <- paste0("d12_", value_col)
   
   return(result)
}

# Function to index data with base date
index_data <- function(data, base_date) {
   if (is.null(data) || nrow(data) == 0) return(NULL)
   
   data %>%
      mutate(across(
         .cols = -time,
         .fns = ~ {
            if (base_date %in% time) {
               (.x / .x[time == base_date]) * 100
            } else {
               # Fallback to first observation if base_date not found
               (.x / .x[1]) * 100
            }
         }
      )) %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 4)))
}

# =============================================================================
# DATA ACQUISITION - EUROSTAT
# =============================================================================

message("Fetching data from Eurostat...")

# 1. Building permits (quarterly)
building_permits <- get_eurostat(
   id = "sts_cobp_q",
   filters = c(list(
      indic_bt = "BPRM_DW",
      geo = "HR",
      s_adj = "SCA",
      cpa2_1 = "CPA_F41001_X_410014",
      freq = "Q",
      unit = "I21"
   ), time_filter),
   time_format = "date"
)

# 2. Gross fixed capital formation (quarterly)
gross_fixed_capital_formation <- get_eurostat(
   id = "namq_10_an6",
   filters = c(list(
      asset10 = "N11G",
      geo = "HR",
      s_adj = "SCA",
      freq = "Q",
      unit = "CLV_I20"
   ), time_filter),
   time_format = "date"
)

# 3. GDP (quarterly)
gdp <- get_eurostat(
   id = "namq_10_gdp",
   filters = c(list(
      geo = "HR",
      na_item = "B1GQ",
      s_adj = "SCA",
      unit = "CLV_I20",
      freq = "Q"
   ), time_filter),
   time_format = "date"
)

# 4. Household consumption (quarterly)
household_consumption <- get_eurostat(
   id = "namq_10_fcs",
   filters = c(list(
      geo = "HR",
      na_item = "P31_S14",
      s_adj = "SCA",
      freq = "Q",
      unit = "CLV_I20"
   ), time_filter),
   time_format = "date"
)

# 5. Wholesale and retail trade (monthly)
wholesale_retail_trade <- get_eurostat(
   id = "sts_trtu_m",
   filters = c(list(
      indic_bt = "VOL_SLS",
      geo = "HR",
      s_adj = "SCA",
      nace_r2 = c("G46", "G47"),
      freq = "M",
      unit = "I21"
   ), time_filter),
   time_format = "date"
)

# 6. Construction production (monthly)
construction_production <- get_eurostat(
   id = "sts_copr_m",
   filters = c(list(
      indic_bt = "PRD",
      geo = "HR",
      s_adj = "SCA",
      nace_r2 = "F",
      freq = "M",
      unit = "I21"
   ), time_filter),
   time_format = "date"
)

# 7. Industrial production (monthly)
industrial_production <- get_eurostat(
   id = "sts_inpr_m",
   filters = c(list(
      indic_bt = "PRD",
      geo = "HR",
      s_adj = "SCA",
      nace_r2 = "B-D",
      freq = "M",
      unit = "I21"
   ), time_filter),
   time_format = "date"
)

# 8. Business bankruptcy and registration (monthly)
business_bankruptcy_registration <- get_eurostat(
   id = "sts_rb_m",
   filters = c(list(
      indic_bt = c("REG", "BKRT"),
      geo = "HR",
      s_adj = "SCA",
      nace_r2 = "B-S_X_O_S94",
      freq = "M",
      unit = "I21"
   ), time_filter),
   time_format = "date"
)

# 9. Total production (monthly)
total_production <- get_eurostat(
   id = "sts_tot_prod_m",
   filters = c(list(
      indic_bt = "PRD",
      geo = "HR",
      s_adj = "SCA",
      nace_r2 = "B-N_X_K",
      freq = "M",
      unit = "I21"
   ), time_filter),
   time_format = "date"
)

# 10. Tourism - nights spent (monthly)
tourism <- get_eurostat(
   id = "tour_occ_nim",
   filters = c(list(
      geo = "HR",
      c_resid = "TOTAL",
      nace_r2 = "I551-I553",
      freq = "M",
      unit = "NR"
   ), time_filter),
   time_format = "date"
)

# 11. Balance of payments (monthly)
balance_of_payments <- get_eurostat(
   id = "bop_c6_m",
   filters = c(list(
      bop_item = c("G", "S"),
      sectpart = "S1",
      currency = "MIO_EUR",
      partner = "WRL_REST",
      geo = "HR",
      sector10 = "S1",
      stk_flow = c("CRE", "DEB"),
      freq = "M"
   ), time_filter),
   time_format = "date"
)

# 12. Unemployment (monthly, trend-cycle adjusted)
unemployment <- get_eurostat(
   id = "une_rt_m",
   filters = c(list(
      age = "TOTAL",
      geo = "HR",
      s_adj = "TC",
      sex = "T",
      freq = "M",
      unit = "THS_PER"
   ), time_filter),
   time_format = "date"
)

# =============================================================================
# DATA ACQUISITION - ECB (NPL)
# =============================================================================

message("Fetching NPL data from ECB...")

npl_data <- tryCatch({
   get_data("CBD2.Q.HR.W0.11._Z._Z.A.F.I3632._Z._Z._Z._Z._Z._Z.PC")
}, error = function(e) {
   message(paste("NPL data fetch failed:", e$message))
   NULL
})

# Clean NPL data - convert quarterly format to date
npl_clean <- NULL
if (!is.null(npl_data) && nrow(npl_data) > 0) {
   npl_clean <- npl_data %>%
      select(obstime, obsvalue) %>%
      filter(!is.na(obsvalue)) %>%
      mutate(
         year = as.numeric(substr(obstime, 1, 4)),
         quarter = as.numeric(substr(obstime, 7, 7)),
         month = (quarter - 1) * 3 + 1,
         time = as.Date(paste(year, month, "01", sep = "-"))
      ) %>%
      select(time, obsvalue) %>%
      rename(NPL = obsvalue) %>%
      arrange(time) %>%
      filter(!is.na(NPL))
}

# =============================================================================
# DATA CLEANING
# =============================================================================

message("Cleaning data...")

# 1. Building permits
building_permits_clean <- building_permits %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(Building_permits = values)

# 2. Gross fixed capital formation
gross_fixed_capital_formation_clean <- gross_fixed_capital_formation %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(investments = values)

# 3. GDP
gdp_clean <- gdp %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(GDP = values)

# 4. Household consumption
household_consumption_clean <- household_consumption %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(Household_consumption = values)

# 5. Wholesale and retail trade (pivot to wide format)
wholesale_retail_trade_clean <- wholesale_retail_trade %>%
   select(time, nace_r2, values) %>%
   pivot_wider(names_from = nace_r2, values_from = values) %>%
   rename(
      wholesale = G46,
      retail = G47
   ) %>%
   drop_na(wholesale, retail)

# 6. Construction
construction_production_clean <- construction_production %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(construction = values)

# 7. Industrial production
industrial_production_clean <- industrial_production %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(Industrial_production = values)

# 8. Business bankruptcy and registration (FIXED: using underscore consistently)
business_bankruptcy_registration_clean <- business_bankruptcy_registration %>%
   select(time, indic_bt, values) %>%
   pivot_wider(names_from = indic_bt, values_from = values) %>%
   rename(
      Registrations = REG,
      Bankruptcy_declarations = BKRT
   ) %>%
   drop_na(Registrations, Bankruptcy_declarations)

# 9. Total production
total_production_clean <- total_production %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(total_production = values)

# 10. Tourism
tourism_clean <- tourism %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(tourism = values)

# 11. Balance of payments (pivot to wide format)
balance_of_payments_clean <- balance_of_payments %>%
   select(time, bop_item, stk_flow, values) %>%
   mutate(indicator = paste(stk_flow, bop_item, sep = "_")) %>%
   select(time, indicator, values) %>%
   pivot_wider(names_from = indicator, values_from = values) %>%
   select(
      time,
      credit_goods = CRE_G,
      credit_services = CRE_S,
      debit_goods = DEB_G,
      debit_services = DEB_S
   ) %>%
   drop_na()

# 12. Unemployment
unemployment_clean <- unemployment %>%
   select(time, values) %>%
   filter(!is.na(values)) %>%
   rename(unemployment = values)

# =============================================================================
# SEASONAL ADJUSTMENT
# =============================================================================

message("Performing seasonal adjustment...")

# Seasonal adjustment of Balance of Payments
bop_start_date <- min(balance_of_payments_clean$time)

balance_of_payments_adjusted <- balance_of_payments_clean %>%
   mutate(across(
      .cols = -time,
      .fns = ~ adjust_series_x13(.x, bop_start_date, 12)
   ))

# Seasonal adjustment of tourism
tourism_start_date <- min(tourism_clean$time)
tourism_ts <- ts(tourism_clean$tourism, 
                 start = c(year(tourism_start_date), month(tourism_start_date)), 
                 frequency = 12)

tourism_adjusted <- tryCatch({
   tourism_model <- seas(tourism_ts)
   sa_series <- final(tourism_model)
   data.frame(
      time = tourism_clean$time,
      broj_nocenja = as.numeric(sa_series)
   )
}, error = function(e) {
   message(paste("Tourism seasonal adjustment failed:", e$message))
   data.frame(
      time = tourism_clean$time,
      broj_nocenja = tourism_clean$tourism
   )
})

# =============================================================================
# INDEXING (base = 100 for 2021-01-01)
# =============================================================================

message("Indexing data...")

indexed_balance_of_payments_adjusted <- index_data(balance_of_payments_adjusted, base_date)
indexed_tourism_adjusted <- index_data(tourism_adjusted, base_date)
indexed_unemployment <- index_data(unemployment_clean, base_date)

# =============================================================================
# TEMPORAL DISAGGREGATION (Quarterly to Monthly)
# =============================================================================

message("Performing temporal disaggregation...")

# Disaggregate NPL (quarterly) to monthly, then index
npl_monthly <- disaggregate_q_to_m(npl_clean, "NPL")
if (!is.null(npl_monthly)) {
   npl_monthly <- npl_monthly %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 4)))
   indexed_npl <- index_data(npl_monthly, base_date)
} else {
   indexed_npl <- NULL
}

# Disaggregate other quarterly data
building_permits_monthly <- disaggregate_q_to_m(building_permits_clean, "Building_permits")
if (!is.null(building_permits_monthly)) {
   building_permits_monthly <- building_permits_monthly %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 4)))
}

gross_fixed_capital_formation_monthly <- disaggregate_q_to_m(gross_fixed_capital_formation_clean, "investments")
if (!is.null(gross_fixed_capital_formation_monthly)) {
   gross_fixed_capital_formation_monthly <- gross_fixed_capital_formation_monthly %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 4)))
}

gdp_monthly <- disaggregate_q_to_m(gdp_clean, "GDP")
if (!is.null(gdp_monthly)) {
   gdp_monthly <- gdp_monthly %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 4)))
}

household_consumption_monthly <- disaggregate_q_to_m(household_consumption_clean, "Household_consumption")
if (!is.null(household_consumption_monthly)) {
   household_consumption_monthly <- household_consumption_monthly %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 4)))
}

# =============================================================================
# EXTERNAL DATA (Croatian-specific sources)
# =============================================================================

message("Loading external data sources...")

# EIZ - OVI index
ovi <- safe_read_excel("ovi.xlsx", "OVI index")

# Vehicle registrations
prvi_put_reg <- safe_read_excel("prvi_put_reg.xlsx", "Vehicle registrations")

# Number of insured persons
broj_osiguranika <- safe_read_excel("broj_osiguranika.xlsx", "Insured persons")

# =============================================================================
# SEASONAL ADJUSTMENT FOR EXTERNAL DATA
# =============================================================================

# Seasonal adjustment function for vehicle/insured persons data
adjust_external_series <- function(data, value_col) {
   if (is.null(data) || !value_col %in% names(data)) return(NULL)
   
   data_filtered <- data %>%
      select(time, all_of(value_col)) %>%
      filter(!is.na(.data[[value_col]]))
   
   if (nrow(data_filtered) < min_seasonal_obs) {
      message(paste("Insufficient data for seasonal adjustment of", value_col))
      return(data_filtered)
   }
   
   start_date <- min(data_filtered$time)
   start_year <- year(start_date)
   start_month <- month(start_date)
   
   ts_data <- ts(data_filtered[[value_col]], 
                 start = c(start_year, start_month), 
                 frequency = 12)
   
   adjusted <- tryCatch({
      model <- seas(ts_data,
                    outlier.types = "AO",
                    outlier.critical = 4.0,
                    regression.aictest = NULL)
      as.numeric(final(model))
   }, error = function(e) {
      message(paste("Seasonal adjustment failed for", value_col, ". Using original data."))
      data_filtered[[value_col]]
   })
   
   result <- data.frame(
      time = data_filtered$time,
      value = adjusted
   )
   names(result)[2] <- value_col
   return(result)
}

# Apply seasonal adjustment to vehicle registrations
personal_vehicles_adjusted <- NULL
freight_vehicles_adjusted <- NULL
if (!is.null(prvi_put_reg)) {
   personal_vehicles_adjusted <- adjust_external_series(prvi_put_reg, "Prvi put registrirana osobna vozila")
   freight_vehicles_adjusted <- adjust_external_series(prvi_put_reg, "Prvi put registrirana teretna vozila")
}

# Combine adjusted vehicle data
vehicle_registrations_adjusted <- NULL
if (!is.null(personal_vehicles_adjusted) && !is.null(freight_vehicles_adjusted)) {
   vehicle_registrations_adjusted <- full_join(personal_vehicles_adjusted, freight_vehicles_adjusted, by = "time")
}

# Apply seasonal adjustment to insured persons
insured_persons_adjusted <- NULL
if (!is.null(broj_osiguranika)) {
   insured_persons_adjusted <- adjust_external_series(broj_osiguranika, "Broj osiguranika")
}

# Index vehicle registrations
indexed_vehicle_registrations <- NULL
if (!is.null(vehicle_registrations_adjusted)) {
   indexed_vehicle_registrations <- index_data(vehicle_registrations_adjusted, base_date)
}

# Index insured persons
indexed_insured_persons <- NULL
if (!is.null(insured_persons_adjusted)) {
   indexed_insured_persons <- index_data(insured_persons_adjusted, base_date)
}

# =============================================================================
# HENDERSON FILTER (D12 TREND EXTRACTION)
# =============================================================================

message("Extracting D12 trends...")

# Quarterly variables (disaggregated to monthly)
d12_building_permits_monthly <- extract_d12_trend(building_permits_monthly, "Building_permits")
d12_gross_fixed_capital_formation_monthly <- extract_d12_trend(gross_fixed_capital_formation_monthly, "investments")
d12_gdp_monthly <- extract_d12_trend(gdp_monthly, "GDP")
d12_household_consumption_monthly <- extract_d12_trend(household_consumption_monthly, "Household_consumption")

# Monthly variables - Trade
d12_wholesale <- extract_d12_trend(
   wholesale_retail_trade_clean %>% select(time, wholesale), 
   "wholesale"
)
d12_retail <- extract_d12_trend(
   wholesale_retail_trade_clean %>% select(time, retail), 
   "retail"
)

# Monthly variables - Production
d12_construction_production_clean <- extract_d12_trend(construction_production_clean, "construction")
d12_industrial_production_clean <- extract_d12_trend(industrial_production_clean, "Industrial_production")
d12_total_production_clean <- extract_d12_trend(total_production_clean, "total_production")

# Business registrations and bankruptcies (FIXED: using underscore)
d12_registrations <- extract_d12_trend(
   business_bankruptcy_registration_clean %>% select(time, Registrations), 
   "Registrations"
)
d12_bankruptcy <- extract_d12_trend(
   business_bankruptcy_registration_clean %>% select(time, Bankruptcy_declarations), 
   "Bankruptcy_declarations"
)

# Tourism
d12_indexed_tourism_adjusted <- extract_d12_trend(indexed_tourism_adjusted, "broj_nocenja")

# Balance of payments components
d12_credit_goods <- extract_d12_trend(
   indexed_balance_of_payments_adjusted %>% select(time, credit_goods), 
   "credit_goods"
)
d12_credit_services <- extract_d12_trend(
   indexed_balance_of_payments_adjusted %>% select(time, credit_services), 
   "credit_services"
)
d12_debit_goods <- extract_d12_trend(
   indexed_balance_of_payments_adjusted %>% select(time, debit_goods), 
   "debit_goods"
)
d12_debit_services <- extract_d12_trend(
   indexed_balance_of_payments_adjusted %>% select(time, debit_services), 
   "debit_services"
)

# Unemployment (already trend-cycle adjusted, just rename)
unemployment_tc <- indexed_unemployment %>%
   rename(d12_unemployment = unemployment)

# Vehicle registrations
d12_personal_vehicles <- NULL
d12_freight_vehicles <- NULL
if (!is.null(indexed_vehicle_registrations)) {
   personal_vehicles_only <- indexed_vehicle_registrations %>% 
      select(time, `Prvi put registrirana osobna vozila`) %>%
      filter(!is.na(`Prvi put registrirana osobna vozila`))
   d12_personal_vehicles <- extract_d12_trend(personal_vehicles_only, "Prvi put registrirana osobna vozila")
   
   freight_vehicles_only <- indexed_vehicle_registrations %>% 
      select(time, `Prvi put registrirana teretna vozila`) %>%
      filter(!is.na(`Prvi put registrirana teretna vozila`))
   d12_freight_vehicles <- extract_d12_trend(freight_vehicles_only, "Prvi put registrirana teretna vozila")
}

# Insured persons
d12_insured_persons <- NULL
if (!is.null(indexed_insured_persons)) {
   d12_insured_persons <- extract_d12_trend(
      indexed_insured_persons %>% filter(!is.na(`Broj osiguranika`)),
      "Broj osiguranika"
   )
}

# NPL
d12_npl <- NULL
if (!is.null(indexed_npl)) {
   d12_npl <- extract_d12_trend(
      indexed_npl %>% filter(!is.na(NPL)),
      "NPL"
   )
}

# =============================================================================
# COMBINE ALL D12 TRENDS
# =============================================================================

message("Combining D12 trends...")

all_d12_trends <- list(
   d12_building_permits_monthly,
   d12_gross_fixed_capital_formation_monthly,
   d12_gdp_monthly,
   d12_household_consumption_monthly,
   d12_wholesale,
   d12_retail,
   d12_construction_production_clean,
   d12_industrial_production_clean,
   d12_registrations,
   d12_bankruptcy,
   d12_total_production_clean,
   d12_indexed_tourism_adjusted,
   d12_credit_goods,
   d12_credit_services,
   d12_debit_goods,
   d12_debit_services,
   unemployment_tc,
   d12_personal_vehicles,
   d12_freight_vehicles,
   d12_insured_persons,
   d12_npl
)

# Remove NULL entries
all_d12_trends <- Filter(Negate(is.null), all_d12_trends)

# Merge all d12 trends
d12_combined <- Reduce(
   function(x, y) full_join(x, y, by = "time"), 
   all_d12_trends
)

# Merge with OVI index
all_dfs_list <- list(d12_combined)
if (!is.null(ovi)) {
   all_dfs_list <- append(all_dfs_list, list(ovi))
}

merged_monthly_data <- Reduce(
   function(x, y) full_join(x, y, by = "time"), 
   all_dfs_list
)

# Sort by time
final_data <- merged_monthly_data %>%
   arrange(time)

# =============================================================================
# VARIABLE GROUPS DEFINITION (FIXED: using underscore consistently)
# =============================================================================

leading_vars_original <- c(
   "d12_Building_permits", 
   "d12_Registrations", 
   "OVI",
   "d12_Prvi put registrirana osobna vozila",
   "d12_Prvi put registrirana teretna vozila"
)

supply_vars_original <- c(
   "d12_GDP", 
   "d12_Industrial_production", 
   "d12_construction", 
   "d12_total_production", 
   "d12_broj_nocenja",
   "d12_Broj osiguranika"
)

demand_vars_original <- c(
   "d12_retail", 
   "d12_wholesale", 
   "d12_Household_consumption", 
   "d12_investments"
)

external_vars_original <- c(
   "d12_credit_goods", 
   "d12_credit_services", 
   "d12_debit_goods", 
   "d12_debit_services"
)

lagging_vars_original <- c(
   "d12_Bankruptcy_declarations",
   "d12_unemployment",
   "d12_NPL"
)

# =============================================================================
# PROCESSING FUNCTION FOR VARIABLE GROUPS
# =============================================================================

process_group <- function(var_list, group_name) {
   # Select only the variables in this group from final_data
   group_data <- final_data %>%
      select(time, any_of(var_list)) %>%
      arrange(time) %>%
      drop_na()
   
   if (nrow(group_data) == 0) {
      message(paste("No data available for group:", group_name))
      return(NULL)
   }
   
   # Check if we have enough data points
   if (nrow(group_data) < min_observations) {
      message(paste("Insufficient data for group:", group_name, "- need at least", min_observations, "months"))
      return(NULL)
   }
   
   # Check if we have any variables besides time
   y_group <- group_data %>% select(-time)
   if (ncol(y_group) == 0) {
      message(paste("No variables available for group:", group_name))
      return(NULL)
   }
   
   # HP filter decomposition
   cycle_data_group <- tryCatch({
      ytrend_group <- hp2(y_group, lambda = hp_lambda)
      ycycle_group <- ((y_group - ytrend_group) / ytrend_group) * 100
      bind_cols(time = group_data$time, as.data.frame(ycycle_group))
   }, error = function(e) {
      message(paste("HP filter failed for group:", group_name, "-", e$message))
      return(NULL)
   })
   
   if (is.null(cycle_data_group)) return(NULL)
   
   # Standardize cycle (z-scores)
   standardized_cycle_group <- cycle_data_group %>%
      mutate(across(.cols = -time, .fns = ~ as.numeric(scale(.x)))) %>%
      slice(-1)  # Remove first row to match MoM
   
   # Rename function for Croatian output
   safe_rename_cycle <- function(df) {
      rename_map <- c(
         "d12_Building_permits" = "Građevinske dozvole",
         "d12_investments" = "Investicije",
         "d12_GDP" = "BDP",
         "d12_Household_consumption" = "Potrošnja kućanstava",
         "d12_wholesale" = "Veleprodaja",
         "d12_retail" = "Trgovina na malo",
         "d12_construction" = "Građevinarstvo",
         "d12_Industrial_production" = "Industrijska proizvodnja",
         "d12_Registrations" = "Registracija novih poduzeća",
         "d12_Bankruptcy_declarations" = "Stečajne prijave",
         "d12_total_production" = "Ukupna proizvodnja",
         "d12_broj_nocenja" = "Broj noćenja",
         "OVI" = "OVI (EIZ)",
         "d12_credit_goods" = "Izvoz dobara",
         "d12_credit_services" = "Izvoz usluga",
         "d12_debit_goods" = "Uvoz dobara",
         "d12_debit_services" = "Uvoz usluga",
         "d12_unemployment" = "Nezaposlenost",
         "d12_Prvi put registrirana osobna vozila" = "Novo registrirana osobna vozila (DZS)",
         "d12_Prvi put registrirana teretna vozila" = "Novo registrirana teretna vozila (DZS)",
         "d12_Broj osiguranika" = "Broj osiguranika (HZMO)",
         "d12_NPL" = "Neprihodonosni krediti (ECB)"
      )
      
      for (old_name in names(rename_map)) {
         if (old_name %in% names(df)) {
            df <- df %>% rename(!!rename_map[old_name] := !!old_name)
         }
      }
      return(df)
   }
   
   standardized_cycle_group <- safe_rename_cycle(standardized_cycle_group)
   
   # Month-over-month changes (FIXED: protection against division by zero)
   mom_data_group <- group_data %>%
      arrange(time) %>%
      mutate(across(.cols = -time, 
                    .fns = ~ {
                       prev <- lag(.x)
                       ifelse(abs(prev) < 1e-10, NA_real_, ((.x - prev) / abs(prev)) * 100)
                    })) %>%
      drop_na()
   
   # Standardize MoM (z-scores)
   standardized_mom_group <- mom_data_group %>%
      mutate(across(.cols = -time, .fns = ~ as.numeric(scale(.x))))
   
   standardized_mom_group <- safe_rename_cycle(standardized_mom_group)
   
   # Invert counter-cyclical indicators (higher values = worse economy)
   counter_cyclical <- c("Stečajne prijave", "Nezaposlenost", "Neprihodonosni krediti (ECB)")
   
   for (indicator in counter_cyclical) {
      if (indicator %in% names(standardized_mom_group)) {
         standardized_mom_group <- standardized_mom_group %>%
            mutate(!!indicator := -get(indicator))
         standardized_cycle_group <- standardized_cycle_group %>%
            mutate(!!indicator := -get(indicator))
      }
   }
   
   # Round values
   standardized_cycle_group <- standardized_cycle_group %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 5)))
   standardized_mom_group <- standardized_mom_group %>%
      mutate(across(.cols = -time, .fns = ~ round(.x, 5)))
   
   # Pivot to long format for Flourish
   mom_long <- standardized_mom_group %>%
      pivot_longer(cols = -time, names_to = "variable", values_to = "MoM")
   
   cycle_long <- standardized_cycle_group %>%
      pivot_longer(cols = -time, names_to = "variable", values_to = "Cycle")
   
   # Combine MoM and Cycle
   combined_group <- full_join(mom_long, cycle_long, by = c("time", "variable"))
   
   # Format for output
   combined_group <- combined_group %>%
      mutate(time = format(time, "%B %Y")) %>%
      rename(
         "Mjesečna promjena (%)" = MoM,
         "Odstupanje od trenda (%)" = Cycle,
         "Varijabla" = variable
      ) %>%
      mutate(across(.cols = -c("time", "Varijabla"), .fns = ~ round(.x, 3)))
   
   return(combined_group)
}

# =============================================================================
# PROCESS EACH GROUP
# =============================================================================

message("Processing variable groups...")

leading_data <- process_group(leading_vars_original, "Leading Indicators")
supply_data <- process_group(supply_vars_original, "Supply/Production")
demand_data <- process_group(demand_vars_original, "Demand/Consumption")
external_data <- process_group(external_vars_original, "External Trade")
lagging_data <- process_group(lagging_vars_original, "Lagging Indicators")

# =============================================================================
# SAVE OUTPUT FILES
# =============================================================================

message("Saving output files...")

if (!is.null(leading_data)) {
   write.xlsx(leading_data, file = "1_vodeci_indikatori.xlsx")
   message("  - 1_vodeci_indikatori.xlsx")
}

if (!is.null(supply_data)) {
   write.xlsx(supply_data, file = "2_podudarni_proizvodnja.xlsx")
   message("  - 2_podudarni_proizvodnja.xlsx")
}

if (!is.null(demand_data)) {
   write.xlsx(demand_data, file = "3_podudarni_potrosnja_trgovina.xlsx")
   message("  - 3_podudarni_potrosnja_trgovina.xlsx")
}

if (!is.null(external_data)) {
   write.xlsx(external_data, file = "4_vanjska_trgovina.xlsx")
   message("  - 4_vanjska_trgovina.xlsx")
}

if (!is.null(lagging_data)) {
   write.xlsx(lagging_data, file = "5_kasni_indikatori_stecaj.xlsx")
   message("  - 5_kasni_indikatori_stecaj.xlsx")
}

# Combine all groups for the master file
all_groups <- list(leading_data, supply_data, demand_data, external_data, lagging_data)
all_groups <- Filter(Negate(is.null), all_groups)

if (length(all_groups) > 0) {
   combined_data <- bind_rows(all_groups)
   write.xlsx(combined_data, file = "combined_standardized_MoM_and_Cycle_Croatia.xlsx")
   message("  - combined_standardized_MoM_and_Cycle_Croatia.xlsx")
}

message("\n========== PROCESSING COMPLETE ==========")
message(paste("Total variables processed:", length(unique(combined_data$Varijabla))))
message(paste("Date range:", min(combined_data$time), "to", max(combined_data$time)))
