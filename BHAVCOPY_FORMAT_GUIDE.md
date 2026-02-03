# Bhavcopy Data Format Guide

## Overview
The bhavcopy (Bhav = Price, Copy = Data snapshot) is NSE's daily F&O market data. When you upload a user bhavcopy file, it must be in **CSV format** with specific columns that the code filters and processes.

---

## Expected CSV Format

The bhavcopy CSV file should have the following columns:

| Column Name | Data Type | Description | Example |
|---|---|---|---|
| `TckrSymb` | String | Ticker Symbol | NIFTY |
| `Symbol` | String | Full symbol identifier | NIFTY (used interchangeably with TckrSymb) |
| `Instrument` | String | Type of financial instrument | OPTIDX, FUTIDX |
| `FinInstrmTp` | String | Financial Instrument Type | IDO (Index Option), IDF (Index Futures), STF, STO |
| `XpryDt` | Date/String | Expiry Date | 2026-01-29, 29-JAN-2026 (converted to datetime) |
| `StrkPric` | Float | Strike Price | 25000, 25050, 25100 |
| `OptnTp` | String | Option Type | CE (Call) or PE (Put) |
| `ClsPric` | Float | Closing Price (Premium) | 150.50, 75.25 |
| `OpnIntrst` | Integer | Open Interest | 1000000, 500000 |

### Additional Columns (may exist but not required)
- `OpenPrc`, `HighPrc`, `LowPrc`, `TtlTrdgVlm`, `TtlTrdVal`, etc.

---

## Data Processing Flow

### 1️⃣ **Loading the CSV**
```python
bhavcopy_data = pd.read_csv(file_path)
```
The code simply reads the CSV file into a pandas DataFrame.

### 2️⃣ **Extracting Weekly Options Data**

**Function:** `extract_weekly_options_from_bhavcopy()`

**Filter Logic:**
```
Filter 1: Symbol == "NIFTY"
Filter 2: Instrument == "OPTIDX"
Filter 3: Expiry Date is a Wednesday (day_of_week == 2)
```

**What it does:**
- Extracts all NIFTY option contracts from the bhavcopy
- Identifies weekly options (they expire on Wednesdays)
- Returns a DataFrame with columns: `XpryDt`, `StrkPric`, `OptnTp`, `ClsPric`, `OpnIntrst`

**Output:** DataFrame with all weekly CE and PE contracts for a specific Wednesday expiry

**Example:**
```
   XpryDt  StrkPric OptnTp  ClsPric  OpnIntrst
0  2026-01-29   25000     CE    250.5    500000
1  2026-01-29   25000     PE     75.2    300000
2  2026-01-29   25050     CE    225.3    450000
3  2026-01-29   25050     PE    100.1    400000
...
```

### 3️⃣ **Extracting Spot Price from Futures**

**Function:** `extract_spot_price_from_futures()`

**Filter Logic:**
```
Filter 1: Symbol == "NIFTY"
Filter 2: Instrument == "FUTIDX"
```

**What it does:**
- Extracts all NIFTY futures contracts
- Sorts by expiry date
- Takes the **closest expiry** (nearest month futures)
- Extracts the **closing price** as the spot price

**Why this works:**
- The nearest month futures closing price is considered a proxy for the spot price
- It's the most liquid contract and most representative of current market price

**Output:** Float value representing spot price
```
Spot Price: 25,234.50
```

---

## Data Requirements Checklist

For your bhavcopy CSV to work properly, ensure:

✅ **Symbol Column**: Contains "NIFTY"  
✅ **Instrument Column**: Contains "OPTIDX" (for options) and "FUTIDX" (for futures)  
✅ **XpryDt Column**: Valid dates (can be YYYY-MM-DD or DD-MMM-YYYY format - pandas handles both)  
✅ **StrkPric Column**: Numeric strike prices  
✅ **OptnTp Column**: Contains "CE" or "PE"  
✅ **ClsPric Column**: Numeric closing prices (premiums for options)  
✅ **OpnIntrst Column**: Numeric open interest values  

---

## How Data is Used in Calculations

### 1. **Weekly Options** → ATM Implied Volatility Calculation
```python
# Gets nearest ATM (At-The-Money) calls and puts
atm_ce, atm_pe = get_atm_options(weekly_options, spot_price)

# Calculates implied volatility using these premiums
iv_ce = implied_vol(atm_ce["ClsPric"], spot_price, atm_ce["StrkPric"], T, r, "CE")
iv_pe = implied_vol(atm_pe["ClsPric"], spot_price, atm_pe["StrkPric"], T, r, "PE")

# ATM IV = Average of CE and PE IV
atm_iv = (iv_ce + iv_pe) / 2
```

### 2. **Weekly Options** → Premium Attachment to User Legs
```python
# For each leg the user specifies (e.g., BUY 25050 PE)
# Code finds the matching contract in weekly options
row = weekly_options[
    (weekly_options["StrkPric"] == 25050) &
    (weekly_options["OptnTp"] == "PE")
]

# Extracts the market premium (closing price)
premium = row["ClsPric"]  # e.g., 100.50

# Attaches it to the leg for PnL calculations
leg["premium"] = premium
```

### 3. **Futures Data** → Spot Price
```python
# Used to determine the current market spot price
# Essential for:
# - ATM strike calculation
# - PnL calculations across different spot price ranges
# - Probability of profit calculations

spot_price = 25234.50  # From futures closing price
```

---

## Example Bhavcopy CSV Structure

```csv
TckrSymb,Symbol,Instrument,FinInstrmTp,XpryDt,StrkPric,OptnTp,ClsPric,OpnIntrst
NIFTY,NIFTY,FUTIDX,IDF,2026-02-27,0,CE,25234.50,10000000
NIFTY,NIFTY,OPTIDX,IDO,2026-01-29,25000,CE,250.50,500000
NIFTY,NIFTY,OPTIDX,IDO,2026-01-29,25000,PE,75.20,300000
NIFTY,NIFTY,OPTIDX,IDO,2026-01-29,25050,CE,225.30,450000
NIFTY,NIFTY,OPTIDX,IDO,2026-01-29,25050,PE,100.10,400000
NIFTY,NIFTY,OPTIDX,IDO,2026-01-29,25100,CE,200.15,420000
NIFTY,NIFTY,OPTIDX,IDO,2026-01-29,25100,PE,125.50,380000
...
```

---

## Getting NSE Bhavcopy Files

The bhavcopy files can be downloaded from:
- **NSE Archives:** https://nsearchives.nseindia.com/content/fo/
- **File Format:** `BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`
- **Location:** Zipped CSV files organized by date

---

## Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| "No futures data found" | Bhavcopy missing FUTIDX contracts | Ensure file contains futures data |
| "No options data found" | Bhavcopy missing OPTIDX contracts | Ensure file contains options data |
| "Symbol not found" | Wrong symbol name in file | Use "NIFTY" exactly (case-sensitive) |
| "No weekly options found" | No Wednesday expiry | Add contracts with Wednesday expiry date |
| "Invalid date format" | XpryDt column format issue | Pandas auto-converts most formats, but ensure valid dates |

