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

# Define all Euro Area countries (using correct Eurostat codes)
euro_countries <- c("AT", "BE", "CY", "EE", "FI", "FR", "DE", "EL", "IE", 
                    "IT", "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES")

country_names <- c("Austria", "Belgium", "Cyprus", "Estonia", "Finland", 
                   "France", "Germany", "Greece", "Ireland", "Italy", 
                   "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", 
                   "Portugal", "Slovakia", "Slovenia", "Spain")

# Set time filter for all Eurostat data (from 2015-01 onwards)
time_filter <- list(sinceTimePeriod = "2015-01")

# Base date for indexing (consistent with Croatia script)
base_date <- as.Date("2021-01-01")

# HP filter lambda for monthly data (Ravn-Uhlig rule: 1600 * 12^4 = 129600)
hp_lambda <- 129600

# Minimum observations required for processing
min_observations <- 24
min_seasonal_obs <- 36

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Function to safely get Eurostat data
safe_get_eurostat <- function(id, filters, country) {
   tryCatch({
      filters$geo <- country
      data <- get_eurostat(id = id, filters = filters)
      if (!is.null(data) && nrow(data) > 0) {
         if ("time" %in% names(data)) {
            data$time <- as.Date(data$time)
         }
         return(data)
      }
      return(NULL)
   }, error = function(e) {
      message(paste("Error fetching", id, "for", country, ":", e$message))
      return(NULL)
   })
}

# Function to clean and rename data
clean_data <- function(data, new_name) {
   if (is.null(data)) return(NULL)
   data %>%
      select(time, values) %>%
      filter(!is.na(values)) %>%
      rename(!!new_name := values)
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

# Function to index data with base date (FIXED: consistent with Croatia)
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
# MAIN PROCESSING FUNCTION FOR EACH COUNTRY
# =============================================================================

process_country <- function(country_code, country_name, current_index = NULL, total_countries = NULL) {
   
   # Progress indicator
   if (!is.null(current_index) && !is.null(total_countries)) {
      progress <- sprintf("[%d/%d]", current_index, total_countries)
      message(paste("\n", progress, "Processing", country_name, "(", country_code, ")"))
   } else {
      message(paste("\n========== Processing", country_name, "(", country_code, ") =========="))
   }
   
   # =========================================================================
   # DATA ACQUISITION
   # =========================================================================
   
   # 1. Building permits (quarterly)
   building_permits <- safe_get_eurostat(
      id = "sts_cobp_q",
      filters = c(list(
         indic_bt = "BPRM_DW", 
         s_adj = "SCA", 
         cpa2_1 = "CPA_F41001_X_410014", 
         freq = "Q", 
         unit = "I21"
      ), time_filter),
      country = country_code
   )
   
   # 2. Gross fixed capital formation (quarterly)
   gfcf <- safe_get_eurostat(
      id = "namq_10_an6",
      filters = c(list(
         asset10 = "N11G", 
         s_adj = "SCA", 
         freq = "Q", 
         unit = "CLV_I20"
      ), time_filter),
      country = country_code
   )
   
   # 3. GDP (quarterly)
   gdp <- safe_get_eurostat(
      id = "namq_10_gdp",
      filters = c(list(
         na_item = "B1GQ", 
         s_adj = "SCA", 
         unit = "CLV_I20", 
         freq = "Q"
      ), time_filter),
      country = country_code
   )
   
   # 4. Household consumption (quarterly)
   hh_cons <- safe_get_eurostat(
      id = "namq_10_fcs",
      filters = c(list(
         na_item = "P31_S14", 
         s_adj = "SCA", 
         freq = "Q", 
         unit = "CLV_I20"
      ), time_filter),
      country = country_code
   )
   
   # 5. Wholesale and retail trade (monthly)
   trade <- safe_get_eurostat(
      id = "sts_trtu_m",
      filters = c(list(
         indic_bt = "VOL_SLS", 
         s_adj = "SCA", 
         nace_r2 = c("G46", "G47"), 
         freq = "M", 
         unit = "I21"
      ), time_filter),
      country = country_code
   )
   
   # 6. Construction (monthly)
   construction <- safe_get_eurostat(
      id = "sts_copr_m",
      filters = c(list(
         indic_bt = "PRD", 
         s_adj = "SCA", 
         nace_r2 = "F", 
         freq = "M", 
         unit = "I21"
      ), time_filter),
      country = country_code
   )
   
   # 7. Industrial production (monthly)
   industry <- safe_get_eurostat(
      id = "sts_inpr_m",
      filters = c(list(
         indic_bt = "PRD", 
         s_adj = "SCA", 
         nace_r2 = "B-D", 
         freq = "M", 
         unit = "I21"
      ), time_filter),
      country = country_code
   )
   
   # 8. Business bankruptcy and registration (monthly)
   business_reg <- safe_get_eurostat(
      id = "sts_rb_m",
      filters = c(list(
         indic_bt = c("REG", "BKRT"), 
         s_adj = "SCA", 
         nace_r2 = "B-S_X_O_S94", 
         freq = "M", 
         unit = "I21"
      ), time_filter),
      country = country_code
   )
   
   # 9. Total production (monthly)
   total_prod <- safe_get_eurostat(
      id = "sts_tot_prod_m",
      filters = c(list(
         indic_bt = "PRD", 
         s_adj = "SCA", 
         nace_r2 = "B-N_X_K", 
         freq = "M", 
         unit = "I21"
      ), time_filter),
      country = country_code
   )
   
   # 10. Tourism (monthly)
   tourism <- safe_get_eurostat(
      id = "tour_occ_nim",
      filters = c(list(
         c_resid = "TOTAL", 
         nace_r2 = "I551-I553", 
         freq = "M", 
         unit = "NR"
      ), time_filter),
      country = country_code
   )
   
   # 11. Balance of payments (monthly)
   bop <- safe_get_eurostat(
      id = "bop_c6_m",
      filters = c(list(
         bop_item = c("G", "S"), 
         sectpart = "S1", 
         currency = "MIO_EUR", 
         partner = "WRL_REST", 
         sector10 = "S1", 
         stk_flow = c("CRE", "DEB"), 
         freq = "M"
      ), time_filter),
      country = country_code
   )
   
   # 12. Unemployment (monthly)
   unemployment <- safe_get_eurostat(
      id = "une_rt_m",
      filters = c(list(
         age = "TOTAL", 
         s_adj = "TC", 
         sex = "T", 
         freq = "M", 
         unit = "THS_PER"
      ), time_filter),
      country = country_code
   )
   
   # 13. Non-performing loans (NPL) from ECB
   npl_data <- tryCatch({
      get_data(paste0("CBD2.Q.", country_code, ".W0.11._Z._Z.A.F.I3632._Z._Z._Z._Z._Z._Z.PC"))
   }, error = function(e) {
      message(paste("NPL data not available for", country_name))
      return(NULL)
   })
   
   # =========================================================================
   # DATA CLEANING
   # =========================================================================
   
   # Clean NPL data if available
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
   
   # Clean all standard data
   building_permits_clean <- clean_data(building_permits, "Building_permits")
   gfcf_clean <- clean_data(gfcf, "investments")
   gdp_clean <- clean_data(gdp, "GDP")
   hh_cons_clean <- clean_data(hh_cons, "Household_consumption")
   construction_clean <- clean_data(construction, "construction")
   industry_clean <- clean_data(industry, "Industrial_production")
   total_prod_clean <- clean_data(total_prod, "total_production")
   tourism_clean <- clean_data(tourism, "tourism")
   unemployment_clean <- clean_data(unemployment, "unemployment")
   
   # Special transformations for trade
   trade_clean <- NULL
   if (!is.null(trade)) {
      trade_clean <- tryCatch({
         trade %>%
            select(time, nace_r2, values) %>%
            pivot_wider(names_from = nace_r2, values_from = values) %>%
            rename(wholesale = G46, retail = G47) %>%
            drop_na(wholesale, retail)
      }, error = function(e) {
         message(paste("Trade data transformation failed for", country_name))
         NULL
      })
   }
   
   # Special transformations for business registration/bankruptcy (FIXED: using underscore)
   business_reg_clean <- NULL
   if (!is.null(business_reg)) {
      business_reg_clean <- tryCatch({
         business_reg %>%
            select(time, indic_bt, values) %>%
            pivot_wider(names_from = indic_bt, values_from = values) %>%
            rename(Registrations = REG, Bankruptcy_declarations = BKRT) %>%
            drop_na()
      }, error = function(e) {
         message(paste("Business registration data transformation failed for", country_name))
         NULL
      })
   }
   
   # Balance of payments transformations
   bop_clean <- NULL
   if (!is.null(bop)) {
      bop_clean <- tryCatch({
         bop %>%
            select(time, bop_item, stk_flow, values) %>%
            mutate(category = paste(stk_flow, bop_item, sep = "_")) %>%
            select(time, category, values) %>%
            pivot_wider(names_from = category, values_from = values) %>%
            rename(
               credit_goods = CRE_G, 
               credit_services = CRE_S,
               debit_goods = DEB_G,
               debit_services = DEB_S
            ) %>%
            drop_na()
      }, error = function(e) {
         message(paste("Balance of payments transformation failed for", country_name))
         NULL
      })
   }
   
   # =========================================================================
   # TEMPORAL DISAGGREGATION
   # =========================================================================
   
   building_permits_monthly <- disaggregate_q_to_m(building_permits_clean, "Building_permits")
   gfcf_monthly <- disaggregate_q_to_m(gfcf_clean, "investments")
   gdp_monthly <- disaggregate_q_to_m(gdp_clean, "GDP")
   hh_cons_monthly <- disaggregate_q_to_m(hh_cons_clean, "Household_consumption")
   
   # =========================================================================
   # INDEXING AND SEASONAL ADJUSTMENT
   # =========================================================================
   
   # Index and adjust tourism data (FIXED: using consistent base_date)
   indexed_tourism_adjusted <- NULL
   if (!is.null(tourism_clean) && nrow(tourism_clean) > 0) {
      indexed_tourism <- index_data(tourism_clean, base_date)
      
      if (!is.null(indexed_tourism) && nrow(indexed_tourism) >= min_seasonal_obs) {
         start_date <- min(indexed_tourism$time)
         adjusted_values <- adjust_series_x13(indexed_tourism$tourism, start_date, frequency = 12)
         indexed_tourism_adjusted <- data.frame(
            time = indexed_tourism$time,
            broj_nocenja = adjusted_values
         )
      } else if (!is.null(indexed_tourism)) {
         indexed_tourism_adjusted <- indexed_tourism %>%
            rename(broj_nocenja = tourism)
      }
   }
   
   # Index and adjust balance of payments data (FIXED: using consistent base_date)
   indexed_bop_adjusted <- NULL
   if (!is.null(bop_clean) && nrow(bop_clean) > 0) {
      indexed_bop <- index_data(bop_clean, base_date)
      
      if (!is.null(indexed_bop) && nrow(indexed_bop) >= min_seasonal_obs) {
         start_date <- min(indexed_bop$time)
         
         cg_adj <- adjust_series_x13(indexed_bop$credit_goods, start_date, 12)
         cs_adj <- adjust_series_x13(indexed_bop$credit_services, start_date, 12)
         dg_adj <- adjust_series_x13(indexed_bop$debit_goods, start_date, 12)
         ds_adj <- adjust_series_x13(indexed_bop$debit_services, start_date, 12)
         
         indexed_bop_adjusted <- data.frame(
            time = indexed_bop$time,
            credit_goods = cg_adj,
            credit_services = cs_adj,
            debit_goods = dg_adj,
            debit_services = ds_adj
         )
      } else if (!is.null(indexed_bop)) {
         indexed_bop_adjusted <- indexed_bop
      }
   }
   
   # Index NPL data (FIXED: using consistent base_date)
   indexed_npl <- NULL
   if (!is.null(npl_clean) && nrow(npl_clean) > 0) {
      indexed_npl <- index_data(npl_clean, base_date)
   }
   
   # =========================================================================
   # D12 TREND EXTRACTION
   # =========================================================================
   
   # Quarterly variables (disaggregated to monthly)
   d12_building_permits <- extract_d12_trend(building_permits_monthly, "Building_permits")
   d12_gfcf <- extract_d12_trend(gfcf_monthly, "investments")
   d12_gdp <- extract_d12_trend(gdp_monthly, "GDP")
   d12_hh_cons <- extract_d12_trend(hh_cons_monthly, "Household_consumption")
   
   # Trade
   d12_wholesale <- NULL
   d12_retail <- NULL
   if (!is.null(trade_clean)) {
      wholesale_only <- trade_clean %>% select(time, wholesale)
      retail_only <- trade_clean %>% select(time, retail)
      d12_wholesale <- extract_d12_trend(wholesale_only, "wholesale")
      d12_retail <- extract_d12_trend(retail_only, "retail")
   }
   
   # Production
   d12_construction <- extract_d12_trend(construction_clean, "construction")
   d12_industry <- extract_d12_trend(industry_clean, "Industrial_production")
   d12_total_prod <- extract_d12_trend(total_prod_clean, "total_production")
   
   # Business registration (FIXED: using underscore)
   d12_registrations <- NULL
   d12_bankruptcy <- NULL
   if (!is.null(business_reg_clean)) {
      if ("Registrations" %in% names(business_reg_clean)) {
         reg_only <- business_reg_clean %>% select(time, Registrations)
         d12_registrations <- extract_d12_trend(reg_only, "Registrations")
      }
      if ("Bankruptcy_declarations" %in% names(business_reg_clean)) {
         bank_only <- business_reg_clean %>% select(time, Bankruptcy_declarations)
         d12_bankruptcy <- extract_d12_trend(bank_only, "Bankruptcy_declarations")
      }
   }
   
   # Tourism
   d12_tourism <- extract_d12_trend(indexed_tourism_adjusted, "broj_nocenja")
   
   # Balance of payments
   d12_credit_goods <- NULL
   d12_credit_services <- NULL
   d12_debit_goods <- NULL
   d12_debit_services <- NULL
   if (!is.null(indexed_bop_adjusted)) {
      cg <- indexed_bop_adjusted %>% select(time, credit_goods)
      cs <- indexed_bop_adjusted %>% select(time, credit_services)
      dg <- indexed_bop_adjusted %>% select(time, debit_goods)
      ds <- indexed_bop_adjusted %>% select(time, debit_services)
      
      d12_credit_goods <- extract_d12_trend(cg, "credit_goods")
      d12_credit_services <- extract_d12_trend(cs, "credit_services")
      d12_debit_goods <- extract_d12_trend(dg, "debit_goods")
      d12_debit_services <- extract_d12_trend(ds, "debit_services")
   }
   
   # Unemployment (already trend-cycle adjusted)
   unemployment_tc <- NULL
   if (!is.null(unemployment_clean)) {
      unemployment_tc <- unemployment_clean %>%
         rename(d12_unemployment = unemployment)
   }
   
   # NPL
   d12_npl <- extract_d12_trend(indexed_npl, "NPL")
   
   # =========================================================================
   # COMBINE ALL D12 TRENDS
   # =========================================================================
   
   all_d12 <- list(
      d12_building_permits, 
      d12_gfcf, 
      d12_gdp, 
      d12_hh_cons,
      d12_wholesale, 
      d12_retail, 
      d12_construction, 
      d12_industry,
      d12_registrations, 
      d12_bankruptcy, 
      d12_total_prod, 
      d12_tourism,
      d12_credit_goods, 
      d12_credit_services, 
      d12_debit_goods, 
      d12_debit_services,
      unemployment_tc,
      d12_npl
   )
   
   # Remove NULL entries
   all_d12 <- Filter(Negate(is.null), all_d12)
   
   if (length(all_d12) == 0) {
      message(paste("No D12 trends available for", country_name))
      return(NULL)
   }
   
   # Merge all D12 trends
   d12_combined <- Reduce(function(x, y) full_join(x, y, by = "time"), all_d12)
   
   # Sort by time
   final_data <- d12_combined %>% 
      arrange(time)
   
   # =========================================================================
   # VARIABLE GROUPS DEFINITION (FIXED: using underscore consistently)
   # =========================================================================
   
   leading_vars_original <- c(
      "d12_Building_permits", 
      "d12_Registrations"
   )
   
   supply_vars_original <- c(
      "d12_GDP", 
      "d12_Industrial_production", 
      "d12_construction", 
      "d12_total_production", 
      "d12_broj_nocenja"
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
   
   # =========================================================================
   # PROCESSING FUNCTION FOR VARIABLE GROUPS
   # =========================================================================
   
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
            "d12_credit_goods" = "Izvoz dobara",
            "d12_credit_services" = "Izvoz usluga",
            "d12_debit_goods" = "Uvoz dobara",
            "d12_debit_services" = "Uvoz usluga",
            "d12_unemployment" = "Nezaposlenost",
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
   
   # =========================================================================
   # PROCESS EACH GROUP
   # =========================================================================
   
   leading_data <- process_group(leading_vars_original, "Leading Indicators")
   supply_data <- process_group(supply_vars_original, "Supply/Production")
   demand_data <- process_group(demand_vars_original, "Demand/Consumption")
   external_data <- process_group(external_vars_original, "External Trade")
   lagging_data <- process_group(lagging_vars_original, "Lagging Indicators")
   
   # Combine all groups for the final output
   all_groups <- list(leading_data, supply_data, demand_data, external_data, lagging_data)
   all_groups <- Filter(Negate(is.null), all_groups)
   
   if (length(all_groups) == 0) {
      message(paste("No groups processed successfully for", country_name))
      return(NULL)
   }
   
   combined_data <- bind_rows(all_groups)
   
   message(paste("Successfully processed", country_name, "with", 
                 nrow(combined_data), "observations"))
   
   return(list(
      combined = combined_data,
      leading = leading_data,
      supply = supply_data,
      demand = demand_data,
      external = external_data,
      lagging = lagging_data
   ))
}

# =============================================================================
# PROCESS ALL COUNTRIES
# =============================================================================

message("\n========== STARTING EURO AREA BUSINESS CYCLE ANALYSIS ==========")
message(paste("Processing", length(euro_countries), "countries..."))

all_results <- list()

for (i in seq_along(euro_countries)) {
   result <- process_country(
      euro_countries[i], 
      country_names[i],
      current_index = i,
      total_countries = length(euro_countries)
   )
   if (!is.null(result)) {
      all_results[[country_names[i]]] <- result
   }
   Sys.sleep(1)  # Be polite to Eurostat servers
}

# =============================================================================
# SAVE RESULTS
# =============================================================================

if (length(all_results) > 0) {
   
   message("\n========== SAVING OUTPUT FILES ==========")
   
   # Save individual country files with separate group sheets
   for (country in names(all_results)) {
      country_data <- all_results[[country]]
      filename <- paste0("Business_Cycle_", gsub(" ", "_", country), ".xlsx")
      
      # Create workbook with separate sheets for each group
      wb <- createWorkbook()
      
      if (!is.null(country_data$leading)) {
         addWorksheet(wb, "1_vodeci_indikatori")
         writeData(wb, "1_vodeci_indikatori", country_data$leading)
      }
      
      if (!is.null(country_data$supply)) {
         addWorksheet(wb, "2_podudarni_proizvodnja")
         writeData(wb, "2_podudarni_proizvodnja", country_data$supply)
      }
      
      if (!is.null(country_data$demand)) {
         addWorksheet(wb, "3_podudarni_potrosnja_trgovina")
         writeData(wb, "3_podudarni_potrosnja_trgovina", country_data$demand)
      }
      
      if (!is.null(country_data$external)) {
         addWorksheet(wb, "4_vanjska_trgovina")
         writeData(wb, "4_vanjska_trgovina", country_data$external)
      }
      
      if (!is.null(country_data$lagging)) {
         addWorksheet(wb, "5_kasni_indikatori_stecaj")
         writeData(wb, "5_kasni_indikatori_stecaj", country_data$lagging)
      }
      
      saveWorkbook(wb, filename, overwrite = TRUE)
      message(paste("  -", filename))
   }
   
   # Combine all countries into one master file
   all_combined <- lapply(names(all_results), function(country) {
      all_results[[country]]$combined
   })
   names(all_combined) <- names(all_results)
   
   final_combined <- bind_rows(all_combined, .id = "Country")
   write.xlsx(final_combined, file = "Euro_Area_Business_Cycles_All_Countries.xlsx")
   message("  - Euro_Area_Business_Cycles_All_Countries.xlsx (combined)")
   
   message("\n========== PROCESSING COMPLETE ==========")
   message(paste("Processed", length(all_results), "countries successfully"))
   
} else {
   message("No countries were successfully processed")
}

# =============================================================================
# SUMMARY STATISTICS
# =============================================================================

if (length(all_results) > 0) {
   summary_df <- data.frame(
      Country = names(all_results),
      Observations = sapply(all_results, function(x) nrow(x$combined)),
      Variables = sapply(all_results, function(x) length(unique(x$combined$Varijabla))),
      Date_Start = sapply(all_results, function(x) head(x$combined$time, 1)),
      Date_End = sapply(all_results, function(x) tail(x$combined$time, 1))
   )
   
   message("\n========== PROCESSING SUMMARY ==========")
   print(summary_df)
   write.xlsx(summary_df, file = "Processing_Summary.xlsx")
   message("  - Processing_Summary.xlsx")
}
