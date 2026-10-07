# FOIR Model — Complete Architecture Guide

> **Audience**: New joiner who has never seen this codebase.
> **Prerequisite knowledge**: EMI, NPA, DPD — standard finance terms.
> **Source code**: `Fin.py` (~3,200 lines), single production module.


---

## 1. Glossary — Model-Specific Terms

| Term | What it means |
|---|---|
| FOIR | Fixed Obligation to Income Ratio. Monthly loan obligations divided by monthly income. Threshold: 50%. |
| CB | Credit Bureau report — the raw bureau data for each loan account. |
| CB_mod | The cleaned version of CB after `filter_cb()` runs. |
| Summary_mod | The cleaned version of the Summary sheet after `filter_summary()` runs. |
| Las (Loanwise Adjustment Sheet) | Per-loan output showing Final EMI, Remarks, and whether the account is included in FOIR. |
| CV (Credit Validation) | Per-lead summary with all check results — Outstanding, Overdue, Lender Count, FOIR. |
| OT (Model Output) | Final per-lead decision table. One row per lead, one comment (decision). |
| modis() | Post-processing function that reassesses income and adjusts decisions. |
| keep_rem | A list of Remark values that qualify an account for inclusion in the Outstanding calculation. |
| Joint Account Identifier | A grouping counter. Joint=1 means the primary/first occurrence of that loan. Joint=2+ means a duplicate grouping (same Sanction Amount + Date Opened + EMI). |
| Remark_Final | The final remark assigned to each loan account after all EMI adjustments. Determines which CV checks the account participates in. |
| A9 | An adjustment layer that excludes old loans, duplicates, and certain institution types from EMI. |
| A10 | An adjustment layer that caps retail loan EMI based on sanction amount tiers. |
| Adjusted EMI | The final EMI after all adjustments (A9, A10, 180+ DPD zeroing, joint micro zeroing). This is what goes into the FOIR calculation. |
| Pivot Income | Income derived from existing obligations: Total Installment / 0.48. Used during income reassessment. |
| Comments Waterfall | The priority-ordered decision logic that assigns a single rejection reason (or approval) to each lead. |
| Leads at COB | "Leads at Close of Business" — the final output Excel file with 4 sheets. |


---

## 2. What This Model Does

The FOIR Model takes a lead (a loan applicant) and decides: **should we give this person a loan?**

It reads the applicant's bureau data (all their existing loans from credit bureaus), checks five things, and outputs a decision. The five checks, in priority order:

1. **Overdue Check** — Do they have unpaid past-due amounts or write-offs?
2. **Credit Score Check** — Is their credit score in a risky range?
3. **Outstanding Check** — Do they owe too much money across all MFI loans?
4. **Lender Check** — Are they borrowing from too many microfinance lenders?
5. **FOIR Check** — Can they afford the new loan (obligations vs income)?

If all five pass → **Approved**.
If any fail → the first failing check (in priority order) determines the rejection reason.

After the initial decision, a post-processor called `modis()` does income reassessment, which can upgrade certain rejections to approvals.


---

## 3. Inputs — What Goes In

The model reads **4 input files** (or DataFrames):

### 3.1 Bureau Split (Excel workbook with 4 sheets)

This is the main input. It comes from the IT team and contains the applicant's credit bureau data.

| Sheet | What it contains |
|---|---|
| **Summary** | One row per lead — Lead ID, Customer ID, State, Branch, Loan Cycle (product), Name, Age, Credit Score, Income. |
| **CB** | One row per bureau account — all loan details: Institution, Account Status, Sanction Amount, Current Balance, EMI, Past Due Amount, Written Off Amount, Date Opened, Date Closed, Date Reported, etc. Multiple rows per lead. |
| **CB_Date** | One row per lead — the date their MFI bureau (CCR_DATE) and retail bureau (RETAIL_DATE) were pulled. Used to check freshness. |
| **DOB** | Date of birth data (used for age calculation, mapped in filter_cb). |

### 3.2 POS (Point of Sale / Product file)

One row per existing customer loan. Contains Loan Product names. Used only to identify **MTL R** (MTL Renewal) leads — if a customer's POS shows a product from a specific product list, their MTL is reclassified to MTL R.

### 3.3 Disbursement Report (inc)

Svamaan's own historical disbursement report (e.g., `Disbursement Report_Oct 2022 to Aug 2026.xlsx`). Contains records of all past loan disbursements. The model uses two columns:

- **`CUST ID`** — to match customers to leads
- **`Total Monthly Income`** — the income the borrower declared at the time of their previous disbursement with Svamaan

This means the "declared income" used in FOIR is whatever income the borrower stated during their **last Svamaan loan**. If a customer isn't found in the disbursement report (i.e., a first-time borrower with no prior Svamaan loan), their income defaults to **₹25,000**.

### 3.4 OD List (optional)

A list of Customer IDs that are pre-approved for special treatment. Leads on this list can have certain rejections (Overdue, Poor Credit Score, High Outstanding, Lender Count) overridden to approval status.


---

## 4. The Pipeline — `Foir_Model()` Orchestrator

**Location**: `Fin.py`, line 2348

The orchestrator function calls each step in sequence:

```
Foir_Model()
  │
  ├── 1. filter_cb()         → CB_mod, CB_Date_mod
  ├── 2. filter_summary()    → Summary_mod
  ├── 3. compute_emi_sheet() → EMI
  ├── 4. compute_las_sheet() → Las
  ├── 5. compute_cv_sheet()  → CV
  ├── 6. compute_ot_sheet()  → OT
  └── 7. modis()             → OT (modified)
```

Each step is described in detail below.


---

## 5. Step 1: `filter_cb()` — Clean Bureau Data

**Location**: `Fin.py`, line 2141
**Input**: CB, CB_Date, Summary, date thresholds
**Output**: CB_mod (cleaned bureau), CB_Date_mod (filtered dates)

### What it does:

**5.1 Remove stale bureau reports**
- Checks the bureau pull dates (CCR_DATE for MFI, RETAIL_DATE for retail).
- If the MFI bureau is older than 30 days or the retail bureau is older than 60 days → the lead is **removed entirely**.
- This ensures the model only works with fresh data.
- Exception: if `eval_all='Yes'` is passed, all leads are kept regardless of dates.

**5.2 Zero out closed accounts**
- If `DATE_CLOSED` has a value (is not empty/NaN), the account is treated as closed.
- All numeric columns (Current Balance, Past Due, Sanction Amount, EMI, etc.) are set to **0**.
- A comment "closed account" is added.
- **Important edge case**: The raw bureau data contains the literal text "NULL" in the DATE_CLOSED column for open accounts. Pandas automatically converts this to NaN when reading the Excel file, so these are correctly treated as open. But this behavior is fragile — if the reading method ever changes to preserve the string "NULL", ~17,500 open accounts would be incorrectly treated as closed.

**5.3 Institution-specific past-due zeroing**
- **Kiara Microcredit Private Limited**: Past Due and Written Off amounts are set to 0 (known data quality issue).
- **SHG Group / SHG Group - Govt**: Past Due and Written Off amounts are set to 0 (group lending — individual liability not applicable).

**5.4 Fix unreliable tenure**
- Bureau data sometimes reports unreliable Number of Installments (0–10) for MFI loans.
- When this happens, tenure is inferred from the loan's ticket size (Sanction Amount or Current Balance):

| Ticket Size | Assigned Tenure |
|---|---|
| ≤ ₹10,000 | 4 months |
| ≤ ₹25,000 | 10 months |
| ≤ ₹50,000 | 20 months |
| ≤ ₹80,000 | 32 months |
| > ₹80,000 | 52 months |

**5.5 Map age**
- Each lead's age is mapped from the Summary sheet.


---

## 6. Step 2: `filter_summary()` — Clean Summary Data

**Location**: `Fin.py`, line 2221
**Input**: Summary, CB_Date_mod, POS, Disbursement Report
**Output**: Summary_mod

### What it does:

**6.1 Keep only fresh leads**
- Removes any lead that was filtered out in Step 1 (stale bureau).

**6.2 Normalize loan products (LOAN CYCLE)**
- `CROSS SELL` → `CTL` (Cross-sell Top-up Loan)
- `IGL 3, IGL 4, ... IGL 10` → `IGL 2` (all higher IGL cycles treated as IGL 2)
- Branch names are lowercased then capitalized.

**6.3 Flag MTL R leads**
- If a customer's existing POS data contains products from a specific renewal product list → their `MTL` is reclassified to `MTL R` (MTL Renewal).
- This matters because MTL and MTL R have different overdue tolerance (both are ₹0, but they're tracked separately in config).

**6.4 Map declared income**
- Each lead's declared income is pulled from the Disbursement Report (matched by Customer ID — the income they declared during their last Svamaan loan).
- If a lead is not in the Disbursement Report (first-time borrower) → income defaults to **₹25,000**.


---

## 7. Step 3: `compute_emi_sheet()` — Calculate EMI Per Loan

**Location**: `Fin.py`, line 856
**Input**: CB_mod, Summary_mod, config
**Output**: EMI (one row per bureau account, enriched with calculated EMI)

This is the most complex step. For each loan account in the bureau, the model determines: **how much monthly EMI should this loan contribute to the lead's FOIR?**

### 7.1 The 16-Condition EMI Chain (line 995–1043)

The model evaluates 16 conditions **in priority order** (first match wins). Each condition either sets EMI to 0 (exclude) or calculates a value:

| # | Condition | EMI Value | Why |
|---|---|---|---|
| 1 | Date Closed exists (has a real date) | 0 | Loan is closed |
| 2 | Open Status = "No" | 0 | Loan is not active |
| 3 | Account Status is terminal (Closed, Settled, Written Off, etc.) AND not SHG AND not Svamaan — OR Guarantor | 0 | Dead account or guarantor liability |
| 4 | Current Balance ≤ 0 AND not SHG | 0 | Fully repaid |
| 5 | Date Reported < Sep 30, 2022 (CUTOFF_DATE) | 0 | Data too old to be relevant |
| 6 | Source is COAPP-RETAIL AND relationship is excluded family member (Wife, Mother, etc.) | 0 | Co-applicant exclusion |
| 7 | SHG Group/Govt with zero installment OR certain balance conditions | Calculated via PMT formula at 18% p.a. | SHG group — derive EMI from balance |
| 8 | SHG Group/Govt (other cases) | Bureau Installment / 10 | SHG group — scaled down |
| 9 | SHG Individual | Calculated via PMT formula at 18% p.a. | SHG individual — derive from balance |
| 10 | Specific banks (IOB, Indian Bank, ICICI) with Installment > ₹10,000 | Installment / 10 | Known over-reporting banks |
| 11 | MFI with zero installment | Calculated via PMT formula at 23.5% p.a. | Derive EMI from sanction amount |
| 12 | MFI with Bi-weekly frequency | Installment × 2 | Convert to monthly |
| 13 | MFI with Bimonthly frequency | Installment × 0.5 | Convert to monthly |
| 14 | MFI with Weekly frequency | Installment × 4 | Convert to monthly |
| 15 | MFI with Monthly/Others/On-Demand | Installment as-is | Already monthly |
| 16 | Bullet loan (gold, overdraft, etc.) | Principal × Rate | Interest-only payment |
| 17 | Retail with recalculation needed | Calculated via PMT formula | Amortization from principal |
| default | Everything else | Bureau Installment as-is | Trust the bureau |

### 7.2 A/C Closed Check (line 1105)

A **predictive closure** mechanism. Even if a loan isn't formally closed, the model estimates whether it should be treated as closed:

```
A/C Closed Check = Current Balance − (EMI × months since last reported)
```

Where `months since last reported = (processing_date − Date Reported) / 30`

If the result is ≤ 0 → the borrower has likely fully repaid → **Final EMI is set to 0**.

### 7.3 Final EMI Adjustments (line 1108–1119)

Three adjustments after the EMI chain:

1. **Svamaan's own loans**: Keep EMI as-is (company's own loans aren't excluded).
2. **Retail loans with 180+ DPD** (severely delinquent retail accounts): EMI → 0. Rationale: these accounts are non-performing; the borrower isn't actually making payments.
3. **A/C Closed Check ≤ 0**: EMI → 0 (see above).

### 7.4 Include in FOIR Flag (line 1120)

Simple binary:
- Final EMI > 0 → **Include in FOIR = Yes** (this loan counts toward obligations)
- Final EMI = 0 → **Include in FOIR = No** (this loan is excluded from FOIR)

### 7.5 Remark Assignment (line 1125–1164)

Each account gets a **Remark** explaining why it was included or excluded. The remark is critical because it determines which downstream CV checks the account participates in.

Key remarks and their meanings:

| Remark | Meaning | Include in FOIR |
|---|---|---|
| `-` | Active loan with bureau installment reported | Yes |
| `Calculated EMI` | Active loan where EMI was calculated (not from bureau) | Yes |
| `Bullet payment calculation` | Bullet loan with interest-only EMI | Yes |
| `Account closed` | Loan predicted as closed by A/C Closed Check | No |
| `Closed Account` | Loan formally closed per account status | No |
| `Closed acc/incorrect data` | Date Closed exists but is before Date Opened (data error) | No |
| `Balance is 0` | Zero balance, no EMI needed | No |
| `Old Reported` | Last reported before Sep 2022 — too stale | No |
| `Old Loan` | MFI loan opened before Dec 2021 — too old | No |
| `Old Gold Loan` | Gold/Priority Sector loan opened before Dec 2022 | No |
| `180+ Past Due` | Retail 180+ DPD — stopped paying, EMI zeroed | No |
| `Charge Off/Written Off` | Terminal bad debt status | No |
| `Past Due/ Write-Off` | Account with past-due status and active obligations | No |
| `Settled` | Account settled (may have balance) | No |
| `Post Write Off Settled/Closed` | Written-off then settled/closed | No |
| `Joint/Duplicate Account` | Duplicate grouping (Joint=2+) | No |
| `SHG not considered` | SHG Group/Govt loan | No |
| `Loss` | Loss account status | No |
| `Guarantor` | Guarantor liability, not direct borrowing | No |
| `Not a registered entity` | NIDHI companies — not a formal lender | No |

### 7.6 A9 — Old Loan & Duplicate Exclusion (line 1177–1203)

For accounts still marked "Include in FOIR = Yes", A9 checks if they should be excluded:

- **Duplicate** (Joint Account Identifier > 1) → EMI set to 0
- **NIDHI companies** (HMPL, Sarathifc, YUGTA, DHANIK) → 0
- **"Other" institution** → 0
- **Gold/Priority Sector loans opened ≤ Dec 2022** → 0
- **MFI loans opened ≤ Dec 2021** (except Svamaan) → 0
- **Tractor/Commercial Vehicle/Construction Equipment** → 0
- **Gold/Kisan/Credit Card/Bullet**: If balance-based EMI < bureau EMI → cap to balance-based

### 7.7 A10 — Retail EMI Cap (line 1206–1224)

For specific retail loan types, EMI is capped based on sanction amount tiers:

| Loan Type | Sanction < ₹80K | ₹80K–₹2L | > ₹2L |
|---|---|---|---|
| Consumer Loan | 65% of sanction ÷ tenure | 40% | 30% |
| Business Loan Unsecured | 55% | 50% | 40% |
| Two-Wheeler | 35% | 30% | 30% |
| Personal Loan | 55% | 35% | 25% |
| Auto Loan | 35% | 30% | 20% |
| Business Loan Secured | 35% | 25% | 25% |
| Housing Loan | 10% flat | 10% | 10% |

The cap only applies if the calculated cap is **less than** the current A9 EMI (i.e., it only reduces, never increases).

### 7.8 Remark_Final & Adjusted EMI (line 1289–1327)

Two final adjustments:

1. **Past Due/Write-Off reclassification**: If the account status is 180+ DPD, Settled, Written Off, etc. AND the loan is still marked FOIR=Yes → remark changes to `Past Due/ Write-Off` and Adjusted EMI → 0.
2. **Joint Micro accounts**: If the loan category is "Joint Account" from certain microfinance institutions → Adjusted EMI → 0 (marked as `Joint/Duplicate Account`).
3. **PSU Bank EMI scaling**: For certain PSU banks (IDBI, Canara, Indian Bank, IOB) with EMI ≥ ₹10,000 → EMI is divided by 10 (known over-reporting).

The **Adjusted EMI** is what ultimately goes into the FOIR calculation. If Adjusted EMI > 0, the account's `Include in FOIR` (final) = Yes.


---

## 8. Step 4: `compute_las_sheet()` — Build Loanwise Adjustment Sheet

**Location**: `Fin.py`, line 1333
**Input**: EMI, CB_mod
**Output**: Las

This is a simple packaging step. It copies the EMI DataFrame and renames columns:
- `Las['Final EMI']` = EMI's Adjusted EMI
- `Las['Remarks']` = EMI's Remark_Final
- `Las['Include in FOIR']` = EMI's Include in FOIR (final version)
- Adds Term Frequency, Account Status, and Loan Category from CB_mod


---

## 9. Step 5: `compute_cv_sheet()` — Credit Validation Checks

**Location**: `Fin.py`, line 1489
**Input**: EMI, Summary_mod, Las, config
**Output**: CV (one row per lead with all check results)

This is where the model evaluates each lead against the five credit checks.

### 9.1 MFI PastDue & Overdue (line 1510–1515)

**What it sums**: `Past Due` column (which equals PAST_DUE_AMOUNT + WRITTENOFF_AMOUNT from the raw bureau, as cleaned by filter_cb)

**Filter**:
- Source = CCR-MFI only
- Joint Account Identifier = 1 only (primary occurrences)
- **No remark filter** — ALL MFI accounts contribute, regardless of whether they're included in FOIR or not

**Important**: This means a loan with FOIR=No (e.g., a closed account, an old loan) still contributes its past due amount to the Overdue check. The only things that reduce past due are:
- filter_cb zeroing past due for closed accounts (DATE_CLOSED exists)
- filter_cb zeroing past due for Kiara Microcredit
- filter_cb zeroing past due for SHG Group/Govt

### 9.2 MFI Outstanding (line 1517–1577)

Total outstanding debt across MFI loans. Composed of **four sub-components**:

**(a) Standard MFI** — Full Current Balance
- Source = CCR-MFI, not Svamaan
- Remark_Final is in the `keep_rem` list
- Excludes SHG Group/Govt categories
- Excludes SHG Individual with balance ≥ ₹5 lakh (these go to SHG scaling)

The `keep_rem` list:
```
'Calculated EMI', '-', '180+ Past Due', 'Charge Off/Written Off',
'Past Due/ Write-Off', 'Post Write Off Settled',
'Post Written Off Settled', 'Settled', 'SHG not considered'
```

**(b) SHG Scaled Exposure**
- SHG Group loans: Balance > ₹15 lakh → divide by 15; else → divide by 10
- SHG Individual loans with balance ≥ ₹5 lakh: Same scaling as SHG Group
- Must have remark in keep_rem

**(c) Recently Closed Accounts**
- Remark_Final = "Account closed" AND Date Opened ≥ Jan 1, 2023
- Full Current Balance (no scaling)

**(d) Loss Accounts**
- Remark_Final = "Loss"
- Full Current Balance

**Final Outstanding = (a) + (b) + (c) + (d)**

### 9.3 Installment & FOIR Calculation (line 1587–1606)

- **Total Installment**: Sum of all EMI values per lead (from EMI chain, before adjustments)
- **Final EMI**: Sum of Adjusted EMI for Joint=1 accounts only (what actually counts for FOIR)
- **Monthly Income**: From the Disbursement Report (or ₹25,000 default for first-time borrowers)
- **FOIR = (Final EMI + Proposed Product EMI) / Monthly Income**
  - Proposed Product EMI: The EMI of the loan being applied for (from config, mapped by product)
- **New Monthly Income**: If FOIR > 50%, calculate the income needed for FOIR = 49%:
  `New Monthly Income = (Final EMI + Proposed EMI) / 0.49`, rounded to nearest ₹10

### 9.4 Outstanding Check (line 1660)

```
O/s Check = 1 (pass) if MFI Outstanding ≤ OS_Lim
           = 0 (fail) if MFI Outstanding > OS_Lim
```

**OS_Lim** (Outstanding Limit) varies by:
- **Branch** (each branch has its own limits)
- **Product** (IGL 1, IGL 2, CTL, MTL, etc.)
- **Credit Score tier**:
  - Good credit (score 700–900 or < 100): uses `os_good_cs` config
  - Bad credit (score 300–699) or CTL product: uses `os_bad_cs` config

These limits are loaded from a config file (`dicts_age.csv` / `new_bp_limits.csv`). If a Branch+Product combination isn't found, the model calls `New_branch_product()` to derive one.

### 9.5 Overdue Check (line 1663–1665)

```
Overdue Check = 1 (pass) if MFI PastDue & Overdue ≤ Overdue Limit
              = 0 (fail) if MFI PastDue & Overdue > Overdue Limit
```

**Overdue Limits** are per-product (from `OVERDUE_LIM` constant):

| Product | Overdue Tolerance |
|---|---|
| IGL 1 | ₹3,000 |
| IGL 2 | ₹3,000 |
| IGL3Y | ₹3,000 |
| IGL3Y-90 | ₹3,000 |
| CTL | ₹5,000 |
| MTL | ₹0 (zero tolerance) |
| MTL R | ₹0 (zero tolerance) |

### 9.6 Lender Count & Check (line 1453–1676)

**Lender Count**: Number of **distinct MFI lender names** the lead is borrowing from.

**Filter for counting**:
- Source = CCR-MFI
- Not Svamaan
- Remark_Final is in the lender remarks list:
  ```
  '180+ Past Due', 'SHG not considered', '-', 'Calculated EMI',
  'Charge Off/Written Off', 'Past Due/ Write-Off',
  'Post Write Off Settled', 'Post Write Off Closed',
  'Settled', 'Post Written Off Settled', 'Restructured & Closed'
  ```
- **OR** Remark_Final = "Account closed" AND Date Opened ≥ Jan 1, 2023

**Important**: There is **no Current Balance filter**. A lender with ₹0 balance still counts if the remark qualifies. This means a fully-repaid loan that was predicted as closed (A/C Closed Check) can still contribute to lender count.

**Lender mapping**: An optional mapping file can consolidate institution names (e.g., if an institution was acquired/renamed).

**Lender Check**:
```
Lender Check = 1 (pass) if lender count ≤ limit
             = 0 (fail) if lender count > limit
```

| State | Lender Limit |
|---|---|
| Tamil Nadu / TamilNadu_MT | 4 |
| All other states | 3 |

### 9.7 FOIR Check (line 1678)

```
FOIR Check = 1 (pass) if FOIR ≤ 50%
           = 0 (fail) if FOIR > 50%
```


---

## 10. Step 6: `compute_ot_sheet()` — Decision (Comments Waterfall)

**Location**: `Fin.py`, line 1713+
**Input**: CV
**Output**: OT (same as CV but with a Comments column)

### The Comments Waterfall

The model evaluates conditions **in priority order**. First match wins — a lead gets exactly one Comment:

| Priority | Condition | Comment (Decision) |
|---|---|---|
| 1 | Overdue fail + Outstanding pass + Lender pass | Overdue&WriteOff - Approve |
| 2 | Overdue fail + Lender fail | Overdue&WriteOff - Higher Lender |
| 3 | Overdue fail + Outstanding fail | Overdue&WriteOff - Higher Outstanding |
| 4 | Overdue fail (any other combo) | Overdue&WriteOff - Reject |
| 5 | Poor Credit Score (300–649) + All other checks pass | Poor Credit Score - Approve |
| 6 | Poor Credit Score + Lender fail | Poor Credit Score - Higher Lender |
| 7 | Poor Credit Score + Outstanding fail + Overdue fail | Poor Credit Score - Higher Outstanding & Overdue |
| 8 | Poor Credit Score + Outstanding fail | Poor Credit Score - Higher Outstanding |
| 9 | Poor Credit Score + Overdue fail | Poor Credit Score - Overdue |
| 10 | Lender fail (non-Tamil Nadu) | More than 3 Lenders |
| 11 | Lender fail (Tamil Nadu) | More than 4 Lenders |
| 12 | Outstanding fail | High Outstanding |
| 13 | FOIR fail + New Monthly Income ≤ ₹25,000 | Approve After Income Reassessment |
| 14 | FOIR fail (all others) | FOIR |
| default | All checks pass | Approve |

**Key observations**:
- Overdue trumps everything else (priorities 1–4)
- Poor Credit Score is next (priorities 5–9)
- Lender count is checked before Outstanding
- FOIR is the last check — it only matters if everything else passed
- The "Approve" sub-decisions for Overdue and PCS branches mean: "yes, this person has overdue/bad credit, but their other metrics are clean enough for conditional approval"


---

## 11. Step 7: `modis()` — Income Reassessment & Final Adjustments

**Location**: `Fin.py`, line 1958
**Input**: OT, Las, OD_list
**Output**: OT (modified decisions)

This is the post-processor that makes final adjustments to the model's decisions.

### 11.1 OD List Override (line 1983–2003)

If a lead's Customer ID appears on the OD List AND their current Comment is a rejection (Overdue, Poor Credit Score, Higher Lender, Higher Outstanding, More than 3/4 Lenders) → Comment is changed to **"Approve- OD"**.

Exceptions: Leads already marked as "Approve" in Overdue/PCS branches are NOT touched (they're already approved).

### 11.2 Income Reassessment Engine (line 2006–2081)

This is the core of modis(). It recalculates income for every lead:

**Rule 1 — Pivot Income (line 2008–2011)**:
```
Total Installment = Sum of all Final EMI across loans + ₹3,000
New Monthly Income = Total Installment / 0.48 (rounded to ₹100)
```

The ₹3,000 is the proposed loan's estimated EMI (added as a buffer).

**Income cap for low-obligation leads (line 2013–2016)**:
If Pivot Income > ₹75,000 but Total Installment < ₹36,500 → cap income at ₹75,000.

**Rule 3 — Low Installment Standardization (line 2042–2050)**:
If ALL of these are true:
- Total Installment < ₹12,500
- Declared Monthly Income ≤ ₹25,000
- Pivot Income ≥ ₹25,000

→ Set New Monthly Income to **₹25,000** (flat).

**Rule 2 — Higher Declared Income Retention (line 2055–2059)**:
If the declared Monthly Income is **higher** than the recalculated New Monthly Income → keep the declared income. The model never penalizes borrowers with verified higher earnings.

**FOIR Recalculation (line 2064–2067)**:
```
New FOIR = Total Installment / New Monthly Income
```

**Decision Update (line 2075–2081)**:
If a lead's Comment is **"FOIR"** AND their recalculated FOIR ≤ 50% → Comment changes to **"Approve After Income Reassessment"**.

**Why this always resolves**: Since income is derived as Installment / 0.48, the resulting FOIR is always Installment / (Installment / 0.48) = 0.48 = 48%. This is mathematically guaranteed to be ≤ 50%, so **every single FOIR rejection gets reclassified to an approval**. This is why the FOIR sheet in the output is always empty.

### 11.3 OD Income Suffix (line 2085–2091)

If an "Approve- OD" lead had their income increased (New Monthly Income > Monthly Income) → upgraded to **"Approve After IC- OD"** (needs field verification).

### 11.4 IC Suffix for Overdue & PCS Approvals (line 2094–2104)

If income was increased (New Monthly Income > Monthly Income):
- "Overdue&WriteOff - Approve" → "Overdue&WriteOff - Approve After IC"
- "Poor Credit Score - Approve" → "Poor Credit Score - Approve After IC"
- "Approve- OD" → "Approve After IC- OD"

### 11.5 High Income Rejection (line 2107–2114)

If New Monthly Income > ₹75,000 → certain approvals are reversed:
- "Overdue&WriteOff - Approve / Approve After IC" → "Overdue&WriteOff - Reject"
- "Poor Credit Score - Approve / Approve After IC" → "Poor Credit Score - Higher Outstanding"
- "Approve- OD / Approve After IC- OD" → "Reject- OD"

Rationale: If the model needs to impute income above ₹75,000 to make the math work, the borrower's actual obligations are suspiciously high.


---

## 12. Outputs — What Comes Out

The model produces an Excel file called **Leads at COB** (Leads at Close of Business) with **4 sheets**:

### 12.1 Approvals Sheet
All leads whose final Comment starts with "Approve" (any variant). These are the leads recommended for loan disbursement.

### 12.2 FOIR Sheet
Intended for leads rejected purely on FOIR. **Currently always empty** because modis() reclassifies all FOIR rejections to "Approve After Income Reassessment" (see Section 11.2).

### 12.3 Loanwise Adjustment Sheet (Las)
Per-loan detail — one row per bureau account per lead. Contains:
- Institution name, Source, Account Status, Loan Category
- Current Balance, Sanction Amount, EMI (from bureau)
- Final EMI (after all adjustments), Include in FOIR (Yes/No)
- Remarks (explaining inclusion/exclusion reason)
- Date Opened, Date Reported, Joint Account Identifier

### 12.4 Model Output (OT)
Per-lead summary — one row per lead. Contains:
- Lead ID, Product, Customer ID, State, Branch, Name
- Credit Score, Comments (the decision)
- MFI Outstanding, MFI PastDue & Overdue
- Total Installment, Monthly Income, FOIR, New Monthly Income
- Lender Count
- CB dates and processing metadata


---

## 13. FOIR=No but CV Checks=Yes — The 5 Combinations

A loan can be excluded from the FOIR calculation (FOIR=No, meaning Adjusted EMI=0) but still be counted in other CV checks (Outstanding, Lender Count, Overdue). This happens because each check uses **different filters**.

### How each check filters:

| Check | Filter used | Based on |
|---|---|---|
| **FOIR** | Adjusted EMI > 0 | EMI chain + all adjustments |
| **Outstanding** | Remark in `keep_rem` list OR "Account closed" opened ≥ 2023 OR "Loss" | Remark + Date Opened |
| **Lender Count** | Remark in `lender_remarks` list OR "Account closed" opened ≥ 2023 | Remark + Date Opened |
| **Overdue** | ALL MFI accounts with Joint=1 | Source + Joint ID only |

### The 5 combinations found in production data:

**Combo 1: Outstanding + Lender + Overdue** (most common — ~2,272 accounts)
- Remarks: Charge Off/Written Off, Past Due/Write-Off, 180+ Past Due, Account closed (recent)
- Why: These remarks are in both `keep_rem` and `lender_remarks`. Joint=1 means overdue counts too. EMI=0 because of terminal status or A/C Closed Check.
- Example: A written-off loan at Asirvad with ₹13,881 balance. FOIR=No (EMI zeroed for bad status), but balance counts in Outstanding, institution counts in Lender Count, and PastDue feeds Overdue.

**Combo 2: Overdue only** (~1,083 accounts)
- Remarks: Closed Account, Old Loan, Balance is 0, Account closed (pre-2023), Old Reported
- Why: These remarks are NOT in `keep_rem` or `lender_remarks`, so Outstanding and Lender skip them. But Overdue has **no remark filter** — it counts all MFI accounts with Joint=1.
- Example: A Bandhan Bank loan with "Closed Account" remark and ₹0 balance. Outstanding doesn't count it (wrong remark). Lender doesn't count it (wrong remark). But if it had any Past Due, it would still contribute to Overdue.

**Combo 3: NONE — not counted anywhere** (~172 accounts)
- Remarks: Joint/Duplicate Account (Joint=2), some Closed Account/Balance is 0 with Joint=2
- Why: Joint=2 means overdue skips it. Remark not in keep_rem or lender_remarks. FOIR=No. Completely invisible to the model.
- Example: A Bank of Baroda SHG loan with ₹1,56,190 balance, Joint=2 (duplicate). This balance is entirely invisible to every check.

**Combo 4: Lender + Overdue** (~25 accounts)
- Remarks: Past Due/Write-Off, 180+ Past Due
- Why: These remarks ARE in `lender_remarks` (Lender counts them). Joint=1 means Overdue counts them. But they're **SHG Group** category — and SHG Group is explicitly excluded from the Outstanding calculation.
- Example: A Bank of India SHG Group loan with ₹3,35,335 balance. Massive balance, but Outstanding ignores it (SHG Group exclusion). Lender and Overdue still see it.

**Combo 5: Outstanding + Lender** (~9 accounts)
- Remarks: Charge Off/Written Off, Account closed
- Why: Joint=2 means Overdue skips them. But the remark is in both `keep_rem` and `lender_remarks`, so Outstanding and Lender still count them.
- Example: PRASADITYA ARC loan with ₹36,251 balance, Joint=2. Outstanding sees the balance, Lender sees the institution name, but Overdue doesn't because Joint≠1.


---

## 14. State Groupings

States are categorized into three groups. These groupings affect branch-level outstanding limits (from config) but do not change the check logic itself.

| Group | States |
|---|---|
| G1 | Bihar, Maharashtra, Madhya Pradesh, Chhattisgarh, Uttar Pradesh, Odisha, Rajasthan, Jharkhand, West Bengal |
| G2 | Tamil Nadu, Telangana |
| G3 | Karnataka |

Tamil Nadu and TamilNadu_MT get a **lender limit of 4** (vs 3 for all other states).


---

## 15. Key Constants & Config Files

| Constant | Value | Location |
|---|---|---|
| `AC_CLOSED_MONTHS` | 0 | Fin.py line 70 |
| `CUTOFF_DATE` | Sep 30, 2022 | Fin.py line 71 |
| `OVERDUE_LIM` | Per-product dict | Fin.py line 114 |
| `BULLET_LOANS` | List of loan types | Fin.py line 74 |
| `FILTERED_PRODUCTS` | MTL R product list | Fin.py line 90 |
| `COAPP_EXCL` | Excluded family relationships | Fin.py line 109 |

| Config File | What it contains |
|---|---|
| `dicts_age.csv` | Branch × Product outstanding limits (os_good_cs, os_bad_cs) |
| `new_bp_limits.csv` | Supplementary branch-product limits for new combinations |
| `fo_emi` | Proposed product EMI values (from config) |
| Lender mapping | Institution name consolidation mapping |


---

## 16. Known Edge Cases & Gotchas

1. **FOIR sheet is always empty**: By design (not a bug). The income reassessment engine in modis() mathematically guarantees FOIR ≤ 48% for all leads, so every "FOIR" rejection is reclassified.

2. **"NULL" strings in DATE_CLOSED**: The raw bureau data contains the text "NULL" (not actual empty/NaN). Pandas silently converts this to NaN, so the model correctly treats these as open accounts. If the reading method ever changes (e.g., `keep_default_na=False`), ~17,500 accounts would be incorrectly treated as closed.

3. **Lender count includes ₹0 balance lenders**: A fully repaid loan that was predicted as closed by A/C Closed Check still counts toward lender count if its remark qualifies. This means a lead could fail the lender check because of a loan they've already repaid.

4. **Overdue has no remark filter**: Even loans excluded from FOIR, Outstanding, and Lender Count can still contribute their past-due amounts to the Overdue check. The only exclusions are at the filter_cb level (DATE_CLOSED, Kiara, SHG Group).

5. **Income default of ₹25,000**: If a lead isn't in the Disbursement Report (first-time borrower, no prior Svamaan loan), they get ₹25,000. This is also the cap used in Rule 3 of modis() for low-installment leads.

6. **Joint Account Identifier is not about joint ownership**: It's a duplicate-detection counter. Accounts with the same (Lead ID, Sanction Amount, Date Opened, EMI) are grouped, and only the first (Joint=1) is fully counted. Joint=2+ are marked as duplicates.

7. **SHG scaling differs from standard**: SHG Group/Govt loans contribute to Outstanding at 1/10th or 1/15th of their balance (not full balance). SHG Individual loans with balance ≥ ₹5 lakh get the same scaling. This can dramatically reduce a lead's apparent outstanding.

8. **PSU bank EMI scaling**: Certain PSU banks (IDBI, Canara, Indian Bank, IOB) have their EMI divided by 10 if it exceeds ₹10,000. This is a known data quality adjustment for banks that report inflated installment amounts.

9. **The ₹3,000 buffer in modis()**: When recalculating installments for income reassessment, modis() adds ₹3,000 to the sum of Final EMI. This represents the proposed loan's expected EMI.

10. **High income rejection (> ₹75K)**: If the model needs to impute income above ₹75,000 to make FOIR work, it reverses Overdue and PCS approvals. The rationale: if a borrower's obligations imply they should be earning > ₹75K, their actual debt level is concerning.
