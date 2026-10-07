import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import numpy_financial as npf
import shap
import decimal

def Lender_Count(Las):
    Las['Remarks'] = Las['Remarks'].astype(str).str.strip()
    # Exclude closed accounts, incorrect dates, restructured, write-offs, and zero-EMI accounts from lender count
    Lend = Las[
        (Las['Source'] == 'CCR- MFI') &
        (Las['Name of the Institution'] != 'Svamaan Financial Services Private Limited') & 
        (Las['Final EMI'] > 0) &
        (Las['Include in FOIR'] == 'Yes') &
        ((Las['Remarks'].isin(['180+ Past Due', 'SHG not considered', '-', 'Calculated EMI', 'Charge Off/Written Off', 'Past Due/ Write-Off', 'Post Write Off Settled', 'Settled', 'Post Written Off Settled'])) | ((Las['Remarks'] == 'Account closed') & (Las['Date Opened'] >= '2023-01-01')))
    ].groupby('LEAD_ID')['Name of the Institution'].nunique().fillna(0)
    return Lend
        
a = [525925]
AC_CLOSED_MONTHS = 0
CUTOFF_DATE = pd.Timestamp('2022-09-30')
supplememt_csv = "new_bp_limits.csv"

BULLET_LOANS = [
    'Business Loan - Priority Sector- Agriculture', 'Business Loan Against Bank Deposits', 'Business Non-Funded Credit Facility - Priority Sector - Agriculture', 'Corporate Credit Card', 'Loan Against Bank Deposits', 'Loan against Shares/Securities', 'Loan on Credit Card', 'Mudra Loans - Shishu / Kishor / Tarun', 'Overdraft', 'Prime Minister Jaan Dhan Yojana - Overdraft', 'Priority Sector- Gold Loan [Secured]', 'Secured Credit Card', 'Business Loan - Priority Sector - Agriculture',]
FILTERED_PRODUCTS = [
    "IGL-R-3 YEAR WEEKLY 75K", "IGL-R- 3 YEAR WEEKLY 90K", "IGL-R- 3 YEAR BI-WEEKLY 90K",
    "IGL-R- 3 YEAR BI-WEEKLY 75K", "IGL-R- 2 YEAR WEEKLY 75K", "MYS IGL-R- 2 YEAR WEEKLY 65K",
    "IGL-R-2 YEAR BI-WEEKLY 75K", "IGL-R-Cycle 3- 3 YEAR WEEKLY 90K", "IGL-R- 2 YEAR WEEKLY 60K",
    "IGL-R-Cycle 3- 2 YEAR WEEKLY 75K", "IGL-R- 1.5 YEAR WEEKLY 29K", "IGL-R- 3 YEAR WEEKLY 90K-KA",
    "IGL-R- 3 YEAR BI-WEEKLY 90K-KA", "IGL-R-3 YEAR WEEKLY 75K-KA", "IGL-R- 2 YEAR WEEKLY 70K",
    "IGL-R- 1 YEAR WEEKLY 22K", "IGL-R- 1.5 YEAR WEEKLY 45K", "IGL-R- 1 YEAR WEEKLY 30K",
    "IGL-R- 2 YEAR BI-WEEKLY 45K", "IGL-R- 2 YEAR WEEKLY", "IGL-R-2 YEAR BI-WEEKLY",
    "IGL-R- 1.5 YEAR WEEKLY", "IGL-R- 2 YEAR BI-WEEKLY", "IGL-R- 1 YEAR WEEKLY",
    "MT - IGL-R-2 YEAR WEEKLY", "IGL-R- 1.5 BI-WEEKLY", "IGL-R- 2 YEAR 1 Lakh WEEKLY",
    "IGL-R-2 YEAR 1 Lakh BI-WEEKLY",
]

AC_REASONS = [
    '180-359 days past due', '360-539 days past due', '540-719 days past due',
    '720+ days past due', 'Cancelled', 'Charge Off/Written Off', 'Loss',
    'Post Write Off Settled', 'Post Written Off Settled', 'Settled', 'Auctioned and Settled',
]
TERMINAL_STATUSES = []

COAPP_EXCL = [
    'Brother', 'Daughter', 'Sister', 'Grand Father', 'Mother',
    'Wife', 'BrotherInLaw', 'MotherInLaw', 'FatherInLaw',
]

OVERDUE_LIM = {
    'CTL': 5000, 'IGL 1': 3000, 'IGL 2': 3000,
    'IGL3Y': 3000, 'IGL3Y-90': 3000, 'MTL': 0, 'MTL R': 0,
}

# State → outstanding limit groups
_G1 = {
    'Good': {'IGL 1': 200000, 'IGL 2': 250000, 'CTL': 250000, 'MTL': 200000, 'MTL R': 250000},
    'Bad':  {'IGL 1': 175000, 'IGL 2': 200000, 'CTL': 250000, 'MTL': 175000, 'MTL R': 200000},
}
_G2 = {
    'Good': {'IGL 1': 250000, 'IGL 2': 300000, 'CTL': 300000, 'MTL': 250000, 'MTL R': 300000},
    'Bad':  {'IGL 1': 225000, 'IGL 2': 250000, 'CTL': 300000, 'MTL': 225000, 'MTL R': 250000},
}
_G3 = {
    'Good': {'IGL 1': 250000, 'IGL 2': 300000, 'CTL': 300000, 'MTL': 250000, 'MTL R': 300000,
             'IGL3Y': 300000, 'IGL3Y-90': 300000},
    'Bad':  {'IGL 1': 225000, 'IGL 2': 250000, 'CTL': 300000, 'MTL': 225000, 'MTL R': 250000,
             'IGL3Y': 2500000, 'IGL3Y-90': 250000},
}

STATE_TO_GROUP = {
    'BIHAR': _G1, 'MAHARASHTRA': _G1, 'CHHATTISGARH': _G1, 'HARYANA': _G1,
    'JHARKHAND': _G1, 'MADHYA PRADESH': _G1, 'ODISHA': _G1, 'RAJASTHAN': _G1,
    'UTTAR PRADESH': _G1,
    'TamilNadu_MT': _G2, 'TAMIL NADU': _G2, 'TAMILNADU MT': _G2, 'TELANGANA': _G2,
    'KARNATAKA': _G3,
}

MASTER_LIMITS: dict = {}
for _state, _scores in STATE_TO_GROUP.items():
    for _score_type, _products in _scores.items():
        for _product, _limit in _products.items():
            MASTER_LIMITS[f"{_score_type}{_state.upper()}{_product}"] = _limit

EMI_ORDER = [
    'LEAD_ID', 'Name of the Institution', 'Account Status', 'Loan Category', 'Source',
    'Open Status', 'Past Due', 'Current Balance', 'Sanction Amount', 'Date Reported',
    'Date Opened', 'Interest Rate', 'No Of Installments', 'Term Frequency', 'EMI',
    'A/C Closed Check', 'Final EMI', 'Include in FOIR', 'Remarks', 'Equifax ID',
    'Relation', 'Joint Account Identifier', 'Date Closed', 'Bullet Loan Check',
    'Check Bullet', 'A9', 'A10', 'FOIR10', 'Remark9', 'Remark10', 'Remark_Final',
    'STEP 1', 'Adjusted EMI', 'Include in FOIR_l',
]
CV_ORDER = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name', 'Credit Score',
    'Comments', 'O/s Check', 'Overdue Check', 'Lender Check', 'FOIR Check', 'MFI Outstanding',
    'MFI PastDue & Overdue', 'Total Installment', 'Final EMI', 'Monthly Income', 'FOIR',
    'New Monthly Income',
    'MFI OUTSTANDING 2', 'shg 10%', 'svmn', 'X', 'Final O/s',
    'Lenders', 'OS_Lim',
]

OT_ORDER = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name', 'Credit Score',
    'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue', 'Total Installment',
    'Monthly Income', 'FOIR', 'New Monthly Income', 'Lender Count',
]
OT_ORDER2 = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
    'Credit Score', 'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue',
    'Total Installment', 'Monthly Income', 'FOIR', 'New Monthly Income',
    'Lender Count', 'Income',
]
LAS_ORDER = [
    'LEAD_ID', 'Name of the Institution', 'Date Opened', 'Sanction Amount',
    'Current Balance', 'Final EMI', 'Include in FOIR', 'Remarks', 'Equifax ID',
    'Source', 'Date Reported', 'Joint Account Identifier', 'Relation',
    'Term freq.', 'ACCOUNT_STATUS', 'Loan_Category', 'No_hit', 
]


# ── Config loader (call once; result passed into functions) ───────────────────

def load_config(path: str = r"dicts_age.csv") -> dict:
    dicts = pd.read_csv(path)
    dicts['BP'] = dicts['Branch '].str.capitalize() + dicts['Product']
    fo_emi     = dicts.set_index('Product List ')['Proposed EMI'].to_dict()
    int_rates  = dicts.set_index('Name of the Loan')['Interest Rate Min (months)'].dropna().to_dict()
    tenure     = dicts.set_index('Name of the Loan')['Tenure Min (months)'].dropna().to_dict()
    inst_types = dicts.set_index('Name of the Loan')['Loan Type'].dropna().to_dict()
    os_good_cs = dicts.set_index('BP')['Credit Limit - Good Score'].dropna().to_dict()
    os_bad_cs  = dicts.set_index('BP')['Credit Limit - Bad Score'].dropna().to_dict()
    return {
        'fo_emi':     fo_emi,
        'int_rates':  int_rates,
        'tenure':     tenure,
        'inst_types': inst_types,
        'os_good_cs': os_good_cs,
        'os_bad_cs': os_bad_cs,        
    }
#==============================================================================================================================================================
'''                                              
88888888888   ,ad8888ba,    88  88888888ba   
88           d8"'    `"8b   88  88      "8b  
88          d8'        `8b  88  88      ,8P  
88aaaaa     88          88  88  88aaaaaa8P'  
88"""""     88          88  88  88""""88'    
88          Y8,        ,8P  88  88    `8b    
88           Y8a.    .a8P   88  88     `8b   
88            `"Y8888Y"'    88  88      `8b  

'''
#==============================================================================================================================================================

def _cap_and_label(tenure_factor, sanction, a9, remark_if_capped, base_remark=None):
    calc   = pd.to_numeric(tenure_factor) * pd.to_numeric(sanction) / 1000
    is_capped = calc < pd.to_numeric(a9)
    if base_remark is None:
        return np.where(is_capped, calc, a9)
    else:
        return np.where(is_capped, remark_if_capped, base_remark)

def excel_round(number, digits):
    try:
        if number is None or not np.isfinite(number):
            return 0
    
        context = decimal.getcontext()
        context.rounding = decimal.ROUND_HALF_UP
        
        d_num = decimal.Decimal(str(number))
        rounded = round(d_num, digits)
        return float(rounded)
        
    except (decimal.InvalidOperation, ValueError, TypeError):
        return 0

    
# ── CB Date + CB filtering ────────────────────────────────────────────────────

def filter_cb(CB: pd.DataFrame, CB_Date: pd.DataFrame, Summary: pd.DataFrame,
              date_15: str, date_45: str, eval_all = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    CB_Date['CCR_DATE'] = pd.to_datetime(CB_Date['CCR_DATE'])
    CB_Date['RETAIL_DATE'] = pd.to_datetime(CB_Date['RETAIL_DATE'])
    
    if (eval_all == 'Yes'):
        CB_Date_mod = CB_Date

    else:
        CB_Date_mod = CB_Date[
            (CB_Date['CCR_DATE'] > date_15) & (CB_Date['RETAIL_DATE'] > date_45)]        
        
    CB_dif = CB_Date.copy()
    CB_dif = CB_dif.drop(CB_Date_mod.index)
    CB_mod = CB[CB['LEAD_ID'].isin(CB_Date_mod['LEAD_ID'])].copy()
    CB_mod = CB_mod.fillna(0)

    CB_mod['PAST_DUE_AMOUNT']   = pd.to_numeric(CB_mod['PAST_DUE_AMOUNT'],   errors='coerce').fillna(0)
    CB_mod['WRITTENOFF_AMOUNT'] = pd.to_numeric(CB_mod['WRITTENOFF_AMOUNT'], errors='coerce').fillna(0)

    #CB_mod.loc[CB_mod['ACCOUNT_STATUS'].isin(TERMINAL_STATUSES), ['PAST_DUE_AMOUNT', 'WRITTENOFF_AMOUNT']] = 0
    
    CB_mod.loc[CB_mod['INSTITUTION'] == 'Kiara Microcredit Private Limited',
               ['PAST_DUE_AMOUNT', 'WRITTENOFF_AMOUNT']] = 0
    CB_mod.loc[CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].isin(['SHG Group', 'SHG Group - Govt']),
               ['PAST_DUE_AMOUNT', 'WRITTENOFF_AMOUNT']] = 0

    mask = (
        (CB_mod['LEAD_ID'].isin(Summary[Summary['STATE'] == 'TamilNadu_MT']['LEAD_ID'])) &
        (CB_mod['INSTITUTION'] == 'AU Small Finance Bank Limited')
    )
    CB_mod.loc[mask,
               ['PAST_DUE_AMOUNT', 'WRITTENOFF_AMOUNT']] = 0

    noi_condn = [
        (CB_mod['NO_OF_INSTALLMENTS'].between(0,3)) & (CB_mod['CB_TYPE'] == 'CCR- MFI') & (CB_mod['SANCTION_AMOUNT'] <= 10_000),       
        (CB_mod['NO_OF_INSTALLMENTS'].between(0,10)) & (CB_mod['CB_TYPE'] == 'CCR- MFI') & (CB_mod['SANCTION_AMOUNT'].between(10_000, 25_000, inclusive = 'right')),       
        (CB_mod['NO_OF_INSTALLMENTS'].between(0,10)) & (CB_mod['CB_TYPE'] == 'CCR- MFI') & (CB_mod['SANCTION_AMOUNT'].between(25_000, 50_000, inclusive = 'right')),       
        (CB_mod['NO_OF_INSTALLMENTS'].between(0,10)) & (CB_mod['CB_TYPE'] == 'CCR- MFI') & (CB_mod['SANCTION_AMOUNT'] > 50_000),       
    ]

    noi_values = [4, 12, 26, 52]
    CB_mod['NO_OF_INSTALLMENTS'] = np.select(noi_condn, noi_values, default = CB_mod['NO_OF_INSTALLMENTS'])
    
    CB_mod['INSTALLMENT_AMOUNT'] = pd.to_numeric(
        CB_mod['INSTALLMENT_AMOUNT'].astype(str), errors='coerce').fillna(0)
    CB_mod = CB_mod.reset_index(drop=True)

    CB_mod['Age'] = CB_mod['LEAD_ID'].map(Summary.set_index('LEAD_ID')['AGE'])
    
    return CB_mod, CB_Date_mod


# ── Summary filtering ─────────────────────────────────────────────────────────

def filter_summary(Summary: pd.DataFrame, CB_Date_mod: pd.DataFrame,
                   Pos: pd.DataFrame, inc: pd.DataFrame = None) -> pd.DataFrame:
    Summary_mod = Summary[Summary['LEAD_ID'].isin(CB_Date_mod['LEAD_ID'])].copy()
    Summary_mod = Summary_mod.reset_index(drop=True)

    Summary_mod.loc[Summary_mod['LOAN CYCLE'] == 'CROSS SELL', 'LOAN CYCLE'] = 'CTL'
    Summary_mod.loc[
        Summary_mod['LOAN CYCLE'].isin(['IGL 3', 'IGL 4', 'IGL 5']), 'LOAN CYCLE'
    ] = 'IGL 2'
    
    Summary_mod['BRANCH_NAME'] = Summary_mod['BRANCH_NAME'].str.lower() 

    mtr_leads = Pos[Pos['Loan Product'].isin(FILTERED_PRODUCTS)]['CUST ID']
    Summary_mod['LOAN CYCLE'] = np.where(
        Summary_mod['ICUST_ID'].isin(mtr_leads) & (Summary_mod['LOAN CYCLE'] == 'MTL'),
        'MTL R', Summary_mod['LOAN CYCLE'])
    
    Summary_mod['BRANCH_NAME'] = np.where(
        Summary_mod['STATE'] == 'TamilNadu_MT',
        'Mt_' + Summary_mod['BRANCH_NAME'],
        Summary_mod['BRANCH_NAME'])
    
    Summary_mod['BRANCH_NAME'] = Summary_mod['BRANCH_NAME'].str.capitalize()

    if inc is not None:
        inc = inc.drop_duplicates(subset=['CUST ID'], keep='first').copy()
        inc['Total Monthly Income'] = pd.to_numeric(inc['Total Monthly Income'], errors='coerce')
        inc_map = inc.set_index('CUST ID')['Total Monthly Income']
        mask = (Summary_mod['ICUST_ID'].isin(inc['CUST ID']))
        Summary_mod['SVAMAAN_COB_INCOME'] = 25000.0
        Summary_mod.loc[mask, 'SVAMAAN_COB_INCOME'] = Summary_mod.loc[mask, 'ICUST_ID'].map(inc_map)
    
    Summary_mod['LOAN CYCLE'] = np.where(
        Summary_mod['LOAN CYCLE'].isin(['IGL 3', 'IGL 4', 'IGL 5', 'IGL 6', "IGL 7", 'IGL 8', 'IGL 9', 'IGL 10']), 'IGL 2', Summary_mod['LOAN CYCLE'])
    return Summary_mod


# ── EMI sheet ─────────────────────────────────────────────────────────────────

def compute_emi_sheet(CB_mod: pd.DataFrame, Summary_mod: pd.DataFrame,
                      config: dict, processing_date: pd.Timestamp) -> pd.DataFrame:
    """Build and return the EMI DataFrame (row-level, one row per CB account)."""
    int_rates  = config['int_rates']
    tenure     = config['tenure']
    inst_types = config['inst_types']
    os_good_cs = config['os_good_cs']
    os_bad_cs  = config['os_bad_cs']

    # ── Interest rate resolution ──────────────────────────────────────────────
    raw_rate = pd.to_numeric(
        CB_mod['INTEREST_RATE'].astype(str).str.replace('%', '', regex=False),
        errors='coerce').fillna(0)
    is_retail = CB_mod['CB_TYPE'].isin(['COAPP- RETAIL', 'CCR- RETAIL'])
    rate_lookup = pd.to_numeric(
        CB_mod['INSTITUTION'].map(int_rates).astype(str).str.replace('%', '', regex=False),
        errors='coerce').fillna(0)
    interest_rate = np.where(is_retail & (raw_rate == 0), rate_lookup, raw_rate)
    # ── Instalment count resolution ───────────────────────────────────────────
    raw_noi = pd.to_numeric(CB_mod['NO_OF_INSTALLMENTS'], errors='coerce').fillna(0)
    noi = np.where(
        is_retail & (raw_noi == 0),
        CB_mod['INSTITUTION'].map(tenure).fillna(0),
        raw_noi)
        
    # ── Term frequency ────────────────────────────────────────────────────────
    term_freq = CB_mod['TERM_FREQUENCY'].astype(str)
    term_freq = np.where((term_freq == '0') | (term_freq == ''), 'Monthly', term_freq)

    # ── Build base DataFrame ──────────────────────────────────────────────────
    E = pd.DataFrame({
        'LEAD_ID':                  CB_mod['LEAD_ID'].values,
        'Name of the Institution':  CB_mod['INSTITUTION'].values,
        'Account Status':           CB_mod['ACCOUNT_STATUS'].values,
        'Loan Category':            CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].values,
        'Source':                   CB_mod['CB_TYPE'].values,
        'Open Status':              CB_mod['AC_OPEN'].values,
        'Past Due':                 (
            pd.to_numeric(CB_mod['PAST_DUE_AMOUNT'],   errors='coerce').fillna(0) +
            pd.to_numeric(CB_mod['WRITTENOFF_AMOUNT'], errors='coerce').fillna(0)
        ).values,
        'Current Balance':          pd.to_numeric(CB_mod['CURRENT_BALANCE'], errors='coerce').fillna(0).values,
        'Sanction Amount':          pd.to_numeric(CB_mod['SANCTION_AMOUNT'], errors='coerce').fillna(0).values,
        'Date Reported':            pd.to_datetime(CB_mod['DATE_REPORTED'], errors='coerce').values,
        'Date Opened':              pd.to_datetime(CB_mod['DATE_OPENED'], errors='coerce').values,
        'Date Closed':              pd.to_datetime(CB_mod['DATE_CLOSED'], errors='coerce').values,
        'Interest Rate':            interest_rate,
        'No Of Installments':       np.nan_to_num(pd.to_numeric(noi, errors='coerce'), nan=0),
        'Term Frequency':           term_freq,
        'INSTALLMENT_AMOUNT':       CB_mod['INSTALLMENT_AMOUNT'].values,
        'Equifax ID':               CB_mod['EQUIFAXID'].values,
        'Age':                      CB_mod['Age'].values,
        #'cams_d':                   CB_mod['cams_d'].values
    })

    E['Relation']          = E['LEAD_ID'].map(Summary_mod.set_index('LEAD_ID')['COAPP_RELATION'])
    E['Bullet Loan Check'] = E['Name of the Institution'].map(inst_types).fillna('NA')
    E['Check Bullet']      = np.where(
        E['Name of the Institution'].isin(BULLET_LOANS),
        E['Name of the Institution'], 7)

    # ── aliases ───────────────────────────────────────────────────────────────
    INST       = E['INSTALLMENT_AMOUNT']
    BAL        = E['Current Balance']
    SAX        = E['Sanction Amount']
    src        = E['Source']
    freq       = pd.Series(term_freq, index=E.index)
    loan_cat   = E['Loan Category']
    acc_status = E['Account Status']
    rel        = E['Relation']
    open_stat  = E['Open Status']
    loan_type  = E['Bullet Loan Check']
    date_cl    = pd.to_datetime(E['Date Closed'],   errors='coerce')
    date_rep   = pd.to_datetime(E['Date Reported'], errors='coerce')
    
    # ── Principal Selection ────────────────────────────────────────────────
    # Use the sanction amount as principal when it is lower than the current
    # balance (and non-zero); otherwise fall back to the current balance.
    E['principal'] = np.where((SAX < BAL) & (SAX != 0), SAX, BAL)
    # Housing / Property loans for borrowers aged 40–60 always use the current
    # balance as principal (bureau sanction is unreliable for that band).
    mask = (E['Age'].between(40, 60, inclusive = 'neither')) & (E['Name of the Institution'].isin(['Housing Loan', 'Property Loan']))
    E.loc[mask, 'principal'] = E.loc[mask, 'Current Balance']
    principal = E['principal'].values
    E = E.drop(columns = ['principal'])

    # ── Tenure conversion to months (retail amortisation) ─────────────────
    # Bureau NOI is reported in the loan's own frequency; convert to months.
    nper_retail = pd.to_numeric(E['No Of Installments']) * np.where(
        freq == 'Annually', 12, np.where(
            freq == 'Quarterly', 3, np.where(
                freq == 'Semiannually', 6, 1)))

    # ── Tenure conversion to months (MFI frequency multipliers) ───────────
    # MFI installments are reported in weekly / bi-weekly / monthly terms;
    # multiply the bureau NOI so the PMT term matches the monthly EMI we want.
    mfi_nper = pd.to_numeric(E['No Of Installments']) * np.where(
        freq == 'Bi-weekly', 0.5, np.where(
            freq == 'Weekly', 0.25, np.where(
                freq == 'Bimonthly', 2, np.where(
                    freq == 'Semiannually', 6, np.where(
                        freq == 'Annually', 12, np.where(
                            freq == 'Daily', 30, 1
                        )
                    )
                ))))

    # Fixed 10% p.a. cap for Loan Against Shares / Securities
    E.loc[E['Name of the Institution'] == 'Loan Against Shares / Securities', 'Interest Rate'] = 0.1

    rate         = pd.to_numeric(E['Interest Rate'], errors='coerce').fillna(0)
    rate_divisor = np.where(rate >= 1, 1200, 12)   # % p.a. → monthly rate

    # ── EMI calculation ───────────────────────────────────────────────────────

    # ── SHG balance: sanction, else balance, then per-member scaling ───────
    # Group loans are scaled to a per-member share; very large loans are
    # divided by 15, ₹1L+ loans by 10, and smaller loans kept as-is.
    SHG_BAL = np.where(SAX == 0, BAL, SAX)
    shg_scaled_bal = np.where(
        SHG_BAL >= 15_00_000, SHG_BAL / 15,
        np.where(SHG_BAL >= 1_00_000, SHG_BAL / 10, SHG_BAL)
    )
    # Reference tenure for the SHG PMT is derived from the scaled balance
    # ticket size (6 / 12 / 24 / 36 / 48 months).
    shg_ref_nper = np.select(
        [
            shg_scaled_bal <= 10_000,
            (shg_scaled_bal > 10_000) & (shg_scaled_bal <= 25_000),
            (shg_scaled_bal > 25_000) & (shg_scaled_bal <= 50_000),
            (shg_scaled_bal > 50_000) & (shg_scaled_bal <= 80_000),
            shg_scaled_bal > 80_000
        ],
        [6, 12, 24, 36, 48],
        default=48
    )
    shg_pmt_emi = -npf.pmt(18 / 1200, shg_ref_nper, shg_scaled_bal)   # SHG group PMT (18% p.a., ticket tenure)
    # Flag for SHG accounts whose reported installment already equals the full
    # sanction/balance (i.e. the installment is NOT a per-member share).
    SHG_EQ_CUR_SAX = ((INST.between(SAX- 100, SAX+ 100)) | (INST.between(BAL - 100, BAL+ 100)))

    # Restructured / closed account flags used by the EMI & Remarks chains
    date_op = pd.to_datetime(E['Date Opened'], errors='coerce')
    invalid_date_closed = (date_cl > pd.Timestamp(0)) & (date_op > pd.Timestamp(0)) & (date_cl < date_op)   # closed before opened
    restructured_statuses = [
        'Closed Account', 'Closed Account/Incorrect', 'Post Write Off Settled', 'Post Written Off Settled',
        'Post Write-Off Settled/Closed', 'Post Write Off Closed', 'Post Write-Off Settled',
        'Restructured & Closed', 'Restructured Loan', 'Restructured due to Covid', 'Restructured',
        'Loss', 'Charge Off/Written Off', 'Settled'
    ]

    # ── Base EMI: 16-condition priority chain ─────────────────────────────
    # First matching condition wins; anything not matched keeps the reported
    # installment (INST) as-is.
    emi_cond = [
        invalid_date_closed,                                                          # 1.  closed before opened on bureau
        date_cl > pd.Timestamp(0),                                                    # 2.  account has a close date → closed
        open_stat == 'No',                                                            # 3.  not marked open on bureau
        acc_status.isin(restructured_statuses) | (loan_cat == 'Guarantor'),          # 4.  restructured / closed / written off / guarantor
        BAL <= 0,                                                                     # 5.  zero / negative current balance
        date_rep < CUTOFF_DATE,                                                       # 6.  reported before the cutoff date
        (src == 'COAPP- RETAIL') & rel.isin(COAPP_EXCL),                              # 7.  excluded co-applicant relation
        (loan_cat.isin(['SHG Group', 'SHG Group - Govt', 'SHG Individual'])) & ((INST == 0) | (SHG_EQ_CUR_SAX)),  # 8.  SHG: no installment or full-amount installment → PMT
        loan_cat.isin(['SHG Group', 'SHG Group - Govt', 'SHG Individual']),           # 9.  SHG with per-member installment → ÷10 share
        (src == 'CCR- MFI') & (INST == 0) & (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),  # 10. MFI, no reported installment (non-Svamaan) → PMT fallback
        (src == 'CCR- MFI') & (freq == 'Bi-weekly'),                                  # 11. MFI bi-weekly installment → ×2 per month
        (src == 'CCR- MFI') & (freq == 'Bimonthly'),                                  # 12. MFI bimonthly installment → ×0.5 per month
        (src == 'CCR- MFI') & (freq == 'Weekly'),                                     # 13. MFI weekly installment → ×4 per month
        (src == 'CCR- MFI') & freq.isin(['Monthly', 'Others', 'On-Demand']),          # 14. MFI monthly / other → ×1
        loan_type == 'Bullet',                                                        # 15. bullet loan → interest-only payment
        src.isin(['CCR- RETAIL', 'COAPP- RETAIL']) & (nper_retail > 0) &
            ((INST == SAX) | (INST > pd.to_numeric(principal) * 0.2) | (INST == 0)),  # 16. retail with unreliable installment → amortised PMT
    ]
    emi_val = [
        0,                                                                            # 1–7. excluded accounts → zero EMI
        0,
        0,
        0,
        0,
        0,
        0,
        shg_pmt_emi,                                                                  # 8.  SHG group PMT (18% p.a., ticket tenure)
        INST / 10,                                                                    # 9.  SHG → per-member installment share
        -npf.pmt(18 / 1200, mfi_nper, SAX),                                           # 10. MFI no-installment fallback (18% p.a., bureau term)
        INST * 2,                                                                     # 11. bi-weekly → monthly
        INST * 0.5,                                                                   # 12. bimonthly → monthly
        INST * 4,                                                                     # 13. weekly → monthly
        INST,                                                                         # 14. monthly / others → as-is
        pd.to_numeric(principal) * rate / rate_divisor,                               # 15. bullet interest-only
        -npf.pmt(rate / rate_divisor, nper_retail, pd.to_numeric(principal)),         # 16. retail amortised PMT
    ]
    E['EMI'] = np.select(emi_cond, emi_val, default=INST)

    # ── Age-based NOI cap: compute modified EMI and take the lower of the two ──
    # Certain retail loan types are subject to a reduced instalment count when
    # the borrower is above a given age threshold.  Rather than modifying
    # NO_OF_INSTALLMENTS on CB_mod (which would propagate to all calculations),
    # we compute a parallel EMI using the capped NOI and take min(EMI, EMI_mod)
    # so only E['EMI'] is affected.  All subsequent steps (A/C Closed Check,
    # Final EMI, Remarks, A9 → Adjusted EMI) continue to use the resolved value.

    raw_noi = pd.to_numeric(CB_mod['NO_OF_INSTALLMENTS'], errors='coerce').fillna(0)
    noi = CB_mod['INSTITUTION'].map(tenure).fillna(CB_mod['NO_OF_INSTALLMENTS'])
    
    CB_mod['INTEREST_RATE'] = pd.to_numeric(CB_mod['INTEREST_RATE'], errors='coerce').fillna(0).astype(float)
    CB_mod.loc[CB_mod['INSTITUTION'] == 'Loan Against Shares/ Securities', 'INTEREST_RATE'] = 0.1
    rate_lookup = rate_lookup.fillna(CB_mod['INTEREST_RATE'])
    interest_rate = np.where((CB_mod['INTEREST_RATE'] < rate_lookup) & ~((CB_mod['INTEREST_RATE'] == 0) | (CB_mod['INTEREST_RATE'].isna())), CB_mod['INTEREST_RATE'], rate_lookup)
    E['Interest Rate'] = pd.Series(pd.to_numeric(interest_rate, errors='coerce')).fillna(0).values

    rate         = pd.to_numeric(E['Interest Rate'], errors='coerce').fillna(0)
    rate_divisor = np.where(rate >= 1, 1200, 12)
    
    inst_over_60 = {
        "Housing Loan": 120,
        "Property Loan": 120,
        "Auto Loan": 84,
        "Auto Loan (Personal)": 84,
    }
    
    age_col = pd.to_numeric(CB_mod['Age'], errors='coerce').fillna(0)
    
    # Modified NOI: apply age-based caps where applicable, leave others unchanged.
    noi_condn_mod = [
        (CB_mod['INSTITUTION'] == "Two-wheeler Loan"),
        (CB_mod['INSTITUTION'] == "Two-Wheeler Loan"),
        (CB_mod['INSTITUTION'] == "Auto Loan"),
        (CB_mod['INSTITUTION'] == "Auto Loan (Personal)"),
        (CB_mod['INSTITUTION'] == "Used Car Loan"),
        (CB_mod['INSTITUTION'] == "Personal Loan"),
        (CB_mod['INSTITUTION'] == 'Loan against Shares/Securities'),
        (CB_mod['INSTITUTION'] == 'Consumer Loan'),
        (CB_mod['INSTITUTION'] == 'Loan Against Bank Deposits'),
        (CB_mod['INSTITUTION'] == 'GECL Loan Unsecured'),
        (CB_mod['INSTITUTION'] == 'Loan on Credit Card'),
        (CB_mod['INSTITUTION'] == 'Mudra Loans - Shishu / Kishor / Tarun'),
        (CB_mod['INSTITUTION'] == 'P2P Personal Loan'),
        (CB_mod['INSTITUTION'] == 'Loan to Professional'),
        (CB_mod['INSTITUTION'] == 'Pradhan Mantri Awas Yojana - Credit Link Subsidy Scheme MAY CLSS'),
        (CB_mod['INSTITUTION'] == 'Business Loan - Secured'),
        (CB_mod['INSTITUTION'] == 'Business Loan - Unsecured'),
        age_col <= 35 & (CB_mod['INSTITUTION'] == 'Housing Loan'),
        age_col <= 40 & (CB_mod['INSTITUTION'] == 'Property Loan'),
        age_col <= 40,
        age_col.between(40, 60, inclusive='neither') &
            CB_mod['INSTITUTION'].isin(['Housing Loan', 'Property Loan']),
        (age_col >= 60) &
            CB_mod['INSTITUTION'].isin(inst_over_60.keys()),
    ]
    noi_values_mod = [
        36,                                                                           # two-wheeler
        36,                                                                           # two-wheeler
        84,                                                                           # auto loan
        84,                                                                           # auto loan (personal)
        42,                                                                           # used car
        60,                                                                           # personal loan
        37,                                                                           # loan against shares
        36,                                                                           # consumer loan
        33,                                                                           # loan against bank deposits
        48,                                                                           # GECL unsecured
        45,                                                                           # credit card
        44,                                                                           # mudra
        23,                                                                           # P2P personal
        53,                                                                           # loan to professional
        239,                                                                          # PMAY CLSS
        120,                                                                          # business loan - secured
        120,                                                                          # business loan - unsecured
        360,                                                                          # housing loan ≤ 35
        300,                                                                          # property loan ≤ 40
        pd.Series(noi, index=CB_mod.index),                                          # other loans ≤ 40 → keep tenure
        (60 - age_col) * 12,                                                          # housing/property 40–60 → months to 60
        CB_mod['INSTITUTION'].map(inst_over_60)                                       # ≥ 60 → product cap
            .fillna(pd.Series(noi, index=CB_mod.index)),
    ]
    noi_mod = np.select(noi_condn_mod, noi_values_mod, default=pd.Series(noi, index=CB_mod.index))
    # Never shorten a tenure that the bureau reports as longer
    noi_mod = np.where(noi_mod>= E['No Of Installments'], noi_mod, E['No Of Installments'])
    
    # Rebuild the period vector using the modified NOI (retail path only)
    '''nper_retail_mod = pd.to_numeric(noi_mod, errors='coerce').fillna(0) * np.where(
        freq == 'Annually',    12,
        np.where(freq == 'Quarterly',    3,
        np.where(freq == 'Semiannually', 6, 1))
    )'''
    nper_retail_mod = pd.Series(
        pd.to_numeric(noi_mod, errors='coerce')
    ).fillna(0) * np.where(
        freq == 'Annually',    12,
        np.where(freq == 'Quarterly',    3,
        np.where(freq == 'Semiannually', 6, 1)))
    
    # ── Age-adjusted EMI (cap pass) ────────────────────────────────────────
    # Modified EMI values list: identical to emi_val except the retail PMT entry
    # uses nper_retail_mod instead of nper_retail.
    emi_condn_mod = [
        (loan_cat.isin(['SHG Group', 'SHG Group - Govt', 'SHG Individual'])) & ((INST == 0) | (SHG_EQ_CUR_SAX)),  # SHG group → PMT
        loan_cat.isin(['SHG Group', 'SHG Group - Govt', 'SHG Individual']),                                       # SHG → per-member share
        (src == 'CCR- MFI') & (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),      # MFI (non-Svamaan) → PMT at bureau term
        (src.isin(['CCR- RETAIL', 'COAPP- RETAIL']))                                                              # retail → amortised PMT
    ]
    emi_val_mod = [  
        shg_pmt_emi,                                                                 # SHG group PMT (18% p.a., ticket tenure)
        INST / 10,                                                                    # SHG per-member share
        -npf.pmt(18 / 1200, mfi_nper, principal),                                     # MFI fallback (18% p.a., bureau term)
        -npf.pmt(rate / rate_divisor, nper_retail_mod, pd.to_numeric(principal))      # retail amortised PMT
    ]
    emi_mod = np.select(emi_condn_mod, emi_val_mod, default=E['EMI'])
    
    # Take the lower of the original and the age-capped EMI.
    E['EMI'] = np.minimum(E['EMI'], emi_mod)
    
    #cams_d = E['cams_d']
    #days_since = (cams_d - date_rep).dt.days
    # ── Account-Closed Check ───────────────────────────────────────────────
    # Estimated EMI the account would have accumulated since its last report
    # (months elapsed × EMI + buffer) vs. the current balance. A positive
    # balance above that estimate indicates the account is effectively closed.
    days_since = (pd.Timestamp(processing_date) - date_rep).dt.days
    E['A/C Closed Check'] = E['Current Balance'] - (E['EMI'] * ((days_since / 30) + AC_CLOSED_MONTHS))

    # ── Final EMI selection ────────────────────────────────────────────────
    # 1. Svamaan → keep its own EMI (see final Svamaan override below too)
    # 2. Per-lead total < ₹10 000 → keep (small exposures stay untouched)
    # 3. Severely past-due retail → zero
    # 4. A/C Closed Check ≤ 0 → zero
    lead_emi_sum = E.groupby('LEAD_ID')['EMI'].transform('sum')
    fin_cond = [
        E['Name of the Institution'] == 'Svamaan Financial Services Private Limited',
        lead_emi_sum < 10000,
        src.isin(['CCR- RETAIL', 'COAPP- RETAIL']) & acc_status.isin([
            '180-359 days past due', '360-539 days past due',
            '540-719 days past due', '720+ days past due',
            'Sub-standard', 'Doubtful']),
        E['A/C Closed Check'] <= 0,
    ]
    fin_val = [E['EMI'], E['EMI'], 0, 0]
    E['Final EMI']       = np.select(fin_cond, fin_val, default=E['EMI'])
    E['Include in FOIR'] = np.where(E['Final EMI'] > 0, 'Yes', 'No')
    
    # ── Business-loan EMI cap (10% p.a., 10-year flat) ─────────────────────
    # Business loans included in FOIR are capped at a notional 10-year
    # amortisation of the current balance — never above this benchmark.
    target_bus_loans = {x.lower() for x in [
        'Business Loan - General',
        'Business Loan - Secured',
        'Business Loan - Unsecured',
        'Microfinance - Business Loan',
        'Business Loan - Priority Sector - Small Business'
    ]}
    is_target_bus = E['Name of the Institution'].astype(str).str.strip().str.lower().isin(target_bus_loans)
    bus_pmt = -npf.pmt(10 / 1200, 120, pd.to_numeric(E['Current Balance'], errors='coerce').fillna(0))
    bus_mask = is_target_bus & (E['Include in FOIR'] == 'Yes') & (bus_pmt < E['Final EMI'])
    E.loc[bus_mask, 'Final EMI'] = bus_pmt[bus_mask]
    
    E['Include in FOIR'] = np.where(E['Final EMI'] > 0, 'Yes', 'No')
    inc = E['Include in FOIR']

    # ── Remarks: reason the EMI took its final value ───────────────────────
    remark_cond = [
        invalid_date_closed,                                                          # closed before opened on bureau
        date_cl > pd.Timestamp(0),                                                    # closed account
        (inc == 'Yes') & (loan_type == 'Bullet'),                                     # bullet → interest-only payment
        (inc == 'Yes') & (INST != 0),                                                 # reported installment kept
        (inc == 'Yes') & (INST == 0),                                                 # no installment → calculated EMI
        (inc == 'No') & (open_stat.isin(['No']) | (acc_status == 'Closed Account')),  # account not open
        loan_cat == 'Guarantor',                                                      # guarantor record
        acc_status.isin(['Post Write Off Settled', 'Post Written Off Settled',
                         'Post Write-Off Settled/Closed', 'Post Write Off Closed',
                         'Restructured & Closed', 'Restructured Loan', 'Restructured due to Covid',
                         'Loss', 'Charge Off/Written Off', 'Settled']),               # written off / restructured / settled
        src == 'SHG Group',                                                           # SHG group loan
        BAL <= 0,                                                                     # zero balance
        date_rep < CUTOFF_DATE,                                                       # old report
        (src == 'COAPP- RETAIL') & rel.isin(COAPP_EXCL),                              # excluded co-app relation
        (E['Final EMI'] == 0) & acc_status.isin([                                     # severe past due → zeroed
            '180-359 days past due', '360-539 days past due',
            '540-719 days past due', '720+ days past due',
            'Sub-standard', 'Doubtful']),
        (E['Final EMI'] == 0) & (E['A/C Closed Check'] <= 0),                         # A/C Closed Check → zeroed
    ]
    remark_val = [
        'Closed Account/Incorrect',
        'Closed Account',
        'Bullet payment calculation',
        '-',
        'Calculated EMI',
        'Account not Open',
        loan_cat,
        acc_status,
        'SHG Group Loan',
        'Balance is 0',
        'Old Reported',
        'Co-App is ' + rel.fillna('').astype(str),
        '180+ Past Due',
        'Account closed',
    ]
    E['Remarks'] = np.select(remark_cond, remark_val, default='No Remarks Found')

    E['Joint Account Identifier'] = (
        E.groupby(['LEAD_ID', 'Sanction Amount', 'Date Opened', 'EMI']).cumcount() + 1
    )

    # ── A9 ────────────────────────────────────────────────────────────────────
    is_gold_kisan  = E['Name of the Institution'].isin(['Gold Loan', 'Priority Sector - Gold Loan', 'Kisan Credit Card'])
    is_credit_card = E['Name of the Institution'] == 'Credit Card'
    is_bullet_inst = E['Check Bullet'] != 7

    a9_excl = (
        (E['Joint Account Identifier'] > 1) |
        E['Name of the Institution'].isin([
            'HMPL NIDHI LIMITED', 'Sarathifc Nidhi Limited',
            'YUGTA NIDHI LIMITED', 'DHANIK NIDHI LIMITED', 'Other']) |
        (E['Name of the Institution'].isin(['Gold Loan', 'Priority Sector - Gold Loan']) &
         (E['Date Opened'] <= pd.Timestamp('2022-12-31'))) |
        ((src == 'CCR- MFI') & (E['Date Opened'] <= pd.Timestamp('2021-12-31')) &
         (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited')) |
        E['Name of the Institution'].isin([
            'Tractor Loan', 'Commercial Vehicle Loan', 'Construction Equipment Loan'])
    )
    a9_cond = [
        a9_excl & (inc == 'Yes'),
        is_gold_kisan  & (inc == 'Yes') & (BAL * 0.005 < E['Final EMI']),
        is_credit_card & (inc == 'Yes') & (BAL * 0.02 < E['Final EMI']),
        is_bullet_inst & (inc == 'Yes') & (BAL * 0.005 < E['Final EMI']),
    ]
    a9_val = [0, BAL * 0.005, BAL * 0.02, BAL * 0.005]
    E['A9'] = np.select(a9_cond, a9_val, default=E['Final EMI'])

    # ── A10 ─────────────────────────────────────────────────────────────────────────
    sa = E['Sanction Amount']
    # NOTE: 'Business Loan - Unsecured' / 'Business Loan - Secured' are intentionally
    # excluded here. They are governed solely by the dedicated 10% p.a. / 120-month
    # PMT cap applied later (target_bus_loans block) so that cap is not overridden
    # by this unrelated sanction-amount-based formula.
    a10_cond = [
        (E['Name of the Institution'] == 'Consumer Loan')             & (sa != 0),
        (E['Name of the Institution'] == 'Two-Wheeler Loan')          & (sa != 0),
        (E['Name of the Institution'] == 'Personal Loan')             & (sa != 0),
        (E['Name of the Institution'] == 'Auto Loan (Personal)')      & (sa != 0),
        (E['Name of the Institution'] == 'Housing Loan')              & (sa != 0),
    ]
    a10_val = [
        _cap_and_label(np.where(sa > 200000, 30, np.where(sa < 80000, 65, 40)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200000, 30, np.where(sa < 80000, 35, 30)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200000, 25, np.where(sa < 80000, 55, 35)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200000, 20, np.where(sa < 80000, 35, 30)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(10, sa, E['A9'], 'Calculated EMI'),
    ]
    E['A10']    = np.select(a10_cond, a10_val, default=E['A9'])
    E['FOIR10'] = np.where(E['A10'] != 0, 'Yes', 'No')

    # ── Remark9 ───────────────────────────────────────────────────────────────
    rmk9_cond = [
        (E['Joint Account Identifier'] > 1) & (inc == 'Yes'),
        E['Name of the Institution'].isin([
            'HMPL NIDHI LIMITED', 'Sarathifc Nidhi Limited',
            'YUGTA NIDHI LIMITED', 'DHANIK NIDHI LIMITED']) & (inc == 'Yes'),
        (E['Name of the Institution'] == 'Other') & (inc == 'Yes'),
        E['Name of the Institution'].isin(['Gold Loan', 'Priority Sector - Gold Loan']) &
            (E['Date Opened'] <= pd.Timestamp('2022-12-31')) & (inc == 'Yes'),
        (src == 'CCR- MFI') & (E['Date Opened'] <= pd.Timestamp('2021-12-31')) &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited') & (inc == 'Yes'),
        E['Name of the Institution'].isin(['Tractor Loan', 'Commercial Vehicle Loan']) & (inc == 'Yes'),
        (E['Name of the Institution'] == 'Construction Equipment Loan') & (inc == 'Yes'),
        is_gold_kisan  & (inc == 'Yes') & (BAL * 0.01 < E['Final EMI']),
        is_credit_card & (inc == 'Yes') & (BAL * 0.05 < E['Final EMI']),
        is_bullet_inst & (inc == 'Yes') & (BAL * 0.015 < E['Final EMI']),
        (E['Check Bullet'] != 7) & (inc == 'Yes') & (E['Current Balance'] * 0.015 < E['Final EMI'])
    ]
    rmk9_val = [
        'Joint/Duplicate Account', 'Not a registered entity', 'Unrecognized Loan',
        'Old Gold Loan', 'Old Loan', 'Guarantor', 'Not Considered',
        'Calculated EMI', 'Calculated EMI', 'Calculated EMI', 'Calculated EMI'
    ]
    E['Remark9'] = np.select(rmk9_cond, rmk9_val, default=E['Remarks'])

    # ── Remark10─────────────────────────────────────────────────────────────────
    rmk10_cond = [
        E['Name of the Institution'] == 'Consumer Loan',
        E['Name of the Institution'] == 'Two-Wheeler Loan',
        E['Name of the Institution'] == 'Personal Loan',
        E['Name of the Institution'] == 'Auto Loan (Personal)',
        (E['Name of the Institution'] == 'Housing Loan') & (sa != 0),
    ]
    rmk10_val = [
        _cap_and_label(np.where(sa > 200000, 30, np.where(sa < 80000, 65, 40)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200000, 30, np.where(sa < 80000, 35, 30)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200000, 25, np.where(sa < 80000, 55, 35)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200000, 20, np.where(sa < 80000, 35, 30)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(10, sa, E['A9'], 'Calculated EMI', E['Remark9']),
    ]
    E['Remark10'] = np.select(rmk10_cond, rmk10_val, default=E['Remark9'])

    # ── Remark_Final ──────────────────────────────────────────────────────────
    past_due_list = [
        '180-359 days past due',
        '360-539 days past due', '540-719 days past due', '720+ days past due', 
        'Cancelled', 'Loss', 'Settled', 'Charge Off/Written Off',
        'Post Write Off Settled', 'Post Written Off Settled',
    ]
    rf_micro = ['Finance institution', 'Microfinance - Housing Loan',
                'Microfinance - Others', 'Micro Busines Unsecu']
    al_col = pd.Series(CB_mod['ACCOUNT_STATUS'].values,            index=E.index)
    am_col = pd.Series(CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].values, index=E.index)

    rmkf_cond = [
        al_col.isin(past_due_list) & (E['FOIR10'] == 'Yes') &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),
        (am_col.isin(['SHG Group', 'SHG Group - Govt'])) & (E['FOIR10'] == 'Yes'),
        (am_col == 'Joint Account') & (inc == 'Yes') & E['Name of the Institution'].isin(rf_micro),
    ]
    rmkf_val = ['Past Due/ Write-Off', '-', 
                'Joint/Duplicate Account']
    E['Remark_Final'] = np.select(rmkf_cond, rmkf_val, default=E['Remark10'])

    psu_banks = ['IDBI Bank Limited', 'Canara Bank', 'Canara Bank SHG',
                 'Indian Bank', 'Indian Overseas Bank']
    E['STEP 1'] = np.where(
        E['Name of the Institution'].isin(psu_banks) & (E['A10'] >= 10000),
        E['A10'] / 10, E['A10'])
    
    adj_past_due = [
        '180-359 days past due', '360-539 days past due', '540-719 days past due',
        '720+ days past due', 'Cancelled', 'Loss', 'Settled', 'Charge Off/Written Off',
        'Post Write Off Settled', 'Post Written Off Settled', 'Auctioned & Settled',
    ]
    adj_micro = ['Finan inst', 'Microfinance - Housing Loan',
                 'Microfinance - Others', 'Micro Busines Unsecu', 'Micro Busines Unsecured']
    ak_col = pd.Series(CB_mod['TERM_FREQUENCY'].values, index=E.index)

    adj_cond = [
        al_col.isin(adj_past_due) & (inc == 'Yes') &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),
        (am_col == 'Joint Account') & (inc == 'Yes') &
            (E['Name of the Institution'].isin(adj_micro))
    ]
    adj_val = [0, 0]
    E['Adjusted EMI']         = np.select(adj_cond, adj_val, default=E['STEP 1'])
    E['Include in FOIR_l'] = np.where(E['Adjusted EMI'] > 0, 'Yes', 'No')

    date_closed_mask = (pd.to_datetime(E['Date Closed'], errors='coerce') > pd.Timestamp(0))
    zero_out_mask = date_closed_mask | (
        acc_status.isin([
            'Closed Account', 'Closed Account/Incorrect', 'Post Write Off Settled',
            'Post Written Off Settled', 'Post Write-Off Settled/Closed', 'Post Write Off Closed',
            'Restructured & Closed', 'Restructured Loan', 'Restructured due to Covid',
            'Loss', 'Charge Off/Written Off', 'Settled'
        ]) & (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited')
    )
    E.loc[zero_out_mask, ['Current Balance', 'Sanction Amount', 'Past Due']] = 0

    E['Final EMI'] = np.where(
        (E['Name of the Institution'] == 'Svamaan Financial Services Private Limited'), 
        E['INSTALLMENT_AMOUNT'], E['Final EMI']
    )
    E['LOAN CYCLE'] = E['LEAD_ID'].map(Summary_mod.set_index('LEAD_ID')['LOAN CYCLE'])

    return E
# ── Loanwise Adjustment (Las) sheet ──────────────────────────────────────────

def compute_las_sheet(EMI: pd.DataFrame, CB_mod: pd.DataFrame) -> pd.DataFrame:
    Las = EMI.copy()
    Las['Final EMI']       = EMI['Adjusted EMI']
    Las['Remarks']         = EMI['Remark_Final']
    Las['Include in FOIR'] = EMI['Include in FOIR_l']
    Las['Term freq.']      = CB_mod['TERM_FREQUENCY'].values   # explicit — no closure
    Las['ACCOUNT_STATUS']  = EMI['Account Status']
    Las['Loan_Category']   = CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].values  # explicit
    Las['Coapp Relation']   = EMI['Relation'].values 
    Las['LOAN CYCLE']      = EMI['LOAN CYCLE']

    sum_inst = Las[Las['Source'] != 'COAPP- RETAIL'].groupby('LEAD_ID')['Final EMI'].sum()
    Las['sum_inst'] = Las['LEAD_ID'].map(sum_inst)
    mask = (Las['Source'] == 'COAPP- RETAIL') & (Las['Final EMI'] > 0) & (Las['LOAN CYCLE'] == 'IGL 1') & (Las['sum_inst'] <= 12_500)
    Las.loc[mask, 'No_hit'] = 'NH'
    Las.loc[~mask, 'No_hit'] = ""

#commit at 11-08-2026
    mask = (Las['LOAN CYCLE'] == 'IGL 1') & (Las['Source'] == 'COAPP- RETAIL') & (Las['Coapp Relation'] != 'Husband') & (Las['Include in FOIR'] == 'Yes') & (Las['Final EMI'] > 0)
    Las.loc[mask, 'No_hit'] = 'Coapp other than husband'
    
    Las.loc[Las['Remarks'] == 'SHG not considered', 'Remarks'] = '-'
    return Las

# ── CV sheet ──────────────────────────────────────────────────────────────────

def compute_cv_sheet(EMI: pd.DataFrame, Summary_mod: pd.DataFrame, Las: pd.DataFrame,
                     config: dict) -> pd.DataFrame:
    """Build and return the CV (credit validation summary) DataFrame."""
    fo_emi = config['fo_emi']
    os_bad_cs = config['os_bad_cs']
    os_good_cs = config['os_good_cs']

    CV = pd.DataFrame({
        'Lead ID':      Summary_mod['LEAD_ID'].values,
        'Product':      Summary_mod['LOAN CYCLE'].values,
        'Cust ID':      Summary_mod['ICUST_ID'].values,
        'State':        Summary_mod['STATE'].values,
        'Branch':       Summary_mod['BRANCH_NAME'].values,
        'Cust Name':    Summary_mod['FirstName'].values,
        'Credit Score': pd.to_numeric(Summary_mod['CCR_CREDIT_SCR'], errors='coerce').values,
    })
    lead_ids = CV['Lead ID']

    # ── MFI Outstanding ───────────────────────────────────────────────────────
    CV['MFI PastDue & Overdue'] = lead_ids.map(
        EMI[(EMI['Source'] == 'CCR- MFI') & (EMI['Joint Account Identifier'] == 1)]
        .groupby('LEAD_ID')['Past Due'].sum()
    ).fillna(0)
    
    # ── MFI Outstanding ── NEW RULE: (a) + (b) + (c) + Loss ──────────────────
    # (a) CCR-MFI, non-SHGA, non-Svamaan, remark list, full balance
    # (b) SHG exposure: Current Balance > Rs 15L -> /15, else /10
    # (c) Account closed, opened 2023 onward
    shg_cats = ['SHG Individual', 'SHG individual', 'SHG Group', 'SHG Group - Govt']
    keep_rem = ['Calculated EMI', '-', '180+ Past Due', 'Charge Off/Written Off',
                'Past Due/ Write-Off', 'Post Write Off Settled',
                'Post Written Off Settled', 'Settled']
    not_svmn = (EMI['Name of the Institution'] != 'Svamaan Financial Services Private Limited')

    mfi_a = EMI[
        (EMI['Source'] == 'CCR- MFI') & not_svmn &
        (~EMI['Loan Category'].isin(shg_cats)) &
        EMI['Remark_Final'].isin(keep_rem)
    ].groupby('LEAD_ID')['Current Balance'].sum()

    mfi_b_rows = EMI[
        not_svmn & EMI['Loan Category'].isin(shg_cats) &
        EMI['Remark_Final'].isin(keep_rem)
    ].copy()
    mfi_b_rows['_scaled_bal'] = np.where(
        pd.to_numeric(mfi_b_rows['Current Balance'], errors='coerce') > 1_500_000,
        mfi_b_rows['Current Balance'] / 15,
        mfi_b_rows['Current Balance'] / 10)
    mfi_b = mfi_b_rows.groupby('LEAD_ID')['_scaled_bal'].sum()

    mfi_c = EMI[
        (EMI['Source'] == 'CCR- MFI') & not_svmn &
        (EMI['Remark_Final'] == 'Account closed') &
        (pd.to_datetime(EMI['Date Opened'], errors='coerce') >= pd.Timestamp('2023-01-01'))
    ].groupby('LEAD_ID')['Current Balance'].sum()

    mfi_loss = EMI[
        (EMI['Source'] == 'CCR- MFI') & not_svmn &
        (EMI['Remark_Final'] == 'Loss')
    ].groupby('LEAD_ID')['Current Balance'].sum()

    CV['MFI Outstanding'] = (
        CV['Lead ID'].map(mfi_a).fillna(0) +
        CV['Lead ID'].map(mfi_b).fillna(0) +
        CV['Lead ID'].map(mfi_c).fillna(0) +
        CV['Lead ID'].map(mfi_loss).fillna(0))

    CV['MFI OUTSTANDING 2'] = 0.0     # absorbed into (a)/(c) above
    CV['shg 10%']           = 0.0     # SHG now inside (b); 'SHG not considered' renamed to '-'
    CV['svmn']              = 0.0     # Svamaan excluded in all parts
    CV['X']                 = CV['MFI Outstanding']
    CV['Final O/s']         = CV['X'].fillna(0)

    
    CV['Total Installment'] = lead_ids.map(
        EMI.groupby('LEAD_ID')['EMI'].sum()).fillna(0)

    CV['Final EMI'] = lead_ids.map(
        EMI[EMI['Joint Account Identifier'] == 1]
        .groupby('LEAD_ID')['Final EMI'].sum()
    ).fillna(0)

    CV['Monthly Income'] = lead_ids.map(
        Summary_mod.set_index('LEAD_ID')['SVAMAAN_COB_INCOME'])

    proposed = CV['Product'].map(fo_emi).fillna(0)
    proposed = pd.to_numeric(proposed.replace({',': '', '-': '0'}, regex=True))
    CV['FOIR'] = ((CV['Final EMI'] + proposed) / CV['Monthly Income'])
    CV['FOIR'] = CV['FOIR'].map(lambda x: excel_round(x, 2)) 
    
    CV['New Monthly Income'] = np.where(
        CV['FOIR'] > 0.5,
        ((CV['Final EMI'] + proposed) / 0.49).round(-1),
        CV['Monthly Income'])

    # ── Checks ────────────────────────────────────────────────────────────────
    CV['Key']    = CV['Branch'] + CV['Product']
    
    def _resolve_os_lim(cv: pd.DataFrame, os_good: dict, os_bad: dict) -> pd.Series:
        return np.where(
            cv['Product'] == 'CTL',
            cv['Key'].map(os_bad),
            np.where(
                (cv['Credit Score'].between(699, 901, inclusive='neither')) |
                (cv['Credit Score'] < 100),
                cv['Key'].map(os_good),
                cv['Key'].map(os_bad),
            )
        )

    CV['OS_Lim'] = _resolve_os_lim(CV, os_good_cs, os_bad_cs)
    csv_path = r"dicts_age.csv"

    na_mask = pd.isna(CV['OS_Lim'])
    if na_mask.any():
        new_rows = New_branch_product(CV[na_mask].copy(), config)
        if not new_rows.empty:
            try:
                existing_csv = pd.read_csv(csv_path)
                updated_csv  = pd.concat([existing_csv, new_rows], ignore_index=True)
                updated_csv.to_csv(csv_path, index=False)
            except FileNotFoundError:
                print(f"[compute_cv_sheet] WARNING: '{csv_path}' not found — "
                      "new BP rows written to memory only.")
            CV.loc[na_mask, 'OS_Lim'] = _resolve_os_lim(CV[na_mask], os_good_cs, os_bad_cs)

        # Rows still NaN after the lookup mean the state/product combo isn't in the
        # master limits table at all (e.g. a brand-new state). Flag them so they
        # surface clearly in the output rather than silently failing the O/s Check.
        still_na = pd.isna(CV['OS_Lim'])
        if still_na.any():
            print(f"[compute_cv_sheet] WARNING: OS_Lim still NaN for "
                  f"{still_na.sum()} row(s) after New_branch_product — "
                  f"Keys: {CV.loc[still_na, 'Key'].unique().tolist()}")
    
    CV['O/s Check'] = np.where(CV['Final O/s'] <= CV['OS_Lim'], 1, 0)
    #CV['O/s Check'] = np.where(CV['MFI Outstanding'] <= CV['OS_Lim'], 1, 0)
    
    od_lim = pd.to_numeric(CV['Product'].map(OVERDUE_LIM), errors='coerce')
    CV['Overdue Check'] = np.where(
        pd.to_numeric(CV['MFI PastDue & Overdue'], errors='coerce') > od_lim, 0, 1)
    
    Lend = Lender_Count(Las)
    CV['Lenders'] = CV['Lead ID'].map(Lend).fillna(0)

    # Lender Check is state-aware: Tamil Nadu (TamilNadu_MT / Tamil Nadu) allows
    # up to 4 distinct MFI lenders; all other states allow up to 3.
    mt_states = ['TamilNadu_MT', 'Tamil Nadu']
    lender_lim = np.where(CV['State'].isin(mt_states), 4, 3)
    CV['Lender Check'] = np.where(
        CV['Lenders'] > lender_lim, 0, 1)

    CV['FOIR Check'] = np.where(CV['FOIR'] > 0.5, 0, 1)

    # ── Comments ──────────────────────────────────────────────────────────────
    #  BUSINESS RULE (same gate logic applied to both Overdue/WriteOff and PCS):
    #  Lender Check = 1 when lenders <= 3 (<= 4 for TamilNadu_MT / Tamil Nadu)
    #  if (overdue / write-off present):
    #      if (O/s Check == 1) AND (Lender Check == 1):   → Overdue&WriteOff - Approve
    #      else:                                           → Overdue&WriteOff - Reject
    #  elif (poor credit score [300, 650)):
    #      if (O/s Check == 1) AND (Overdue Check == 1) AND (Lender Check == 1):
    #                                                      → Poor Credit Score - Approve
    #      else:                                           → Poor Credit Score - Reject
    #  elif (Lender Check == 0, non-MT):                  → More than 3 Lenders
    #  elif (Lender Check == 0, TamilNadu_MT / Tamil Nadu):→ More than 4 Lenders
    #  elif (O/s Check == 0):                              → High Outstanding
    #  elif (FOIR > 0.5 AND NMI <= 25 000):               → Approve After Income Reassessment
    #  elif (FOIR > 0.5):                                  → FOIR
    #  else:                                               → Approve

    # Poor Credit Score flag: Equifax score in [300, 650)
    pcs_mask = CV['Credit Score'].between(300, 650, inclusive='left')

    # Secondary checks — both PCS-Approve and OW-Approve require these
    ow_ok = (                           # checks for Overdue/WriteOff branch (no overdue re-check)
        (CV['O/s Check'] == 1) &        # MFI outstanding within branch-product OS limit
        (CV['Lender Check'] == 1)       # distinct MFI lender count <= 3 (<= 4 for Tamil Nadu)
    )
    other_ok = (                        # checks for PCS branch (overdue must also be within limit)
        (CV['O/s Check'] == 1) &        # MFI outstanding within branch-product OS limit
        (CV['Overdue Check'] == 1) &    # MFI past-due within OVERDUE_LIM threshold
        (CV['Lender Check'] == 1)       # distinct MFI lender count <= 3 (<= 4 for Tamil Nadu)
    )

    com_condn = [
        (CV['Overdue Check'] == 0) & ow_ok,                                               # overdue/write-off + secondary checks pass  → approve
        (CV['Overdue Check'] == 0),                                                        # overdue/write-off + any secondary check fails → reject
        pcs_mask & other_ok,                                                               # poor credit score + all checks pass → approve
        pcs_mask,                                                                          # poor credit score + at least one check failed → reject
        (CV['Lender Check'] == 0) & ~(CV['State'].isin(['TamilNadu_MT', 'Tamil Nadu'])),  # >3 lenders (non-MT)
        (CV['Lender Check'] == 0) & (CV['State'].isin(['TamilNadu_MT', 'Tamil Nadu'])),   # >4 lenders (MT states)
        CV['O/s Check'] == 0,                                                              # outstanding exceeds limit
        (CV['FOIR Check'] == 0) & (CV['New Monthly Income'] <= 25000),                    # FOIR fail + low income → income reassess
        (CV['FOIR Check'] == 0)                                                            # FOIR fail + higher income → FOIR flag
    ]

    com_choice = [
        'Overdue&WriteOff - Approve', 'Overdue&WriteOff - Reject',
        'Poor Credit Score - Approve', 'Poor Credit Score - Reject',
        'More than 3 Lenders', 'More than 4 Lenders', 'High Outstanding',
        'Approve After Income Reassessment', 'FOIR']
    CV['Comments'] = np.select(com_condn, com_choice, default='Approve')
    return CV


# ── OT sheet ──────────────────────────────────────────────────────────────────

def compute_ot_sheet(CV: pd.DataFrame, EMI: pd.DataFrame) -> pd.DataFrame:
    OT = CV[[
        'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
        'Credit Score', 'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue',
        'Monthly Income', 'FOIR', 'New Monthly Income',
    ]].copy()
    OT['Total Installment'] = CV['Final EMI']
    OT['MFI Outstanding'] = CV['Final O/s']

    mapping = (
        EMI[
            (EMI['Name of the Institution'] != 'Svamaan Financial Services Private Limited') &
            (EMI['Include in FOIR'] == 'Yes') &
            (EMI['Source'] == 'CCR- MFI')
        ]
        .groupby('LEAD_ID')['Name of the Institution'].nunique()
    )
    OT['Lender Count'] = CV['Lead ID'].map(mapping).fillna(0)
    return OT
# ── Modifications ──────────────────────────────────────────────────────────────
def modis(    
    OT: pd.DataFrame, 
    Las: pd.DataFrame, 
    Stages=None, 
    OD_list=None,
    a = None,):    
    a = [525925]
    tracking_history = None
    if a is not None and len(a) > 0:
        # Keep track of target rows at entry (Step 0 - Entry)
        tracking_history = OT[OT["Lead ID"].isin(a)][
            ["Lead ID", "Comments", "New Monthly Income"]
        ].copy()
        tracking_history["Step"] = "0. Entry" # Debug snapshot at entry
        
    def capture_snapshot(step_name: str):
        """Helper to append current status of target leads to tracking dataframe."""
        nonlocal tracking_history
        if tracking_history is not None:
            current_state = OT[OT["Lead ID"].isin(a)][
                ["Lead ID", "Comments", "New Monthly Income"]
            ].copy()
            current_state["Step"] = step_name
            tracking_history = pd.concat(
                [tracking_history, current_state], ignore_index=True
            )

    # ── OD override: rejection → 'Approve- OD' for OD customers ──────────────
    if OD_list is not None:
        ot_ids = OT['Cust ID'].astype(str).str.strip()
        od_ids = OD_list['CUST ID'].astype(str).str.strip()
        mask = (
            ot_ids.isin(od_ids) &
            OT['Comments'].isin([
                # 'Overdue&WriteOff - Approve' intentionally excluded: already approved
                'Overdue&WriteOff', 'Overdue&WriteOff - Reject',
                'More than 4 Lenders', 'More than 3 Lenders',
                'High Outstanding', 'Poor Credit Score',
                # 'Poor Credit Score - Approve' intentionally excluded: already approved
                'Poor Credit Score - Reject',
            ])
        )
        OT.loc[mask, 'Comments'] = 'Approve- OD'
    capture_snapshot("Step1")

    # ── Compute Income and Income 2 for bracket snapping ──────────────────────
    lend = Lender_Count(Las)

    # Income 2: total LAS obligations + ₹3 000 proposed EMI buffer
    Las_map = (Las.groupby('LEAD_ID')['Final EMI'].sum()).fillna(0) + 3_000
    OT['Total Installment'] = OT['Lead ID'].map(Las_map).fillna(0)

    # Income: back-calculated from Income 2 at 48 % FOIR, rounded to nearest ₹100
    OT['Income'] = ((OT['Total Installment']) / 0.48).round(-2)

    # Cap Income at ₹75 000 if Income 2 is below the NQA instalment threshold
    OT['Income'] = np.where(
        (OT['Income'] > 75_000) & (OT['Total Installment'] < 36_500),
        75_000, OT['Income']
    )
    capture_snapshot("Step2")

    # ── MT IGL1 exception ─────────────────────────────────────────────────────
    # TamilNadu_MT IGL1 leads with rejection/FOIR comments but computed income
    # within NQA → approve with IC (income change) tag
    mt_mask = (
        OT['Comments'].isin([
            'FOIR', 'Overdue&WriteOff', 'Overdue&WriteOff - Reject',
            'More than 4 Lenders', 'High Outstanding', 'Poor Credit Score',
            # 'Overdue&WriteOff - Approve' and 'Poor Credit Score - Approve'
            # intentionally excluded: already approved, must surface in output.
            'Poor Credit Score - Reject',
        ]) &
        (OT['State'] == 'TamilNadu_MT') &
        (OT['Product'] == 'IGL 1') &
        (OT['Income'] <= 75_000)
    )
    OT.loc[mt_mask, 'Comments'] = 'Approve After IC- MT'

    # ── Step 2: QA-range snap ─────────────────────────────────────────────────
    # If the computed Income is in QA (≤ ₹25 000) but New Monthly Income is
    # above ₹25 000 and current Monthly Income is also QA → snap down to Income
    mask = (
        (OT['Income'] <= 25_000) &
        (OT['New Monthly Income'] > 25_000) &
        (OT['Monthly Income'] <= 25_000) &
        OT['Comments'].isin([
            'FOIR', 'Approve', 'Approve- OD', 
            'Approve After Income Reassessment', 'Approve After IC- MT',
        ])
    )
    OT.loc[mask, 'New Monthly Income'] = OT.loc[mask, 'Income']
    OT.loc[mask & (OT['Comments'] == 'Approve- OD'), 'Comments'] = 'Approve After IC- OD'
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- MT', 'Approve After IC- OD']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    capture_snapshot("Step3")

    # ── Step 3: NQA MT snap ────────────────────────────────────────────────────
    mask = (
        OT['Income'].between(25_001, 75_000, inclusive='both') &
        (OT['New Monthly Income'] > 25_000) &
        (OT['Comments'].isin(['Approve After IC- MT']))
    )
    OT.loc[mask, 'New Monthly Income'] = OT.loc[mask, 'Income']
    capture_snapshot("Step4")

    # ── Step 4: Minimum income floor (₹13 000) ────────────────────────────────
    mask = (
        (OT['New Monthly Income'] < 13_000) &
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment', 'Approve- OD',
        ])
    )
    OT.loc[mask, 'New Monthly Income'] = 13_000
    OT.loc[mask & (OT['Comments'] == 'Approve- OD'), 'Comments'] = 'Approve After IC- OD'
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- OD', 'Approve After IC- MT']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    capture_snapshot("Step5")

    # ── Step 5: Lower-bracket nudge (₹13 001–₹23 500 → +₹1 000) ──────────────
    mask = (
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment', 'Approve- OD',
            'Approve After IC- MT', 'Approve After IC- OD',
        ]) &
        OT['New Monthly Income'].between(13_001, 23_500)
    )
    OT.loc[mask & (OT['Comments'] == 'Approve- OD'), 'Comments'] = 'Approve After IC- OD'
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- OD', 'Approve After IC- MT']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    OT.loc[mask, 'New Monthly Income'] = OT.loc[mask, 'New Monthly Income'] + 1_000
    capture_snapshot("Step6")

    # ── Step 6: NQA boundary snap (₹24 501–₹24 999 → ₹25 000) ───────────────
    mask = (
        OT['New Monthly Income'].between(24_501, 24_999) &
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment', 'Approve- OD',
            'Approve After IC- MT', 'Approve After IC- OD',
        ])
    )
    OT.loc[mask, 'New Monthly Income'] = 25_000
    OT.loc[mask & OT['Comments'].isin(['Approve- OD']), 'Comments'] = 'Approve After IC- OD'
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- OD', 'Approve After IC- MT']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    capture_snapshot("Step7")

    # ── Step 7: NQA lower boundary (₹25 001–₹25 999 → ₹26 000) ──────────────
    # ##mod 5-12 # removed foir: mod 5-15
    mask = (
        OT['New Monthly Income'].between(25_001, 25_999) &
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment',
            'Approve- OD', 'Approve After IC- MT',
        ])
    )
    OT.loc[mask, 'New Monthly Income'] = 26_000
    OT.loc[mask & OT['Comments'].isin(['Approve- OD']), 'Comments'] = 'Approve After IC- OD'
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- OD', 'Approve After IC- MT']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    capture_snapshot("Step8")

    # ── Step 8: NQA mid-range nudge (₹26 001–₹74 000 → +₹1 000) ─────────────
    mask = (
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment',
            'Approve- OD', 'Approve After IC- MT', 'Approve After IC- OD',
        ]) &
        OT['New Monthly Income'].between(26_001, 74_000)
    )
    OT.loc[mask & (OT['Comments'] == 'Approve- OD'), 'Comments'] = 'Approve After IC- OD'
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- OD', 'Approve After IC- MT']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    OT.loc[mask, 'New Monthly Income'] = OT.loc[mask, 'New Monthly Income'] + 1_000
    capture_snapshot("Step9")

    # ── Step 9: Below-minimum QA floor snap (< ₹13 000 → ₹13 000) ────────────
    mask = (
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment', 'Approve- MT',
            'Approve After IC- MT',
        ]) &
        (OT['New Monthly Income'] < 13_000)
    )
    OT.loc[mask, 'New Monthly Income'] = 13_000
    OT.loc[mask & (OT['Comments'] != 'Approve After IC- MT'), 'Comments'] = (
        'Approve After Income Reassessment'
    )
    capture_snapshot("Step10")

    # ── Step 10: NQA lower boundary (₹25 000–₹27 000 → ₹27 000) ─────────────
    mask = (
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment', 'Approve After IC- MT',
        ]) &
        OT['New Monthly Income'].between(25_000, 27_000, inclusive='neither')
    )
    OT.loc[mask, 'New Monthly Income'] = 27_000
    OT.loc[
        mask & ~OT['Comments'].isin(['Approve After IC- MT', 'Approve- OD', 'Approve- MT']),
        'Comments'
    ] = 'Approve After Income Reassessment'
    OT.loc[mask & OT['Comments'].isin(['Approve- OD']), 'Comments'] = 'Approve After IC- OD'
    capture_snapshot("Step11")

    # ── Step 11: Guard — New Income < previous Svamaan income ────────────────
    # For non-IGL1 products, the new income should never be below the previously
    # disbursed income (don't penalise customers for good historical performance).
    mask = (
        (OT['New Monthly Income'] < OT['Monthly Income']) &
        (OT['Monthly Income'] > OT['Income']) &
        OT['Comments'].isin([
            'Approve', 'Approve After Income Reassessment',
            'Approve After IC- MT', 'Approve After IC- OD', 'Approve- OD',
        ]) &
        (OT['Product'] != 'IGL 1')
    )
    OT.loc[mask, 'New Monthly Income'] = OT.loc[mask, 'Monthly Income']
    OT.loc[mask & OT['Comments'].isin(['FOIR', 'Approve']), 'Comments'] = (
        'Approve After Income Reassessment'
    )
    OT.loc[mask & OT['Comments'].isin(['Approve- OD']), 'Comments'] = 'Approve After IC- OD'
    capture_snapshot("Step12")

    if tracking_history is not None:
        print("\n" + "=" * 60)
        print(f" DEBUG REPORT FOR LEADS: {a}")
        print("=" * 60)
        # Pivot or format layout for crisp readability
        for lead_id in a:
            lead_track = tracking_history[tracking_history["Lead ID"] == lead_id]
            if not lead_track.empty:
                print(f"\n➔ Timeline for Lead ID: {lead_id}")
                print(
                    lead_track[["Step", "Comments", "New Monthly Income"]].to_string(
                        index=False
                    )
                )
        print("=" * 60 + "\n")

    OT['FOIR'] =  OT['Total Installment'] /OT['New Monthly Income']    
    return OT
    #, tests
# ── Orchestrator ──────────────────────────────────────────────────────────────

def Foir_Model(Bureau, Pos, run_date=None, mods = None, eval_all = None, OD_list = None, inc = None):
    
    today        = datetime.strptime(run_date, "%Y-%m-%d") if run_date is not None else datetime.now()
    date_15      = (today - timedelta(days=15)).strftime('%Y-%m-%d')
    date_45      = (today - timedelta(days=45)).strftime('%Y-%m-%d')
    processing_date = pd.Timestamp(run_date) if run_date else today.strftime('%Y-%m-%d')
    print(f"Processing date: {processing_date}")

    Summary, CB, CB_Date = Bureau[0], Bureau[1], Bureau[2]

    config = load_config()

    CB_mod, CB_Date_mod = filter_cb(CB, CB_Date, Summary , date_15, date_45, eval_all)
    print("CB filtered")

    Summary_mod = filter_summary(Summary, CB_Date_mod, Pos = Pos, inc = inc)
    print("Summary filtered")

    EMI = compute_emi_sheet(CB_mod, Summary_mod, config, processing_date)
    print(f"EMI rows     : {len(EMI)}, unique leads: {EMI['LEAD_ID'].nunique()}")

    Las = compute_las_sheet(EMI, CB_mod)
    print(f"LAS rows     : {len(Las)}, unique leads: {Las['LEAD_ID'].nunique()}")
    
    CV  = compute_cv_sheet(EMI, Summary_mod, Las, config)
    print(f"CV rows      : {len(CV)}, unique leads: {CV['Lead ID'].nunique()}")

    OT  = compute_ot_sheet(CV, EMI)

    print(f"CV rows      : {len(CV[CV_ORDER])}, unique leads: {CV['Lead ID'].nunique()}")
    
    print(f"OT rows      : {len(OT[OT_ORDER])}, unique leads: {OT['Lead ID'].nunique()}")
    

    if mods != 'False':
        OT_m = modis(OT, Las ,OD_list = OD_list)
        print('Output Modified')
        print(OT_m['Comments'].value_counts().to_string())
        label = "Total"
        count = len(OT)
        print(f"{label:<30} {count:>9}")
        return EMI[EMI_ORDER], CV[CV_ORDER], OT_m[OT_ORDER2], Las[LAS_ORDER], processing_date
    
    print(OT['Comments'].value_counts())    
    return EMI[EMI_ORDER], CV[CV_ORDER], OT[OT_ORDER], Las[LAS_ORDER], processing_date

def New_branch_product(OT, config, supplement_csv : str= "new_bp_limits.csv"): 
    OVERDUE_LIM = {
            'CTL': 5000, 'IGL 1': 3000, 'IGL 2': 3000,
            'IGL3Y': 3000, 'IGL3Y-90': 3000, 'MTL': 0, 'MTL R': 0,
    }

    _G1 = {
        'Good': {'IGL 1': 200000, 'IGL 2': 250000, 'CTL': 250000, 'MTL': 200000, 'MTL R': 250000},
        'Bad':  {'IGL 1': 175000, 'IGL 2': 200000, 'CTL': 250000, 'MTL': 175000, 'MTL R': 200000},
    }
    _G2 = {
        'Good': {'IGL 1': 250000, 'IGL 2': 300000, 'CTL': 300000, 'MTL': 250000, 'MTL R': 300000},
        'Bad':  {'IGL 1': 225000, 'IGL 2': 250000, 'CTL': 300000, 'MTL': 225000, 'MTL R': 250000},
    }
    _G3 = {
        'Good': {'IGL 1': 250000, 'IGL 2': 300000, 'CTL': 300000, 'MTL': 250000, 'MTL R': 300000,
                 'IGL3Y': 300000, 'IGL3Y-90': 300000},
        'Bad':  {'IGL 1': 225000, 'IGL 2': 250000, 'CTL': 300000, 'MTL': 225000, 'MTL R': 250000,
                 'IGL3Y': 250000, 'IGL3Y-90': 250000},  # note: 2500000 in original looks like a typo
    }

    STATE_TO_GROUP = {
        'BIHAR': _G1, 'MAHARASHTRA': _G1, 'CHHATTISGARH': _G1, 'HARYANA': _G1,
        'JHARKHAND': _G1, 'MADHYA PRADESH': _G1, 'ODISHA': _G1, 'RAJASTHAN': _G1,
        'UTTAR PRADESH': _G1,
        'TamilNadu_MT': _G2, 'TAMIL NADU': _G2, 'TAMILNADU MT': _G2, 'TELANGANA': _G2,
        'KARNATAKA': _G3,
    }

    MASTER_LIMITS: dict = {}
    for _state, _scores in STATE_TO_GROUP.items():
        for _score_type, _products in _scores.items():
            for _product, _limit in _products.items():
                MASTER_LIMITS[f"{_score_type}{_state.upper()}{_product}"] = _limit
    OT = OT.copy()

    OT['_BP'] = OT['Branch'].str.strip().str.capitalize() + OT['Product'].str.strip()

    existing_bps = set(config['os_good_cs'].keys())
    new_combos = (
        OT.loc[~OT['_BP'].isin(existing_bps), ['Branch', 'Product', 'State', '_BP']]
        .drop_duplicates(subset='_BP')
        .reset_index(drop=True)
    )

    if new_combos.empty:
        return pd.DataFrame(columns=[
            'Branch', 'Product', 'Branch Product',
            'Credit Limit - Good Score', 'Overdue Limit', 'Credit Limit - Bad Score',
        ])

    rows = []
    for _, row in new_combos.iterrows():
        state_up = str(row['State']).strip().upper()
        product  = str(row['Product']).strip()
        branch   = str(row['Branch']).strip().capitalize()
        bp       = row['_BP']

        good_lim = MASTER_LIMITS.get(f"Good{state_up}{product}")
        bad_lim  = MASTER_LIMITS.get(f"Bad{state_up}{product}")

        if good_lim is None or bad_lim is None:
            print(f"[New_branch_product] WARNING: No limit found for state='{row['State']}' "
                  f"product='{product}'. BP '{bp}' skipped.")
            continue

        rows.append({
            'Branch':                    branch,
            'Product':                   product,
            'Branch Product':            bp,
            'Credit Limit - Good Score': good_lim,
            'Overdue Limit':             OVERDUE_LIM.get(product, 0),
            'Credit Limit - Bad Score':  bad_lim,
        })

    new_df = pd.DataFrame(rows)

    for _, row in new_df.iterrows():
        config['os_good_cs'][row['Branch Product']] = row['Credit Limit - Good Score']
        config['os_bad_cs'][row['Branch Product']]  = row['Credit Limit - Bad Score']
        
    try:
        existing = pd.read_csv(supplement_csv)
        updated  = pd.concat([existing, new_df], ignore_index=True).drop_duplicates(
            subset='Branch Product', keep='last'
        )
    except FileNotFoundError:
        updated = new_df
    updated.to_csv(supplement_csv, index=False)
    return new_df
    
    updated.to_csv(supplement_csv, index=False)
