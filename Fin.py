import os
import sys
import shutil
import tempfile
import logging
import decimal
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import numpy_financial as npf
from typing import Union, Optional, List



_base_dir = Path(__file__).resolve().parent

def _load_dotenv_fin():
    env_path = _base_dir / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if " #" in val:
                        val = val[:val.index(" #")].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ[key] = val

_load_dotenv_fin()

def _resolve_dict_path(path: str) -> str:
    if os.path.isabs(path) and os.path.exists(path):
        return path
    env_dict_path = os.environ.get("DICT_PATH")
    if env_dict_path and os.path.exists(env_dict_path):
        return env_dict_path
    rel_files_path = _base_dir / "files" / path
    if rel_files_path.exists():
        return str(rel_files_path)
    rel_base_path = _base_dir / path
    if rel_base_path.exists():
        return str(rel_base_path)
    cwd_path = Path(path)
    if cwd_path.exists():
        return str(cwd_path.resolve())
    return str(_base_dir / "files" / path)

def _resolve_supplement_path(path: str) -> str:
    if os.path.isabs(path) and os.path.exists(path):
        return path
    rel_base_path = _base_dir / path
    if rel_base_path.exists():
        return str(rel_base_path)
    cwd_path = Path(path)
    if cwd_path.exists():
        return str(cwd_path.resolve())
    return str(_base_dir / path)

existing_dict= "dicts_age.csv"
new_dict     = "new_bp_limits.csv"

print_modis = "Yes"
AC_CLOSED_MONTHS = 0
CUTOFF_DATE = pd.Timestamp('2022-09-30')
supplememt_csv = "new_bp_limits.csv"

BULLET_LOANS = [
    'Business Loan - Priority Sector- Agriculture',
    'Business Loan Against Bank Deposits',
    'Business Non-Funded Credit Facility - Priority Sector - Agriculture',
    'Corporate Credit Card',
    'Loan Against Bank Deposits',
    'Loan against Shares/Securities',
    'Loan on Credit Card',
    'Mudra Loans - Shishu / Kishor / Tarun',
    'Overdraft',
    'Prime Minister Jaan Dhan Yojana - Overdraft',
    'Priority Sector- Gold Loan [Secured]',
    'Secured Credit Card',
    'Business Loan - Priority Sector - Agriculture',
]

FILTERED_PRODUCTS = [
    "IGL-R-3 YEAR WEEKLY 75K", "IGL-R- 3 YEAR WEEKLY 90K",
    "IGL-R- 3 YEAR BI-WEEKLY 90K", "IGL-R- 3 YEAR BI-WEEKLY 75K",
    "IGL-R- 2 YEAR WEEKLY 75K", "MYS IGL-R- 2 YEAR WEEKLY 65K",
    "IGL-R-2 YEAR BI-WEEKLY 75K", "IGL-R- 2 YEAR WEEKLY 60K",
    "IGL-R-Cycle 3- 3 YEAR WEEKLY 90K", "IGL-R-Cycle 3- 2 YEAR WEEKLY 75K",
    "IGL-R- 1.5 YEAR WEEKLY 29K", "IGL-R- 3 YEAR WEEKLY 90K-KA",
    "IGL-R- 3 YEAR BI-WEEKLY 90K-KA", "IGL-R-3 YEAR WEEKLY 75K-KA",
    "IGL-R- 2 YEAR WEEKLY 70K", "IGL-R- 1 YEAR WEEKLY 22K",
    "IGL-R- 1.5 YEAR WEEKLY 45K", "IGL-R- 1 YEAR WEEKLY 30K",
    "IGL-R- 2 YEAR BI-WEEKLY 45K", "IGL-R- 2 YEAR WEEKLY",
    "IGL-R-2 YEAR BI-WEEKLY", "IGL-R- 1.5 YEAR WEEKLY",
    "IGL-R- 2 YEAR BI-WEEKLY", "IGL-R- 1 YEAR WEEKLY",
    "MT - IGL-R-2 YEAR WEEKLY", "IGL-R- 1.5 BI-WEEKLY",
    "IGL-R- 2 YEAR 1 Lakh WEEKLY", "IGL-R-2 YEAR 1 Lakh BI-WEEKLY",
]

TERMINAL_STATUSES = []

COAPP_EXCL = [
    'Brother', 'Daughter', 'Sister', 'Grand Father', 'Mother',
    'Wife', 'BrotherInLaw', 'MotherInLaw', 'FatherInLaw',
]

OVERDUE_LIM = {
    'CTL': 5000,
    'IGL 1': 3000,
    'IGL 2': 3000,
    'IGL3Y': 3000,
    'IGL3Y-90': 3000,
    'MTL': 0,
    'MTL R': 0,
}

EMI_ORDER = [
    'LEAD_ID', 'Name of the Institution', 'Account Status', 'Loan Category',
    'Source', 'Open Status', 'Past Due', 'Current Balance', 'Sanction Amount',
    'Date Reported', 'Date Opened', 'Interest Rate', 'No Of Installments',
    'Term Frequency', 'EMI', 'A/C Closed Check', 'Final EMI',
    'Include in FOIR', 'Remarks', 'Equifax ID', 'Relation',
    'Joint Account Identifier', 'Date Closed', 'Bullet Loan Check',
    'Check Bullet', 'A9', 'A10', 'FOIR10', 'Remark9', 'Remark10',
    'Remark_Final', 'STEP 1', 'Adjusted EMI', 'Include in FOIR_l',
]
#credit validation sheet in Leads at COB 
CV_ORDER = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
    'Credit Score', 'Comments', 'O/s Check', 'Overdue Check',
    'Lender Check', 'FOIR Check', 'MFI Outstanding',
    'MFI PastDue & Overdue', 'Total Installment', 'Final EMI',
    'Monthly Income', 'FOIR', 'New Monthly Income',
    'MFI OUTSTANDING 2', 'shg 10%', 'shg_indiv_10%', 'svmn', 'X', 'Final O/s',
    'Lenders', 'OS_Lim',
]

#shg 10% and shg_indiv_10% shouldnt even exist at CV_order , need to use the OT_order

#model output in LEADS at COB
OT_ORDER = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
    'Credit Score', 'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue',
    'Total Installment', 'Monthly Income', 'FOIR', 'New Monthly Income',
    'Lender Count', 'Rejection Reasons',
]

#model output in leads at COB after step 15?
OT_ORDER2 = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
    'Credit Score', 'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue',
    'Total Installment', 'Monthly Income', 'FOIR', 'New Monthly Income',
    'Lender Count', 'Income', 'Rejection Reasons',
]

#Loan Wise sheet at Leads at cob
LAS_ORDER = [
    'LEAD_ID', 'Name of the Institution', 'Date Opened', 'Sanction Amount',
    'Current Balance', 'Final EMI', 'Include in FOIR', 'Remarks',
    'Equifax ID', 'Source', 'Date Reported', 'Joint Account Identifier',
    'Relation', 'Term freq.', 'ACCOUNT_STATUS', 'Loan_Category',
]

def load_lender_mapping(path: str = "Lender Names to be combined 1.xlsx") -> dict:
    """Load mapping of variant institution names to canonical lender names."""
    path = _resolve_supplement_path(path)
    if not os.path.exists(path):
        return {}
    try:
        df = pd.read_excel(path)
        if df.shape[1] >= 2:
            col_src = df.columns[0]
            col_tgt = df.columns[1]
            for c in df.columns:
                cl = str(c).strip().lower()
                if any(k in cl for k in ['raw', 'bureau', 'original', 'old', 'from', 'source', 'institution']):
                    col_src = c
                elif any(k in cl for k in ['comb', 'map', 'stand', 'new', 'final', 'group', 'to', 'target']):
                    col_tgt = c
            valid_df = df.dropna(subset=[col_src, col_tgt])
            mapping = {str(k).strip(): str(v).strip() for k, v in zip(valid_df[col_src], valid_df[col_tgt]) if str(k).strip()}
            return mapping
    except Exception as e:
        print(f"[load_lender_mapping] WARNING: Could not load '{path}': {e}")
    return {}


def load_config(
        path: str = None,
        supplement_csv: str = None,
        lender_mapping_file: str = "Lender Names to be combined 1.xlsx"
) -> dict:
    if path is None:
        path = existing_dict
    if supplement_csv is None:
        supplement_csv = new_dict

    path = _resolve_dict_path(path)
    supplement_csv = _resolve_supplement_path(supplement_csv)

    if os.path.exists(path):
        try:
            dicts = pd.read_csv(path)
        except Exception:
            dicts = pd.DataFrame()
    else:
        dicts = pd.DataFrame()

    # Robust column matching ignoring surrounding whitespace
    col_map = {str(c).strip().lower(): c for c in dicts.columns}

    def _safe_dict(key_col_name, val_col_name):
        k_col = col_map.get(key_col_name.strip().lower())
        v_col = col_map.get(val_col_name.strip().lower())
        if k_col and v_col and k_col in dicts.columns and v_col in dicts.columns:
            return dicts.set_index(k_col)[v_col].dropna().to_dict()
        return {}

    branch_col = col_map.get('branch', 'Branch ')
    prod_col = col_map.get('product', 'Product')
    if branch_col in dicts.columns and prod_col in dicts.columns:
        dicts['BP'] = dicts[branch_col].astype(str).str.capitalize() + dicts[prod_col].astype(str)

    fo_emi     = _safe_dict('Product List', 'Proposed EMI')
    int_rates  = _safe_dict('Name of the Loan', 'Interest Rate Min (months)')
    tenure     = _safe_dict('Name of the Loan', 'Tenure Min (months)')
    inst_types = _safe_dict('Name of the Loan', 'Loan Type')

    keep_cols = ['BP', 'Credit Limit - Good Score', 'Credit Limit - Bad Score']
    valid_master_cols = [c for c in keep_cols if c in dicts.columns]
    master_slim = dicts[valid_master_cols].copy() if valid_master_cols else pd.DataFrame()

    try:
        if os.path.exists(supplement_csv):
            supplement = pd.read_csv(supplement_csv)
        else:
            supplement = pd.DataFrame()
        if 'BP' not in supplement.columns:
            if 'Branch ' in supplement.columns and 'Product' in supplement.columns:
                supplement['BP'] = supplement['Branch '].str.capitalize() + supplement['Product']
            elif 'Branch Product' in supplement.columns:
                supplement['BP'] = supplement['Branch Product']
            elif 'Branch' in supplement.columns and 'Product' in supplement.columns:
                supplement['BP'] = supplement['Branch'].str.capitalize() + supplement['Product']
        valid_supp_cols = [c for c in keep_cols if c in supplement.columns]
        supplement = supplement[valid_supp_cols] if valid_supp_cols else pd.DataFrame()
        if not master_slim.empty and not supplement.empty and 'BP' in master_slim.columns and 'BP' in supplement.columns:
            merged = pd.concat([master_slim, supplement], ignore_index=True).drop_duplicates(
                subset='BP', keep='last'
            )
        elif not master_slim.empty:
            merged = master_slim
        else:
            merged = supplement
    except Exception:
        merged = master_slim

    os_good_cs = merged.set_index('BP')['Credit Limit - Good Score'].dropna().to_dict() if ('BP' in merged.columns and 'Credit Limit - Good Score' in merged.columns) else {}
    os_bad_cs  = merged.set_index('BP')['Credit Limit - Bad Score'].dropna().to_dict() if ('BP' in merged.columns and 'Credit Limit - Bad Score' in merged.columns) else {}

    lender_mapping = load_lender_mapping(lender_mapping_file)

    return {
        'fo_emi':         fo_emi,
        'int_rates':      int_rates,
        'tenure':         tenure,
        'inst_types':     inst_types,
        'os_good_cs':     os_good_cs,
        'os_bad_cs':      os_bad_cs,
        'lender_mapping': lender_mapping,
    }

# ------------------------------------------------------------
# --- utils.py ---
# ------------------------------------------------------------
from typing import Union, Optional, List


def convert_to_excel(
    file_name:  str,
    sheets_dict: dict[str, pd.DataFrame],
    hide_sheets: str = None
) -> None:
    if isinstance(hide_sheets, str):
        hide_sheets = [hide_sheets]
    elif hide_sheets is None:
        hide_sheets = []

    Path(file_name).parent.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelWriter(file_name, engine="xlsxwriter") as writer:
            for sheet_name, df in sheets_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, startrow=2, startcol=1, index=False, header=False)

            workbook = writer.book
            header_format = workbook.add_format(
                {"bold": True, "valign": "top", "fg_color": "#44B3E1", "border": 1}
            )
            cell_border_format = workbook.add_format({"border": 1})
            for sheet_name, worksheet in writer.sheets.items():
                if sheet_name in hide_sheets:
                    worksheet.hide()
                df = sheets_dict[sheet_name]
                start_row = 1
                end_row = 2 + len(df) - 1
                start_col = 1
                end_col = len(df.columns)
                worksheet.conditional_format(
                    start_row, start_col, end_row, end_col,
                    {"type": "formula", "criteria": "=TRUE()", "format": cell_border_format}
                )
                for col_idx, col in enumerate(df.columns):
                    max_len = df.iloc[:, col_idx].fillna('').astype(str).str.len().max()
                    col_len = max(max_len, len(str(col))) + 2
                    target_col = col_idx + 1
                    worksheet.set_column(target_col, target_col, col_len)
                    worksheet.write(1, target_col, col, header_format)
    except PermissionError as e:
        raise PermissionError(
            f"Permission denied while attempting to write to Excel file: '{file_name}'.\n"
            f"--> Please close '{Path(file_name).name}' in Microsoft Excel if it is currently open, or check if OneDrive is syncing/locking the file."
        ) from e


def extract_psc_od_approvals(OT: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts PSC and OD approved leads with only the required columns:
    ['Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name']
    """
    psc_od_cols = ['Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name']
    psc_od = OT[OT['Comments'].isin([
        'Poor Credit Score',
        'Overdue&WriteOff',
    ])]
    existing_cols = [c for c in psc_od_cols if c in psc_od.columns]
    return psc_od[existing_cols]


def export_psc_od_approvals(
    OT: pd.DataFrame,
    file_path: Union[str, Path]
) -> None:
    """
    Filters OT for PSC & OD approvals with only the required 6 columns
    and exports them to an Excel file with sheet name 'PSC & OD Approvals'.
    """
    psc_od_approvals = extract_psc_od_approvals(OT)
    convert_to_excel(
        file_name=str(file_path),
        sheets_dict={
            "PSC & OD Approvals": psc_od_approvals
        }
    )


def _resolve_if_needed(path: str) -> str:
    if not path:
        return ""
    path = path.strip().strip('"').strip("'")
    p = Path(path)
    if p.is_absolute():
        return path
    if p.exists():
        return str(p.resolve())

    has_glob = any(c in path for c in '*?[]')
    if not has_glob:
        return path

    files_dir = os.environ.get("FILES_DIR")
    if files_dir:
        try:
            candidates = sorted(Path(files_dir).glob(path))
            if candidates:
                return str(candidates[-1])
        except NotImplementedError:
            pass
    try:
        candidates = sorted(Path().glob(path))
        if candidates:
            return str(candidates[-1])
    except NotImplementedError:
        pass
    script_dir = Path(__file__).resolve().parent.parent
    try:
        candidates = sorted((script_dir / "files").glob(path))
        if candidates:
            return str(candidates[-1])
    except NotImplementedError:
        pass
    return path


def read_file(
    path: str,
    sheet_name: Union[int, str] = 0,
    usecols: Optional[Union[int, str, List[Union[int, str]]]] = None,
) -> pd.DataFrame:
    path = _resolve_if_needed(path)
    if not path:
        return pd.DataFrame()

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: '{path}'")

    if path.endswith('.csv'):
        try:
            df = pd.read_csv(path, header=None)
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied while reading CSV file: '{path}'.\n"
                f"--> Please close the file in Excel or check if OneDrive is syncing/locking it."
            ) from e
    elif path.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, header=None, engine='calamine')
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied while reading Excel file: '{path}'.\n"
                f"--> Please close '{file_path.name}' in Microsoft Excel if it is open, or check if OneDrive is syncing/locking it."
            ) from e
        except Exception:
            try:
                df = pd.read_excel(path, sheet_name=sheet_name, header=None, engine='openpyxl')
            except PermissionError as e:
                raise PermissionError(
                    f"Permission denied while reading Excel file: '{path}'.\n"
                    f"--> Please close '{file_path.name}' in Microsoft Excel if it is open, or check if OneDrive is syncing/locking it."
                ) from e
            except Exception:
                for enc in [None, 'utf-8-sig', 'utf-16', 'latin-1']:
                    try:
                        kwargs = {'header': None}
                        if enc:
                            kwargs['encoding'] = enc
                        df = pd.read_csv(path, **kwargs)
                        break
                    except PermissionError as e:
                        raise PermissionError(
                            f"Permission denied while reading file: '{path}'.\n"
                            f"--> Please close '{file_path.name}' in Microsoft Excel if it is open, or check if OneDrive is syncing/locking it."
                        ) from e
                    except Exception:
                        continue
                else:
                    raise ValueError(f"Unable to read file: {path}")
    else:
        raise ValueError(f"Unsupported file type: {path}")
    return clean_df(df, usecols=usecols)


def clean_df(
    df: pd.DataFrame,
    min_header_fill: float = 0.5,
    usecols: Optional[Union[int, str, List[Union[int, str]]]] = None,
) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    while not df.empty:
        if df.iloc[:, 0].replace(0, pd.NA).isna().all():
            df = df.iloc[:, 1:].reset_index(drop=True)
        else:
            break
    first_data_row = 0
    while first_data_row < len(df):
        row = df.iloc[first_data_row].replace(0, pd.NA)
        fill_ratio = row.notna().sum() / len(row)
        if fill_ratio >= min_header_fill:
            break
        first_data_row += 1
    df.columns = df.iloc[first_data_row]
    df = df.iloc[first_data_row + 1:].reset_index(drop=True)
    df.columns.name = None
    if usecols is not None:
        if isinstance(usecols, (int, str)):
            usecols = [usecols]
        if all(isinstance(c, int) for c in usecols):
            df = df.iloc[:, usecols]
        else:
            df = df[usecols]
    return df

# ------------------------------------------------------------
# --- column_normalizer.py ---
# ------------------------------------------------------------
"""
Column Normalizer Module
========================
Provides schema mappings and column normalization utilities to convert raw 
MS SQL query output column names to the standardized headers expected by the pipeline.
"""


# Comprehensive Mapping for raw SQL output (scrub.sql) -> Pipeline Code Expectations
SCRUB_SQL_MAP = {
    'LEAD_ID': 'LEAD ID',
    'CB_DATE': 'CB DATE',
    'CB_STATUS': 'CB STATUS',
    'STATE': 'State',
    'Blank Intentionally_1': 'Center',
    'Branch_Name': 'Branch Name',
    'Co-Borrowers Name': 'Co Borrowers Name',
    "Members's Address": "Members's Address",
    'Co_Applicant_Total_Outstanding_Balance': 'Co Applicant Total Outstanding Balance',
    'Blank Intentionally_2': 'Co Applicant CB Date',
    'Blank Intentionally_5': 'Applicant Total Monthly Installment',
    'Blank Intentionally_6': 'Co-Applicant Total Monthly Installment',
    'Blank Intentionally_7': 'Household Total Monthly Income',
    'Blank Intentionally_8': 'FOIR  %',
    'CreatedDate': 'Created Date',
    'NO of ACTIVE ACCOUNTS': 'NO OF ACTIVE ACCOUNTS',
    'TOT_PAST_DUE': 'TOT PAST DUE',
    'NO_PAST_DUE_ACCNT': 'NO PAST DUE ACCNT',
    'TOT_BAL_AMT': 'TOT BAL AMT',
    'TOT_MON_PAY_AMT': 'TOT MON PAY AMT',
    'TOT_WRT_OFF_AMT': 'TOT WRT OFF AMT',
}


def normalize_scrub(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes column headers of a raw SQL Scrub DataFrame to match pipeline expectations.
    Ensures both apostrophe and non-apostrophe variations exist to satisfy scrub.py indexing.
    """
    if df is None or df.empty:
        return df
    
    # 1. Deduplicate & Rename raw SQL headers
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df = df.rename(columns=SCRUB_SQL_MAP)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    # 2. Synchronize Members's Address vs Members s Address
    if "Members's Address" in df.columns and "Members s Address" not in df.columns:
        df["Members s Address"] = df["Members's Address"]
    elif "Members s Address" in df.columns and "Members's Address" not in df.columns:
        df["Members's Address"] = df["Members s Address"]

    # 3. Synchronize Family Monthly Income vs Household Total Monthly Income
    if "Family Monthly Income" in df.columns and "Household Total Monthly Income" not in df.columns:
        df["Household Total Monthly Income"] = df["Family Monthly Income"]
    elif "Household Total Monthly Income" in df.columns and "Family Monthly Income" not in df.columns:
        df["Family Monthly Income"] = df["Household Total Monthly Income"]
        
    # Zero-division protection on income series
    if "Household Total Monthly Income" in df.columns:
        series = df["Household Total Monthly Income"]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        df["Household Total Monthly Income"] = pd.to_numeric(series, errors='coerce').replace(0, np.nan)
        
    if "Family Monthly Income" in df.columns:
        series = df["Family Monthly Income"]
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]
        df["Family Monthly Income"] = pd.to_numeric(series, errors='coerce').replace(0, np.nan)

    return df


def normalize_emi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes EMI DataFrame headers for downstream credit validation sheets.
    """
    if df is None or df.empty:
        return df
    if 'Sanctioned Amount' not in df.columns and 'Sanction Amount' in df.columns:
        df['Sanctioned Amount'] = df['Sanction Amount']
    return df

# ------------------------------------------------------------
# --- data_fetcher.py ---
# ------------------------------------------------------------
"""
data_fetcher.py — MS SQL Server Data Extractor
Pulls daily raw input data from MS SQL Server using pyodbc with SSL TrustServerCertificate fix.
"""

import shutil
import tempfile
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("data_fetcher")

# Resolve root path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


def get_mssql_connection():
    """
    Connects to MS SQL Server using pyodbc with TrustServerCertificate=yes & Encrypt=no
    to resolve ODBC Driver 18 untrusted SSL certificate errors.
    """
    import pyodbc

    server   = os.getenv("MSSQL_SERVER", "192.168.10.111").strip()
    port     = os.getenv("MSSQL_PORT", "1440").strip()
    database = os.getenv("MSSQL_DATABASE", "SVAMAAN_DEV_NEW").strip()
    username = os.getenv("MSSQL_USER", "SC032").strip()
    password = os.getenv("MSSQL_PASSWORD", "").strip()
    driver   = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    trusted  = os.getenv("MSSQL_TRUSTED_CONNECTION", "no").lower() in ("yes", "true", "1")

    # Format server endpoint (e.g. 192.168.10.111,1440)
    if "," in server:
        server_target = server
    elif port and str(port).strip() and str(port).strip() != "1433":
        server_target = f"{server},{port}"
    else:
        server_target = server

    # Escaped password string
    pwd_escaped = password.replace("}", "}}") if "}" in password else password

    # List of connection string variations (starting with TrustServerCertificate=yes & Encrypt=no)
    if trusted:
        conn_strings = [
            f"DRIVER={{{driver}}};SERVER={server_target};DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;Encrypt=no;",
            f"DRIVER={{{driver}}};SERVER={server_target};DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;",
        ]
    else:
        conn_strings = [
            # 1. Driver 18 with TrustServerCertificate=yes & Encrypt=no
            f"DRIVER={{{driver}}};SERVER={server_target};DATABASE={database};UID={username};PWD={pwd_escaped};TrustServerCertificate=yes;Encrypt=no;",
            # 2. Driver 18 with TrustServerCertificate=yes & Encrypt=yes
            f"DRIVER={{{driver}}};SERVER={server_target};DATABASE={database};UID={username};PWD={pwd_escaped};TrustServerCertificate=yes;Encrypt=yes;",
            # 3. Driver 18 with raw password & TrustServerCertificate=yes
            f"DRIVER={{{driver}}};SERVER={server_target};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;Encrypt=no;",
            # 4. Fallback to legacy SQL Server driver
            f"DRIVER={{SQL Server}};SERVER={server_target};DATABASE={database};UID={username};PWD={password};",
        ]

    last_err = None
    for i, cs in enumerate(conn_strings, 1):
        try:
            log_cs = cs.replace(password, "*******") if password else cs
            logger.info(f"Attempting MS SQL connection ({i}/{len(conn_strings)}): {log_cs}")
            conn = pyodbc.connect(cs, timeout=10)
            logger.info(f"✓ Successfully connected to MS SQL Server ({server_target}/{database})!")
            return conn
        except Exception as e:
            last_err = e

    logger.error(f"All connection attempts failed. Last error: {last_err}")
    raise last_err


def fetch_query(query_or_file: str, conn=None) -> pd.DataFrame:
    """
    Executes a SQL query string or reads a .sql file, returning a pandas DataFrame.
    """
    sql_text = query_or_file
    if os.path.exists(query_or_file):
        with open(query_or_file, "r", encoding="utf-8") as f:
            sql_text = f.read()

    close_conn = False
    if conn is None:
        conn = get_mssql_connection()
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute(sql_text)
        # Advance past any non-SELECT statements (SET NOCOUNT ON, USE db, etc.)
        while cursor.description is None:
            if not cursor.nextset():
                raise RuntimeError("Query returned no result set (all statements were non-SELECT)")
        cols = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame.from_records(rows, columns=cols)
        logger.info(f"Query executed successfully. Retrieved {len(df)} rows.")
        return df
    finally:
        if close_conn and hasattr(conn, "close"):
            conn.close()


def fetch_all_inputs(run_date: datetime = None) -> str:
    """
    Pulls all daily input tables from MS SQL Server and saves them into DataResolver().inputs_dir.
    Returns the target inputs directory path as a string.
    """
    resolver = DataResolver(run_date=run_date)
    target_dir = resolver.inputs_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    date_str = resolver.date_str
    run_dt = resolver.run_date

    # Dynamic date formats for output filenames
    bureau_date  = run_dt.strftime("%d%b%Y").upper()           # e.g. 24JUL2026
    scrub_date   = f"{run_dt.day}{run_dt.month}{run_dt.year}" # e.g. 1672026  (no leading zeros)
    demog_date   = run_dt.strftime("%d%B%Y").upper()           # e.g. 17JULY2026

    # SQL files live in the pipeline code folder, not the data root
    queries_dir = Path(__file__).resolve().parent.parent / "queries"

    # 1. Fetch & Export BUREAU Workbook (4 sheets: Summary, CB, CB Date, DOB)
    bureau_file = target_dir / f"BUREAU SPLIT {bureau_date}.xlsx"
    try:
        from export_bureau import export_bureau_data
        logger.info(f"Executing Bureau Multi-sheet Query -> {bureau_file.name}")
        export_bureau_data(output_filepath=str(bureau_file), run_date=date_str)
    except Exception as e:
        logger.error(f"Error exporting Bureau data: {e}")

    # 2. Fetch SCRUB File
    scrub_file = target_dir / f"COB CB Scrub__{scrub_date}.xlsx"
    scrub_sql_path = queries_dir / "scrub.sql"
    if not scrub_sql_path.exists():
        scrub_sql_path = queries_dir / "COB SCRUB FILE.sql"

    if scrub_sql_path.exists():
        logger.info(f"Running Scrub Query '{scrub_sql_path.name}' -> {scrub_file.name}")
        conn = get_mssql_connection()
        try:
            df_scrub = fetch_query(str(scrub_sql_path), conn=conn)
            df_scrub = normalize_scrub(df_scrub)
            with pd.ExcelWriter(str(scrub_file), engine="openpyxl") as writer:
                df_scrub.to_excel(writer, index=False)
            logger.info(f"Saved {scrub_file.name} ({len(df_scrub)} rows) to {scrub_file}")
        finally:
            if hasattr(conn, "close"):
                conn.close()

    # 3. Fetch DEMOGRAPHIC File
    demog_file = target_dir / f"Demographic data_{demog_date}.xlsx"
    demog_sql_path = queries_dir / "demographic.sql"
    if not demog_sql_path.exists():
        demog_sql_path = queries_dir / "Customer Demographic with Bank details - Akash.sql"

    if demog_sql_path.exists():
        logger.info(f"Running Demographic Query '{demog_sql_path.name}' -> {demog_file.name}")
        conn = get_mssql_connection()
        try:
            df_demog = fetch_query(str(demog_sql_path), conn=conn)
            with pd.ExcelWriter(str(demog_file), engine="openpyxl") as writer:
                df_demog.to_excel(writer, index=False)
            logger.info(f"Saved {demog_file.name} ({len(df_demog)} rows) to {demog_file}")
        finally:
            if hasattr(conn, "close"):
                conn.close()

    logger.info(f"All MS SQL data inputs downloaded successfully to: {target_dir}")
    return str(target_dir)

# ------------------------------------------------------------
# --- emi_calc_sheet.py ---
# ------------------------------------------------------------



def compute_emi_calculation_sheet(
    EMI: pd.DataFrame,
) -> pd.DataFrame:
    cols = [c for c in EMI_ORDER if c in EMI.columns]
    sheet = EMI[cols].copy()
    sheet.insert(0, '#', range(1, len(sheet) + 1))
    return sheet


def emi_summary(
    EMI: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    by_institution = EMI.groupby('Name of the Institution').agg(
        Count=('LEAD_ID', 'nunique'),
        Total_EMI=('EMI', 'sum'),
        Total_Adjusted_EMI=('Adjusted EMI', 'sum'),
    ).reset_index()

    by_remark = EMI.groupby('Remark_Final').agg(
        Count=('LEAD_ID', 'count'),
    ).reset_index()

    return {
        'By Institution': by_institution,
        'By Remark': by_remark,
    }


def export_emi_calculation_sheet(
    EMI: pd.DataFrame,
    file_path: str,
    hide_summary: bool = True,
) -> None:
    emi_calc = compute_emi_calculation_sheet(EMI)
    summaries = emi_summary(EMI)

    sheets = {
        'EMI Calculation': emi_calc,
        **summaries,
    }

    hide = list(summaries.keys()) if hide_summary else None
    convert_to_excel(file_path, sheets, hide_sheets=hide)

# ------------------------------------------------------------
# --- foir_emi.py ---
# ------------------------------------------------------------
import decimal
import numpy_financial as npf



def _cap_and_label(
    tenure_factor,
    sanction,
    a9,
    remark_if_capped,
    base_remark=None
):
    calc      = pd.to_numeric(tenure_factor) * pd.to_numeric(sanction) / 1_000
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
        d_num   = decimal.Decimal(str(number))
        rounded = round(d_num, digits)
        return float(rounded)
    except (decimal.InvalidOperation, ValueError, TypeError):
        return 0


def compute_emi_sheet(
    CB_mod: pd.DataFrame,
    Summary_mod: pd.DataFrame,
    config: dict,
    processing_date: pd.Timestamp
) -> pd.DataFrame:
    int_rates  = config['int_rates']
    tenure     = config['tenure']
    inst_types = config['inst_types']

    raw_rate = pd.to_numeric(
        CB_mod['INTEREST_RATE'].astype(str).str.replace('%', '', regex=False),
        errors='coerce'
    ).fillna(0)
    is_retail    = CB_mod['CB_TYPE'].isin(['COAPP- RETAIL', 'CCR- RETAIL'])
    rate_lookup  = pd.to_numeric(
        CB_mod['INSTITUTION'].map(int_rates).astype(str).str.replace('%', '', regex=False),
        errors='coerce'
    ).fillna(0)
    interest_rate = np.where(is_retail & (raw_rate == 0), rate_lookup, raw_rate)

    # ── Resolve ticket-size tenure lookup for unreliable bureau NOI (0-3 or 0-10) ──
    sax_amt  = pd.to_numeric(CB_mod['SANCTION_AMOUNT'], errors='coerce').fillna(0)
    bal_amt  = pd.to_numeric(CB_mod['CURRENT_BALANCE'], errors='coerce').fillna(0)
    prin_amt = np.where(sax_amt == 0, bal_amt, sax_amt)

    ticket_tenure_cond = [
        prin_amt <= 10_000,
        prin_amt <= 25_000,
        prin_amt <= 50_000,
        prin_amt <= 80_000,
    ]
    ticket_tenure_val = [4, 10, 20, 32]
    ticket_tenure = np.select(ticket_tenure_cond, ticket_tenure_val, default=52)

    raw_noi     = pd.to_numeric(CB_mod['NO_OF_INSTALLMENTS'], errors='coerce').fillna(0)
    inst_tenure = pd.to_numeric(CB_mod['INSTITUTION'].map(tenure), errors='coerce').fillna(0)

    noi = np.where(
        is_retail & (raw_noi > 10),
        raw_noi,
        np.where(
            is_retail & (inst_tenure > 0),
            inst_tenure,
            np.where(
                raw_noi <= 10,
                ticket_tenure,
                raw_noi
            )
        )
    )

    term_freq = CB_mod['TERM_FREQUENCY'].astype(str)
    term_freq = np.where((term_freq == '0') | (term_freq == ''), 'Monthly', term_freq)

    E = pd.DataFrame({
        'Equifax ID':               CB_mod['EQUIFAXID'].values,
        'LEAD_ID':                  CB_mod['LEAD_ID'].values,
        'Name of the Institution':  CB_mod['INSTITUTION'].values,
        'Account Status':           CB_mod['ACCOUNT_STATUS'].values,
        'Loan Category':            CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].values,
        'Source':                   CB_mod['CB_TYPE'].values,
        'Open Status':              CB_mod['AC_OPEN'].values,
        'Past Due': (
            pd.to_numeric(CB_mod['PAST_DUE_AMOUNT'],   errors='coerce').fillna(0) +
            pd.to_numeric(CB_mod['WRITTENOFF_AMOUNT'], errors='coerce').fillna(0)
        ).values,
        'Current Balance':   pd.to_numeric(CB_mod['CURRENT_BALANCE'],  errors='coerce').fillna(0).values,
        'Sanction Amount':   pd.to_numeric(CB_mod['SANCTION_AMOUNT'],  errors='coerce').fillna(0).values,
        'Date Reported':     pd.to_datetime(CB_mod['DATE_REPORTED'],   errors='coerce').values,
        'Date Opened':       pd.to_datetime(CB_mod['DATE_OPENED'],     errors='coerce').values,
        'Date Closed':       pd.to_datetime(CB_mod['DATE_CLOSED'],     errors='coerce').values,
        'Interest Rate':     interest_rate,
        'No Of Installments': np.nan_to_num(pd.to_numeric(noi, errors='coerce'), nan=0),
        'Term Frequency':    term_freq,
        'INSTALLMENT_AMOUNT': CB_mod['INSTALLMENT_AMOUNT'].values,
        
    })

    E['Relation']          = E['LEAD_ID'].map(Summary_mod.set_index('LEAD_ID')['COAPP_RELATION'])
    E['Bullet Loan Check'] = E['Name of the Institution'].map(inst_types).fillna('NA')
    E['Check Bullet']      = np.where(
        E['Name of the Institution'].isin(BULLET_LOANS),
        E['Name of the Institution'],
        7
    )

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

    principal = np.where(SAX == 0, BAL, SAX)

    nper_retail = pd.to_numeric(E['No Of Installments']) * np.where(
        freq == 'Annually',    12,
        np.where(freq == 'Quarterly',    3,
        np.where(freq == 'Semiannually', 6, 1))
    )

    mfi_nper = pd.to_numeric(E['No Of Installments']) * np.where(
        freq == 'Bi-weekly', 0.5,
        np.where(freq == 'Weekly',    0.25,
        np.where(freq == 'Bimonthly', 2,    1))
    )

    rate         = pd.to_numeric(E['Interest Rate'], errors='coerce').fillna(0)
    rate_divisor = np.where(rate >= 1, 1200, 12)

    SHG_BAL = np.where(SAX == 0, BAL, SAX)
    SHG_BAL = np.where(
        SHG_BAL >= 15_00_000, SHG_BAL/15, SHG_BAL/10)
    SHG_EQ_CUR_SAX = ((INST.between(SAX- 100, SAX+ 100)) | (INST.between(BAL - 100, BAL+ 100)))

    shg_group_tenure_cond = [
        SHG_BAL <= 10_000,
        SHG_BAL <= 25_000,
        SHG_BAL <= 50_000,
        SHG_BAL <= 80_000,
    ]
    shg_group_tenure = np.select(shg_group_tenure_cond, [6, 12, 18, 30], default=42)

    shg_indiv_bal = np.where(BAL == 0, SAX, BAL)
    shg_indiv_tenure_cond = [
        shg_indiv_bal <= 10_000,
        shg_indiv_bal <= 25_000,
        shg_indiv_bal <= 50_000,
        shg_indiv_bal <= 80_000,
    ]
    shg_indiv_tenure = np.select(shg_indiv_tenure_cond, [6, 12, 18, 30], default=42)

    emi_cond = [
        date_cl > pd.Timestamp(0),
        open_stat == 'No',
        (
            acc_status.isin([
                'Closed Account', 'Post Write Off Settled', 'Post Write Off Closed',
                'Post Written Off Settled', 'Restructured & Closed', 'Loss',
                'Charge Off/Written Off', 'Settled',
            ]) &
            (~loan_cat.isin(['SHG Group', 'SHG Group - Govt', 'SHG individual', 'SHG Individual'])) &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited')
        ) | (loan_cat == 'Guarantor'),
        (BAL <= 0) & (~loan_cat.isin(['SHG Group', 'SHG Group - Govt', 'SHG individual', 'SHG Individual'])),
        date_rep < CUTOFF_DATE,
        (src == 'COAPP- RETAIL') & rel.isin(COAPP_EXCL),
        (loan_cat.isin(['SHG Group', 'SHG Group - Govt'])) & ((INST == 0) | (SHG_EQ_CUR_SAX)),
        loan_cat.isin(['SHG Group', 'SHG Group - Govt']),
        loan_cat.isin(['SHG individual', 'SHG Individual']),
        E['Name of the Institution'].isin(['Indian Overseas Bank', 'Indian Bank', 'ICICI Bank']) & (INST > 10000),
        (src == 'CCR- MFI') & (INST == 0),
        (src == 'CCR- MFI') & (freq == 'Bi-weekly'),
        (src == 'CCR- MFI') & (freq == 'Bimonthly'),
        (src == 'CCR- MFI') & (freq == 'Weekly'),
        (src == 'CCR- MFI') & freq.isin(['Monthly', 'Others', 'On-Demand']),
        loan_type == 'Bullet',
        src.isin(['CCR- RETAIL', 'COAPP- RETAIL']) &
            (nper_retail > 0) &
            ((INST == SAX) | (INST > pd.to_numeric(principal) * 0.2) | (INST == 0)),
    ]
    emi_val = [
        0,
        0,
        0,
        0,
        0,
        0,
        -npf.pmt(18/1200, shg_group_tenure, SHG_BAL),
        INST / 10,
        -npf.pmt(18/1200, shg_indiv_tenure, shg_indiv_bal),
        INST / 10,
        -npf.pmt(23.5 / 1200, mfi_nper, SAX),
        INST * 2,
        INST * 0.5,
        INST * 4,
        INST,
        pd.to_numeric(principal) * rate / rate_divisor,
        -npf.pmt(rate / rate_divisor, nper_retail, pd.to_numeric(principal)),
    ]
    E['EMI'] = np.select(emi_cond, emi_val, default=INST)

    inst_over_60 = {
        "Housing Loan": 120,
        "Property Loan": 120,
        "Two-wheeler Loan": 36,
        "Two-Wheeler Loan": 36,
        "Used Car Loan": 42,
        "Personal Loan": 36,
        "Auto Loan": 72,
        "Auto Loan (Personal)": 72,
    }

    age_col = pd.to_numeric(CB_mod['Age'], errors='coerce').fillna(0)

    noi_condn_mod = [
        age_col <= 40,
        age_col.between(40, 60, inclusive='neither') &
            CB_mod['INSTITUTION'].isin(['Housing Loan', 'Property Loan']),
        (age_col >= 60) &
            CB_mod['INSTITUTION'].isin(inst_over_60.keys()),
    ]
    noi_values_mod = [
        pd.Series(noi, index=CB_mod.index),
        (60 - age_col) * 12,
        CB_mod['INSTITUTION'].map(inst_over_60)
            .fillna(pd.Series(noi, index=CB_mod.index)),
    ]
    noi_mod = np.select(noi_condn_mod, noi_values_mod, default=pd.Series(noi, index=CB_mod.index))

    nper_retail_mod = pd.Series(
        pd.to_numeric(noi_mod, errors='coerce')
    ).fillna(0) * np.where(
        freq == 'Annually',    12,
        np.where(freq == 'Quarterly',    3,
        np.where(freq == 'Semiannually', 6, 1)))

    emi_val_mod = [
        0,
        0,
        0,
        0,
        0,
        0,
        -npf.pmt(18/1200, shg_group_tenure, SHG_BAL),
        INST / 10,
        -npf.pmt(18/1200, shg_indiv_tenure, shg_indiv_bal),
        INST / 10,
        -npf.pmt(23.5 / 1200, mfi_nper, SAX),
        INST * 2,
        INST * 0.5,
        INST * 4,
        INST,
        pd.to_numeric(principal) * rate / rate_divisor,
        -npf.pmt(rate / rate_divisor, nper_retail_mod,
                 pd.to_numeric(principal)),
    ]
    emi_mod = np.select(emi_cond, emi_val_mod, default=INST)

    E['EMI'] = np.minimum(E['EMI'], emi_mod)

    days_since = (pd.Timestamp(processing_date) - date_rep).dt.days
    E['A/C Closed Check'] = E['Current Balance'] - (E['EMI'] * ((days_since / 30) + AC_CLOSED_MONTHS))

    lead_emi_sum = E.groupby('LEAD_ID')['EMI'].transform('sum')
    fin_cond = [
        E['Name of the Institution'] == 'Svamaan Financial Services Private Limited',
        src.isin(['CCR- RETAIL', 'COAPP- RETAIL']) & acc_status.isin([
            '180-359 days past due', '360-539 days past due',
            '540-719 days past due', '720+ days past due',
            'Sub-standard', 'Doubtful',
        ]),
        E['A/C Closed Check'] <= 0,
    ]
    fin_val = [E['EMI'],
               0, 0]
    E['Final EMI']       = np.select(fin_cond, fin_val, default=E['EMI'])
    E['Include in FOIR'] = np.where(E['Final EMI'] > 0, 'Yes', 'No')
    inc = E['Include in FOIR']

    date_op = pd.to_datetime(E['Date Opened'], errors='coerce')

    remark_cond = [
        (date_cl > pd.Timestamp(0)) & (date_cl < date_op),
        date_cl > pd.Timestamp(0),
        (inc == 'Yes') & (loan_type == 'Bullet'),
        (inc == 'Yes') & (INST != 0),
        (inc == 'Yes') & (INST == 0),
        (inc == 'No') & (open_stat.isin(['No']) | (acc_status == 'Closed Account')),
        loan_cat == 'Guarantor',
        (src == 'CCR- MFI') & (date_op <= pd.Timestamp('2021-12-31')) &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),
        acc_status.isin([
            'Post Write Off Settled', 'Post Write Off Closed',
            'Post Written Off Settled', 'Restructured & Closed',
            'Loss', 'Charge Off/Written Off', 'Settled',
        ]),
        src == 'SHG Group',
        BAL <= 0,
        date_rep < CUTOFF_DATE,
        (src == 'COAPP- RETAIL') & rel.isin(COAPP_EXCL),
        (E['Final EMI'] == 0) & acc_status.isin([
            '180-359 days past due', '360-539 days past due',
            '540-719 days past due', '720+ days past due',
            'Sub-standard', 'Doubtful',
        ]),
        (E['Final EMI'] == 0) & (E['A/C Closed Check'] <= 0),
    ]
    remark_val = [
        'Closed acc/incorrect data',
        'Closed Account',
        'Bullet payment calculation',
        '-',
        'Calculated EMI',
        'Account not Open',
        loan_cat,
        'Old Loan',
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
        E.groupby(['LEAD_ID', 'Sanction Amount', 'Date Opened', 'Name of the Institution']).cumcount() + 1
    )

    is_gold_kisan  = E['Name of the Institution'].isin(
        ['Gold Loan', 'Priority Sector - Gold Loan', 'Kisan Credit Card']
    )
    is_credit_card = E['Name of the Institution'] == 'Credit Card'
    is_bullet_inst = E['Check Bullet'] != 7

    a9_excl = (
        (E['Joint Account Identifier'] > 1) |
        E['Name of the Institution'].isin([
            'HMPL NIDHI LIMITED', 'Sarathifc Nidhi Limited',
            'YUGTA NIDHI LIMITED', 'DHANIK NIDHI LIMITED', 'Other',
        ]) |
        (
            E['Name of the Institution'].isin(['Gold Loan', 'Priority Sector - Gold Loan']) &
            (E['Date Opened'] <= pd.Timestamp('2022-12-31'))
        ) |
        (
            (src == 'CCR- MFI') &
            (E['Date Opened'] <= pd.Timestamp('2021-12-31')) &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited')
        ) |
        E['Name of the Institution'].isin([
            'Tractor Loan', 'Commercial Vehicle Loan', 'Construction Equipment Loan',
        ])
    )
    a9_cond = [
        a9_excl                             & (inc == 'Yes'),
        is_gold_kisan  & (inc == 'Yes')     & (BAL * 0.01 < E['Final EMI']),
        is_credit_card & (inc == 'Yes')     & (BAL * 0.05 < E['Final EMI']),
        is_bullet_inst & (inc == 'Yes')     & (BAL * 0.015 < E['Final EMI']),
    ]
    a9_val = [0, BAL * 0.01, BAL * 0.05, BAL * 0.015]
    E['A9'] = np.select(a9_cond, a9_val, default=E['Final EMI'])

    sa = E['Sanction Amount']
    a10_cond = [
        (E['Name of the Institution'] == 'Consumer Loan')             & (sa != 0),
        (E['Name of the Institution'] == 'Business Loan - Unsecured') & (sa != 0),
        (E['Name of the Institution'] == 'Two-Wheeler Loan')          & (sa != 0),
        (E['Name of the Institution'] == 'Personal Loan')             & (sa != 0),
        (E['Name of the Institution'] == 'Auto Loan (Personal)')      & (sa != 0),
        (E['Name of the Institution'] == 'Business Loan - Secured')   & (sa != 0),
        (E['Name of the Institution'] == 'Housing Loan')              & (sa != 0),
    ]
    a10_val = [
        _cap_and_label(np.where(sa > 200_000, 30, np.where(sa < 80_000, 65, 40)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200_000, 40, np.where(sa < 80_000, 55, 50)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200_000, 30, np.where(sa < 80_000, 35, 30)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200_000, 25, np.where(sa < 80_000, 55, 35)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200_000, 20, np.where(sa < 80_000, 35, 30)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(np.where(sa > 200_000, 25, np.where(sa < 80_000, 35, 25)), sa, E['A9'], 'Calculated EMI'),
        _cap_and_label(10, sa, E['A9'], 'Calculated EMI'),
    ]
    E['A10']    = np.select(a10_cond, a10_val, default=E['A9'])
    E['FOIR10'] = np.where(E['A10'] != 0, 'Yes', 'No')

    rmk9_cond = [
        (E['Joint Account Identifier'] > 1)                        & (inc == 'Yes'),
        E['Name of the Institution'].isin([
            'HMPL NIDHI LIMITED', 'Sarathifc Nidhi Limited',
            'YUGTA NIDHI LIMITED', 'DHANIK NIDHI LIMITED',
        ])                                                          & (inc == 'Yes'),
        (E['Name of the Institution'] == 'Other')                  & (inc == 'Yes'),
        E['Name of the Institution'].isin([
            'Gold Loan', 'Priority Sector - Gold Loan'
        ]) & (E['Date Opened'] <= pd.Timestamp('2022-12-31'))      & (inc == 'Yes'),
        (src == 'CCR- MFI') & (E['Date Opened'] <= pd.Timestamp('2021-12-31')) &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited') & (inc == 'Yes'),
        E['Name of the Institution'].isin([
            'Tractor Loan', 'Commercial Vehicle Loan'
        ])                                                          & (inc == 'Yes'),
        (E['Name of the Institution'] == 'Construction Equipment Loan') & (inc == 'Yes'),
        is_gold_kisan  & (inc == 'Yes') & (BAL * 0.01 < E['Final EMI']),
        is_credit_card & (inc == 'Yes') & (BAL * 0.05 < E['Final EMI']),
        is_bullet_inst & (inc == 'Yes') & (BAL * 0.015 < E['Final EMI']),
        (E['Check Bullet'] != 7) & (inc == 'Yes') & (E['Current Balance'] * 0.015 < E['Final EMI']),
    ]
    rmk9_val = [
        'Joint/Duplicate Account', 'Not a registered entity', 'Unrecognized Loan',
        'Old Gold Loan', 'Old Loan', 'Guarantor', 'Not Considered',
        'Calculated EMI', 'Calculated EMI', 'Calculated EMI', 'Calculated EMI',
    ]
    E['Remark9'] = np.select(rmk9_cond, rmk9_val, default=E['Remarks'])

    rmk10_cond = [
        E['Name of the Institution'] == 'Consumer Loan',
        E['Name of the Institution'] == 'Business Loan - Unsecured',
        E['Name of the Institution'] == 'Two-Wheeler Loan',
        E['Name of the Institution'] == 'Personal Loan',
        E['Name of the Institution'] == 'Auto Loan (Personal)',
        E['Name of the Institution'] == 'Business Loan - Secured',
        (E['Name of the Institution'] == 'Housing Loan') & (sa != 0),
    ]
    rmk10_val = [
        _cap_and_label(np.where(sa > 200_000, 30, np.where(sa < 80_000, 65, 40)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200_000, 40, np.where(sa < 80_000, 55, 50)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200_000, 30, np.where(sa < 80_000, 35, 30)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200_000, 25, np.where(sa < 80_000, 55, 35)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200_000, 20, np.where(sa < 80_000, 35, 30)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(np.where(sa > 200_000, 25, np.where(sa < 80_000, 35, 25)), sa, E['A9'], 'Calculated EMI', E['Remark9']),
        _cap_and_label(10, sa, E['A9'], 'Calculated EMI', E['Remark9']),
    ]
    E['Remark10'] = np.select(rmk10_cond, rmk10_val, default=E['Remark9'])

    past_due_list = [
        '180-359 days past due', '360-539 days past due',
        '540-719 days past due', '720+ days past due',
        'Cancelled', 'Loss', 'Settled', 'Charge Off/Written Off',
        'Post Write Off Settled', 'Post Write Off Closed',
        'Post Written Off Settled', 'Restructured & Closed',
    ]
    rf_micro = [
        'Finance institution', 'Microfinance - Housing Loan',
        'Microfinance - Others', 'Micro Busines Unsecu',
    ]
    al_col = pd.Series(CB_mod['ACCOUNT_STATUS'].values,                index=E.index)
    am_col = pd.Series(CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].values,  index=E.index)

    rmkf_cond = [
        al_col.isin(past_due_list) & (E['FOIR10'] == 'Yes') &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),
        am_col.isin(['SHG Group', 'SHG Group - Govt'])   & (E['FOIR10'] == 'Yes'),
        (am_col == 'Joint Account')  & (inc == 'Yes') & E['Name of the Institution'].isin(rf_micro),
    ]
    rmkf_val = ['Past Due/ Write-Off', 'SHG not considered', 'Joint/Duplicate Account']
    E['Remark_Final'] = np.select(rmkf_cond, rmkf_val, default=E['Remark10'])

    psu_banks = [
        'IDBI Bank Limited', 'Canara Bank', 'Canara Bank SHG',
        'Indian Bank', 'Indian Overseas Bank', 'Aye Finance Pvt Ltd',
    ]
    E['EMI Div10 Applied'] = E['Name of the Institution'].isin(psu_banks) & (E['A10'] >= 10_000)
    E['STEP 1'] = np.where(
        E['EMI Div10 Applied'],
        E['A10'] / 10,
        E['A10']
    )

    adj_past_due = [
        '180-359 days past due', '360-539 days past due', '540-719 days past due',
        '720+ days past due', 'Cancelled', 'Loss', 'Settled', 'Charge Off/Written Off',
        'Post Write Off Settled', 'Post Write Off Closed',
        'Post Written Off Settled', 'Restructured & Closed', 'Auctioned & Settled',
    ]
    adj_micro = [
        'Finan inst', 'Microfinance - Housing Loan',
        'Microfinance - Others', 'Micro Busines Unsecu',
    ]
    ak_col = pd.Series(CB_mod['TERM_FREQUENCY'].values, index=E.index)

    adj_cond = [
        al_col.isin(adj_past_due) & (inc == 'Yes') &
            (E['Name of the Institution'] != 'Svamaan Financial Services Private Limited'),
        (am_col == 'Joint Account') & (inc == 'Yes') &
            E['Name of the Institution'].isin(adj_micro),
    ]
    adj_val = [0, 0]
    E['Adjusted EMI']      = np.select(adj_cond, adj_val, default=E['STEP 1'])
    E['Include in FOIR_l'] = np.where(E['Adjusted EMI'] > 0, 'Yes', 'No')

    return normalize_emi(E)


def compute_las_sheet(EMI: pd.DataFrame, CB_mod: pd.DataFrame) -> pd.DataFrame:
    Las = EMI.copy()
    Las['Final EMI']       = EMI['Adjusted EMI']
    Las['Remarks']         = EMI['Remark_Final']
    Las['Include in FOIR'] = EMI['Include in FOIR_l']
    Las['Term freq.']      = CB_mod['TERM_FREQUENCY'].values
    Las['ACCOUNT_STATUS']  = EMI['Account Status']
    Las['Loan_Category']   = CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].values
    return Las

# ------------------------------------------------------------
# --- foir_bp.py ---
# ------------------------------------------------------------



def New_branch_product(OT, config, supplement_csv: str = new_dict):
    OVERDUE_LIM_LOCAL = {
        'CTL': 5000, 'IGL 1': 3000, 'IGL 2': 3000,
        'IGL3Y': 3000, 'IGL3Y-90': 3000, 'MTL': 0, 'MTL R': 0,
    }

    # State-product fallback for unmapped Branch-Product keys
    # WHAT: Defines baseline outstanding loan exposure ceilings by state cluster and score tier.
    # WHY: Caps maximum allowable aggregate microfinance exposure per household based on regional risk appetite.
    # Repeat cycle products (IGL 3, IGL 4, IGL 5, CROSS SELL) inherit higher repeat borrower limits.
    _G1 = {
        'Good': {'IGL 1': 200000, 'IGL 2': 250000, 'IGL 3': 250000, 'IGL 4': 250000, 'IGL 5': 250000, 'CROSS SELL': 250000, 'CTL': 250000, 'MTL': 200000, 'MTL R': 250000},
        'Bad':  {'IGL 1': 175000, 'IGL 2': 200000, 'IGL 3': 200000, 'IGL 4': 200000, 'IGL 5': 200000, 'CROSS SELL': 200000, 'CTL': 250000, 'MTL': 175000, 'MTL R': 200000},
    }
    _G2 = {
        'Good': {'IGL 1': 250000, 'IGL 2': 300000, 'IGL 3': 300000, 'IGL 4': 300000, 'IGL 5': 300000, 'CROSS SELL': 300000, 'CTL': 300000, 'MTL': 250000, 'MTL R': 300000},
        'Bad':  {'IGL 1': 225000, 'IGL 2': 250000, 'IGL 3': 250000, 'IGL 4': 250000, 'IGL 5': 250000, 'CROSS SELL': 250000, 'CTL': 300000, 'MTL': 225000, 'MTL R': 250000},
    }
    _G3 = {
        'Good': {'IGL 1': 250000, 'IGL 2': 300000, 'IGL 3': 300000, 'IGL 4': 300000, 'IGL 5': 300000, 'CROSS SELL': 300000, 'CTL': 300000, 'MTL': 250000, 'MTL R': 300000,
                 'IGL3Y': 300000, 'IGL3Y-90': 300000},
        'Bad':  {'IGL 1': 225000, 'IGL 2': 250000, 'IGL 3': 250000, 'IGL 4': 250000, 'IGL 5': 250000, 'CROSS SELL': 250000, 'CTL': 300000, 'MTL': 225000, 'MTL R': 250000,
                 'IGL3Y': 250000, 'IGL3Y-90': 250000},
    }

    STATE_TO_GROUP = {
        'BIHAR': _G1, 'MAHARASHTRA': _G1, 'CHHATTISGARH': _G1, 'HARYANA': _G1,
        'JHARKHAND': _G1, 'MADHYA PRADESH': _G1, 'ODISHA': _G1, 'RAJASTHAN': _G1,
        'UTTAR PRADESH': _G1,
        'TAMILNADU_MT': _G2, 'TamilNadu_MT': _G2, 'TAMIL NADU': _G2, 'TAMILNADU MT': _G2, 'TELANGANA': _G2,
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

        good_lim = MASTER_LIMITS.get(f"Good{state_up}{product}", 200000)
        bad_lim  = MASTER_LIMITS.get(f"Bad{state_up}{product}", 175000)

        rows.append({
            'Branch ':                    branch,
            'Product':                   product,
            'Branch Product':            bp,
            'Credit Limit - Good Score': good_lim,
            'Overdue Limit':             OVERDUE_LIM_LOCAL.get(product, 0),
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


def Return_dicts(config) -> pd.DataFrame:
    fo_emi     = config['fo_emi']
    os_bad_cs  = config['os_bad_cs']
    os_good_cs = config['os_good_cs']
    return os_bad_cs, os_good_cs, fo_emi

# ------------------------------------------------------------
# --- foir_cv.py ---
# ------------------------------------------------------------



def Lender_Count(Las: pd.DataFrame, lender_mapping: dict = None) -> pd.Series:
    Las = Las.copy()
    Las['Remarks'] = Las['Remarks'].astype(str).str.strip()

    if lender_mapping is None:
        lender_mapping = load_lender_mapping()

    inst_series = Las['Name of the Institution'].astype(str).str.strip()
    if lender_mapping:
        Las['_Lender_Name'] = inst_series.map(lender_mapping).fillna(inst_series)
    else:
        Las['_Lender_Name'] = inst_series

    Lender_Count = Las[
        (Las['Source'] == 'CCR- MFI') &
        (Las['_Lender_Name'] != 'Svamaan Financial Services Private Limited') &
        (Las['Name of the Institution'] != 'Svamaan Financial Services Private Limited') &
        (
            Las['Remarks'].isin([
                '180+ Past Due', 'SHG not considered', '-', 'Calculated EMI',
                'Charge Off/Written Off', 'Past Due/ Write-Off',
                'Post Write Off Settled', 'Post Write Off Closed',
                'Settled', 'Post Written Off Settled', 'Restructured & Closed',
            ])
        )
    ].groupby('LEAD_ID')['_Lender_Name'].nunique().fillna(0)

    return Lender_Count


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

    # ── MFI Outstanding & Exposure Metrics ─────────────────────────────────────
    # 1. MFI Past Due & Overdue:
    #    Sum of Past Due amounts for CCR-MFI primary/applicant accounts (Joint Account Identifier == 1).
    CV['MFI PastDue & Overdue'] = lead_ids.map(
        EMI[
            (EMI['Source'] == 'CCR- MFI') &
            (EMI['Joint Account Identifier'] == 1) &
            (~EMI['Remark_Final'].isin(['Old Loan', 'Old Gold Loan', 'Old Reported', 'Balance is 0', 'Account closed']))
        ].groupby('LEAD_ID')['Past Due'].sum()
    ).fillna(0)

    # ── MFI Outstanding Rule: (a) Standard MFI + (b) SHG + (c) Closed 2023+ + (d) Loss ──
    shg_group_cats = ['SHG Group', 'SHG Group - Govt']
    shg_indiv_cats = ['SHG Individual', 'SHG individual']

    keep_rem = [
        'Calculated EMI', '-', '180+ Past Due', 'Charge Off/Written Off',
        'Past Due/ Write-Off', 'Post Write Off Settled',
        'Post Written Off Settled', 'Settled', 'SHG not considered',
    ]
    not_svmn = (EMI['Name of the Institution'] != 'Svamaan Financial Services Private Limited')
    cb_numeric = pd.to_numeric(EMI['Current Balance'], errors='coerce').fillna(0)

    # IDBI/IOB/Aye loans whose EMI was divided by 10 count at balance /10 (/15 above 15L)
    div10_os = EMI['EMI Div10 Applied'] & EMI['Name of the Institution'].isin(
        ['IDBI Bank Limited', 'Indian Overseas Bank', 'Aye Finance Pvt Ltd'])
    os_bal = pd.Series(
        np.where(div10_os, np.where(cb_numeric > 1_500_000, cb_numeric / 15, cb_numeric / 10), cb_numeric),
        index=EMI.index)

    # (a) Standard MFI (Full Current Balance, except the div10 bank loans above):
    # CCR-MFI, non-Svamaan, valid remarks, excluding SHG Group and excluding high-ticket SHG Individual (>= 1.5L)
    # (SHG Individual with Current Balance < 1.5L remains in standard MFI at 100% full balance)
    is_standard_mfi = (
        (EMI['Source'] == 'CCR- MFI') & not_svmn &
        EMI['Remark_Final'].isin(keep_rem) &
        (~EMI['Loan Category'].isin(shg_group_cats)) &
        ~(EMI['Loan Category'].isin(shg_indiv_cats) & (cb_numeric >= 150_000))
    )
    mfi_a = os_bal[is_standard_mfi].groupby(EMI.loc[is_standard_mfi, 'LEAD_ID']).sum()

    # (b) SHG scaled exposure:
    # 1. SHG Group: >15L -> /15, else -> /10
    is_shg_grp = not_svmn & EMI['Loan Category'].isin(shg_group_cats) & EMI['Remark_Final'].isin(keep_rem)
    shg_grp_rows = EMI[is_shg_grp].copy()
    shg_grp_bal = pd.to_numeric(shg_grp_rows['Current Balance'], errors='coerce').fillna(0)
    shg_grp_rows['_scaled_bal'] = np.where(shg_grp_bal > 1_500_000, shg_grp_bal / 15, shg_grp_bal / 10)

    # 2. SHG Individual (>= 1.5L): >15L -> /15, else -> /10
    is_shg_ind = not_svmn & EMI['Loan Category'].isin(shg_indiv_cats) & (cb_numeric >= 150_000) & EMI['Remark_Final'].isin(keep_rem)
    shg_ind_rows = EMI[is_shg_ind].copy()
    shg_ind_bal = pd.to_numeric(shg_ind_rows['Current Balance'], errors='coerce').fillna(0)
    shg_ind_rows['_scaled_bal'] = np.where(shg_ind_bal > 1_500_000, shg_ind_bal / 15, shg_ind_bal / 10)

    mfi_b = (
        CV['Lead ID'].map(shg_grp_rows.groupby('LEAD_ID')['_scaled_bal'].sum()).fillna(0) +
        CV['Lead ID'].map(shg_ind_rows.groupby('LEAD_ID')['_scaled_bal'].sum()).fillna(0)
    )

    # (c) Loss accounts
    mfi_loss = EMI[
        (EMI['Source'] == 'CCR- MFI') & not_svmn &
        (EMI['Remark_Final'] == 'Loss')
    ].groupby('LEAD_ID')['Current Balance'].sum()
#- , 180+ od , 
    # Combined MFI Outstanding: (a) + (b) + (c)
    CV['MFI Outstanding'] = (
        CV['Lead ID'].map(mfi_a).fillna(0) +
        mfi_b +
        CV['Lead ID'].map(mfi_loss).fillna(0)
    )

    # SHG Group & Individual breakdown tracking
    CV['shg 10%']           = CV['Lead ID'].map(shg_grp_rows.groupby('LEAD_ID')['_scaled_bal'].sum()).fillna(0)
    CV['shg_indiv_10%']     = CV['Lead ID'].map(shg_ind_rows.groupby('LEAD_ID')['_scaled_bal'].sum()).fillna(0)
    CV['svmn']              = 0.0     # Svamaan excluded in all parts via not_svmn
    CV['MFI OUTSTANDING 2'] = CV['Lead ID'].map(mfi_loss).fillna(0)
    CV['X']                 = CV['MFI Outstanding']
    CV['Final O/s']         = CV['X'].fillna(0)

    # ── Installments, FOIR & Income Calculations ──────────────────────────────
    # Total monthly installment across all loans
    CV['Total Installment'] = lead_ids.map(
        EMI.groupby('LEAD_ID')['EMI'].sum()).fillna(0)

    # Final EMI for applicant non-joint loans
    CV['Final EMI'] = lead_ids.map(
        EMI[EMI['Joint Account Identifier'] == 1]
        .groupby('LEAD_ID')['Final EMI'].sum()
    ).fillna(0)

    # Monthly reported household income
    CV['Monthly Income'] = lead_ids.map(
        Summary_mod.set_index('LEAD_ID')['SVAMAAN_COB_INCOME'])

    # FOIR calculation: (Final EMI + proposed product EMI) / Monthly Income
    proposed = CV['Product'].map(fo_emi).fillna(0)
    proposed = pd.to_numeric(proposed.replace({',': '', '-': '0'}, regex=True))
    CV['FOIR'] = ((CV['Final EMI'] + proposed) / CV['Monthly Income'])
    CV['FOIR'] = CV['FOIR'].map(lambda x: excel_round(x, 2)) 
    
    # New Monthly Income: If FOIR > 50%, recalculate required income for FOIR <= 49%
    CV['New Monthly Income'] = np.where(
        CV['FOIR'] > 0.5,
        ((CV['Final EMI'] + proposed) / 0.49).round(-1),
        CV['Monthly Income'])

    # ── Checks ────────────────────────────────────────────────────────────────
    CV['Key'] = CV['Branch'] + CV['Product']
    
    def _resolve_os_lim(cv: pd.DataFrame, os_good: dict, os_bad: dict) -> pd.Series:
        os_good_norm = {str(k).strip().upper(): v for k, v in os_good.items()}
        os_bad_norm = {str(k).strip().upper(): v for k, v in os_bad.items()}
        norm_key = (
            cv['Branch'].astype(str).str.strip().str.upper() +
            cv['Product'].astype(str).str.strip().str.upper()
        )
        return np.where(
            cv['Product'] == 'CTL',
            norm_key.map(os_bad_norm),
            np.where(
                (cv['Credit Score'].between(699, 901, inclusive='neither')) |
                (cv['Credit Score'] < 100),
                norm_key.map(os_good_norm),
                norm_key.map(os_bad_norm),
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
    
    lender_map = config.get('lender_mapping') if config else None
    Lend = Lender_Count(Las, lender_map)
    CV['Lenders'] = CV['Lead ID'].map(Lend).fillna(0)

    # Lender Check: >3 lenders fails. Income-based stricter check (>2 for ≤25k) runs in modis() after income recalc.
    CV['Lender Check'] = np.where(CV['Lenders'] > 3, 0, 1)

    CV['FOIR Check'] = np.where(CV['FOIR'] > 0.5, 0, 1)

    # ── Comments ──────────────────────────────────────────────────────────────
    #  COMMENT HIERARCHY (highest priority first):
    #    1. Overdue&WriteOff
    #    2. High Outstanding
    #    3. More than 3 Lenders
    #    4. Poor Credit Score  (only -Approve reaches here; rejections caught above)
    #    5. FOIR / Approve After Income Reassessment
    #    default: Approve

    # Poor Credit Score flag: Equifax score in [300, 650)
    pcs_mask = CV['Credit Score'].between(300, 650, inclusive='left')

    # Secondary checks for OW-Approve (OS & Lender must both pass)
    ow_ok = (
        (CV['O/s Check'] == 1) &
        (CV['Lender Check'] == 1)
    )

    com_condn = [
        # ── 1. Overdue branches ──
        (CV['Overdue Check'] == 0) & ow_ok,
        (CV['Overdue Check'] == 0) & (CV['Lender Check'] == 0),
        (CV['Overdue Check'] == 0) & (CV['O/s Check'] == 0),
        (CV['Overdue Check'] == 0),

        # ── 2. Lender (before Outstanding and PCS) ──
        CV['Lender Check'] == 0,

        # ── 3. Outstanding (before PCS) ──
        CV['O/s Check'] == 0,

        # ── 4. PCS — only approval case reaches here (OS/Lender/Overdue already caught above) ──
        pcs_mask,

        # ── 5. FOIR branches ──
        (CV['FOIR Check'] == 0) & (CV['New Monthly Income'] <= 25000),
        (CV['FOIR Check'] == 0)
    ]

    com_choice = [
        'Overdue&WriteOff',
        'Overdue&WriteOff',
        'Overdue&WriteOff',
        'Overdue&WriteOff',
        'More than 3 Lenders',
        'High Outstanding',
        'Poor Credit Score',
        'Approve After Income Reassessment',
        'FOIR'
    ]
    CV['Comments'] = np.select(com_condn, com_choice, default='Approve')

    # ── Rejection Reasons: all failing checks combined ──────────────────────
    _flags = [
        (CV['Overdue Check'] == 0,  'Overdue&WriteOff'),
        (CV['Lender Check'] == 0,   'More than 3 Lenders'),
        (CV['O/s Check'] == 0,      'High Outstanding'),
        (pcs_mask,                  'Poor Credit Score'),
        ((CV['FOIR Check'] == 0) & (CV['New Monthly Income'] > 25000),     'FOIR'),
    ]
    _parts = pd.DataFrame({str(i): np.where(m, lbl, '') for i, (m, lbl) in enumerate(_flags)})
    CV['Rejection Reasons'] = _parts.apply(lambda r: ' & '.join(x for x in r if x), axis=1)

    return CV


# ------------------------------------------------------------
# --- credit_val_sheet.py ---
# ------------------------------------------------------------



CREDIT_VAL_ORDER = [
    'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
    'Credit Score', 'Comments', 'Final Decision',
    'O/s Check', 'Overdue Check', 'Lender Check', 'FOIR Check',
    'MFI Outstanding', 'MFI PastDue & Overdue',
    'Total Installment', 'Final EMI',
    'Monthly Income', 'FOIR', 'New Monthly Income',
    'Final O/s', 'OS_Lim', 'Lenders',
]


def compute_credit_val_sheet(
    CV: pd.DataFrame,
    OT: pd.DataFrame = None,
) -> pd.DataFrame:
    cols = [c for c in CV_ORDER if c in CV.columns]
    sheet = CV[cols].copy()

    if OT is not None and 'Comments' in OT.columns:
        ot_comments = OT[['Lead ID', 'Comments']].copy()
        ot_comments.columns = ['Lead ID', 'OT Comments']
        sheet = sheet.merge(ot_comments, on='Lead ID', how='left')
        sheet['Final Decision'] = sheet['OT Comments'].fillna(sheet['Comments'])
        sheet.drop(columns=['OT Comments'], inplace=True)
    else:
        sheet['Final Decision'] = sheet['Comments']

    fail_checks = (
        (sheet['O/s Check'] == 0).astype(int),
        (sheet['Overdue Check'] == 0).astype(int),
        (sheet['Lender Check'] == 0).astype(int),
        (sheet['FOIR Check'] == 0).astype(int),
    )
    labels = ['O/s', 'Overdue', 'Lender', 'FOIR']
    parts = pd.DataFrame(dict(zip(labels, fail_checks)), index=sheet.index)
    sheet['Failed Checks'] = (
        parts
        .dot(parts.columns + ', ')
        .str.strip(', ')
        .replace('', 'None')
    )

    sheet.insert(0, '#', range(1, len(sheet) + 1))
    return sheet


def credit_val_summary(
    CV: pd.DataFrame,
    OT: pd.DataFrame = None,
) -> dict[str, pd.DataFrame]:
    sheet = compute_credit_val_sheet(CV, OT)

    by_comment = sheet.groupby('Comments').agg(
        Count=('Lead ID', 'count'),
    ).reset_index()

    by_decision = sheet.groupby('Final Decision').agg(
        Count=('Lead ID', 'count'),
    ).reset_index()

    fail_counts = {
        'O/s Check Fail': int((sheet['O/s Check'] == 0).sum()),
        'Overdue Check Fail': int((sheet['Overdue Check'] == 0).sum()),
        'Lender Check Fail': int((sheet['Lender Check'] == 0).sum()),
        'FOIR Check Fail': int((sheet['FOIR Check'] == 0).sum()),
        'All Checks Pass': int(((sheet['O/s Check'] == 1)
                                & (sheet['Overdue Check'] == 1)
                                & (sheet['Lender Check'] == 1)
                                & (sheet['FOIR Check'] == 1)).sum()),
        'Total Leads': len(sheet),
    }

    return {
        'By CV Comment': by_comment,
        'By Final Decision': by_decision,
        'Fail Counts': pd.DataFrame([fail_counts]),
    }


def export_validation_sheets(
    CV: pd.DataFrame,
    EMI: pd.DataFrame,
    file_path: str,
    OT: pd.DataFrame = None,
    hide_summary: bool = True,
) -> None:
    credit_val = compute_credit_val_sheet(CV, OT)
    emi_calc = compute_emi_calculation_sheet(EMI)
    summaries = {**credit_val_summary(CV, OT), **emi_summary(EMI)}

    sheets = {
        'Credit Validation': credit_val,
        'EMI Calculation': emi_calc,
        **{k: v for k, v in summaries.items()},
    }

    hide = list(summaries.keys()) if hide_summary else None
    convert_to_excel(file_path, sheets, hide_sheets=hide)

# ------------------------------------------------------------
# --- foir_ot.py ---
# ------------------------------------------------------------



def compute_ot_sheet(CV: pd.DataFrame, EMI: pd.DataFrame) -> pd.DataFrame:
    OT = CV[[
        'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
        'Credit Score', 'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue',
        'Monthly Income', 'FOIR', 'New Monthly Income', 'Rejection Reasons',
    ]].copy()

    OT['Total Installment'] = CV['Final EMI']
    OT['MFI Outstanding']   = CV['Final O/s']

    if 'Lenders' in CV.columns:
        OT['Lender Count'] = CV['Lenders']
    else:
        lender_mapping = load_lender_mapping()
        inst_series = EMI['Name of the Institution'].astype(str).str.strip()
        if lender_mapping:
            inst_series = inst_series.map(lender_mapping).fillna(inst_series)
        temp_emi = EMI.copy()
        temp_emi['_Lender_Name'] = inst_series
        mapping = (
            temp_emi[
                (
                    temp_emi['Remark_Final'].isin([
                        '180+ Past Due', 'SHG not considered', '-', 'Calculated EMI',
                        'Charge Off/Written Off', 'Past Due/ Write-Off',
                        'Post Write Off Settled', 'Post Write Off Closed',
                        'Settled', 'Post Written Off Settled', 'Restructured & Closed',
                    ])
                ) &
                (temp_emi['_Lender_Name'] != 'Svamaan Financial Services Private Limited') &
                (temp_emi['Source'] == 'CCR- MFI')
            ]
            .groupby('LEAD_ID')['_Lender_Name'].nunique()
        )
        OT['Lender Count'] = CV['Lead ID'].map(mapping).fillna(0)
    return OT


def modis(
    OT: pd.DataFrame,
    Las: pd.DataFrame,
    Stages=None,
    OD_list=None,
    a = None,
) -> pd.DataFrame:
    tracking_history = None
    if a is not None and len(a) > 0:
        tracking_history = OT[OT["Lead ID"].isin(a)][
            ["Lead ID", "Comments", "New Monthly Income"]
        ].copy()
        tracking_history["Step"] = "0. Entry"

    def capture_snapshot(step_name: str):
        nonlocal tracking_history
        if tracking_history is not None:
            current_state = OT[OT["Lead ID"].isin(a)][
                ["Lead ID", "Comments", "New Monthly Income"]
            ].copy()
            current_state["Step"] = step_name
            tracking_history = pd.concat(
                [tracking_history, current_state], ignore_index=True
            )

    if OD_list is not None:
        ot_ids = OT['Cust ID'].astype(str).str.strip()
        od_ids = OD_list['CUST ID'].astype(str).str.strip()
        mask = (
            ot_ids.isin(od_ids) &
            OT['Comments'].isin([
                'Overdue&WriteOff',
                'More than 3 Lenders', 'More than 2 Lenders',
                'High Outstanding', 'Poor Credit Score',
            ])
        )
        OT.loc[mask, 'Comments'] = 'Approve- OD'
    capture_snapshot("Step1")

    lend = Lender_Count(Las)

    Las_map = (Las.groupby('LEAD_ID')['Final EMI'].sum()).fillna(0) + 3_000
    OT['Total Installment'] = OT['Lead ID'].map(Las_map).fillna(0)

    OT['Income'] = ((OT['Total Installment']) / 0.48).round(-2)

    OT['Income'] = np.where(
        (OT['Income'] > 75_000) & (OT['Total Installment'] < 36_500),
        75_000, OT['Income']
    )
    capture_snapshot("Step2")

    # Tamil Nadu MT Regional Exception Removed:
    # WHAT: No 'Approve After IC- MT' exception is applied to TamilNadu_MT.
    # WHY: TamilNadu_MT now follows identical waterfall policy to Tamil Nadu — both states use the standard income reassessment and risk cap without a regional MT carve-out.
    # (Previously: TamilNadu_MT + IGL 1 + Income <= 75000 was auto-approved via 'Approve After IC- MT'; removed to align with Tamil Nadu.)
    mt_mask = pd.Series(False, index=OT.index)
    # OT.loc[mt_mask, 'Comments'] = 'Approve After IC- MT'  # Disabled: MT now identical to Tamil Nadu

    # ── END-OF-WATERFALL INCOME REASSESSMENT ENGINE (RULES 1, 2, 3 & OPTION A) ─
    # Executes the centralized 3-rule income standardisation engine cleanly at the end of the waterfall,
    # completely eliminating clashing legacy buffer steps and preserving declared income integrity.

    # Rule 1 (Baseline Pivot Income):
    # WHAT: Sets New Monthly Income directly to required Pivot Income (Total Installment / 0.48, rounded to ₹100).
    # WHY: Establishes applicant baseline debt-servicing income directly from mathematical debt obligations.
    OT['New Monthly Income'] = OT['Income']

    # Rule 3: Low Installment Standardisation Tier (Installment < ₹12.5k, Monthly <= ₹25k, New Monthly >= ₹25k -> ₹25,000)
    # WHAT: Standardizes New Monthly Income to ₹25,000 when:
    #       1. Total Installment is strictly less than ₹12,500.
    #       2. Stated Monthly Income is less than or equal to ₹25,000.
    #       3. Modeled New Monthly Income (Pivot Income) is greater than or equal to ₹25,000.
    # WHY: Under statutory RBI guidelines (FOIR <= 50%), an obligation < ₹12.5k on a standardized ₹25,000 income
    #      mathematically guarantees FOIR <= 50% (₹12,500 / ₹25,000 = 0.50) without inflating income into higher brackets.
    low_installment_standardise_mask = (
        # Sub-condition 1: Obligation is under the statutory ₹12,500 midpoint threshold
        (pd.to_numeric(OT['Total Installment'], errors='coerce').fillna(0) < 12_500) &
        # Sub-condition 2: Stated household income is within the baseline policy tier (<= ₹25,000)
        (pd.to_numeric(OT['Monthly Income'], errors='coerce').fillna(0) <= 25_000) &
        # Sub-condition 3: Modeled pivot income reaches or exceeds ₹25,000
        (pd.to_numeric(OT['New Monthly Income'], errors='coerce').fillna(0) >= 25_000)
    )
    OT.loc[low_installment_standardise_mask, 'New Monthly Income'] = 25_000

    # Rule 2 (Higher Declared Income Retention):
    # WHAT: Retains declared Monthly Income whenever declared income is strictly higher than New Monthly Income.
    # WHY: Credit policy never artificially penalizes or downgrades borrowers who have verified higher earnings.
    higher_declared_income_mask = (
        pd.to_numeric(OT['Monthly Income'], errors='coerce').fillna(0) >
        pd.to_numeric(OT['New Monthly Income'], errors='coerce').fillna(0)
    )
    OT.loc[higher_declared_income_mask, 'New Monthly Income'] = OT.loc[higher_declared_income_mask, 'Monthly Income']

    # Recalculate Final FOIR based on finalized New Monthly Income
    # WHAT: Recomputes debt-to-income ratio using total monthly debt obligations and finalized reassessed income.
    # WHY: Provides the authoritative FOIR metric used for final regulatory approval testing and auditing.
    OT['FOIR'] = (
        pd.to_numeric(OT['Total Installment'], errors='coerce').fillna(0) /
        pd.to_numeric(OT['New Monthly Income'], errors='coerce').replace(0, np.nan)
    ).fillna(0)

    # Decision Updates (Option A):
    # WHAT: Reclassifies ONLY initial FOIR breaches (Comments == 'FOIR') to 'Approve After Income Reassessment'
    #       if their recalculated FOIR meets the statutory ceiling (FOIR <= 50%).
    #       Clean initial approvals (Comments == 'Approve') strictly remain 'Approve'.
    # WHY: Preserves genuine clean credit approvals without false reclassification, while approving eligible
    #      recalibrated borrowers under formal policy guidelines.
    foir_resolved_mask = (
        # Sub-condition 1: Lead originally failed scorecard FOIR limit
        (OT['Comments'] == 'FOIR') &
        # Sub-condition 2: Reassessed FOIR is strictly within the statutory 50% ceiling
        (OT['FOIR'] <= 0.50)
    )
    OT.loc[foir_resolved_mask, 'Comments'] = 'Approve After Income Reassessment'

    # WHAT: Upgrades 'Approve- OD' leads whose income was upwardly adjusted to 'Approve After IC- OD'.
    # WHY: Notifies operations that pre-approved OD leads had income calibrated and require field verification.
    od_income_revised_mask = (
        # Sub-condition 1: Lead is in pre-approved OD status
        (OT['Comments'] == 'Approve- OD') &
        # Sub-condition 2: Modeled income was increased above declared income
        (OT['New Monthly Income'] > OT['Monthly Income'])
    )
    OT.loc[od_income_revised_mask, 'Comments'] = 'Approve After IC- OD'
    capture_snapshot("Step3_IncomeReassessment")

    # ── Step 13: "Approve After IC" suffix for Poor Credit Score & OD ──
    # Rule: when New Monthly Income > Monthly Income (income increased),
    # apply "Approve After IC" suffix to PCS and OD approved leads.
    inc_raised = OT['New Monthly Income'] > OT['Monthly Income']

    # PCS suffix removed — all Poor Credit Score leads keep bare label
    OT.loc[inc_raised & (OT['Comments'] == 'Approve- OD'), 'Comments'] = 'Approve After IC- OD'
    capture_snapshot("Step13")

    # ── Step 14: "> 75k Rejection" for Overdue&WriteOff & Poor Credit Score ──
    # Rule: If New Monthly Income > 75000, Overdue&WriteOff and Poor Credit Score
    # leads are outright rejected (overriding the 'Approve After IC' rule).
    high_inc = OT['New Monthly Income'] > 75_000

    # PCS suffix removed — all Poor Credit Score leads keep bare label
    OT.loc[high_inc & OT['Comments'].isin(['Approve- OD', 'Approve After IC- OD']), 'Comments'] = 'Reject- OD'
    capture_snapshot("Step14")

    # ── Step 15: Reclassify approved leads to FOIR for income verification ──
    # Approved leads with a significant gap between declared income (Monthly Income)
    # and modelled income (New Monthly Income) are sent to the FOIR sheet for review.
    _approve_mask = OT['Comments'].isin(['Approve', 'Approve After Income Reassessment'])
    _mi  = pd.to_numeric(OT['Monthly Income'],     errors='coerce').fillna(0)
    _nmi = pd.to_numeric(OT['New Monthly Income'],  errors='coerce').fillna(0)

    _foir_a = _approve_mask & (_mi <= 25_000) & (_nmi > 25_000)
    _foir_b = _approve_mask & (_mi >  25_000) & (_nmi > 75_000)

    OT.loc[_foir_a | _foir_b, 'Comments'] = 'FOIR'
    capture_snapshot("Step15_FOIR_Reclassify")

    # ── Step 16: 3 lenders + income ≤ 25k → More than 2 Lenders ──
    _lc = pd.to_numeric(OT['Lender Count'], errors='coerce').fillna(0)
    _nmi2 = pd.to_numeric(OT['New Monthly Income'], errors='coerce').fillna(0)
    _3lend_low = (_nmi2 <= 25_000) & (_lc == 3)

    _comment16 = _3lend_low & OT['Comments'].isin([
        'Approve', 'Approve After Income Reassessment',
        'Overdue&WriteOff', 'Poor Credit Score'])
    OT.loc[_comment16, 'Comments'] = 'More than 2 Lenders'

    _rr_str = OT['Rejection Reasons'].astype(str)
    _no_lender_rr = ~_rr_str.str.contains('More than', regex=False)
    _rr16 = _3lend_low & _no_lender_rr
    _existing16 = OT.loc[_rr16, 'Rejection Reasons'].astype(str)
    OT.loc[_rr16, 'Rejection Reasons'] = np.where(
        _existing16.isin(['', 'nan']),
        'More than 2 Lenders',
        _existing16 + ' & More than 2 Lenders')
    capture_snapshot("Step16_Lender_Reclassify")

    # ── Step 17: 4+ lenders → income-based lender label ──
    _lc2 = pd.to_numeric(OT['Lender Count'], errors='coerce').fillna(0)
    _nmi3 = pd.to_numeric(OT['New Monthly Income'], errors='coerce').fillna(0)

    _comment17 = (_lc2 >= 4) & OT['Comments'].isin([
        'Approve', 'Approve After Income Reassessment',
        'Overdue&WriteOff', 'Poor Credit Score', 'More than 3 Lenders'])
    OT.loc[_comment17, 'Comments'] = np.where(
        _nmi3[_comment17] <= 25_000, 'More than 2 Lenders', 'More than 3 Lenders')
    _low4 = (_lc2 >= 4) & (_nmi3 <= 25_000)
    OT.loc[_low4, 'Rejection Reasons'] = OT.loc[_low4, 'Rejection Reasons'].str.replace(
        'More than 3 Lenders', 'More than 2 Lenders', regex=False)
    capture_snapshot("Step17_Lender4_Reclassify")

    if tracking_history is not None:
        print("\n" + "=" * 60)
        print(f" DEBUG REPORT FOR LEADS: {a}")
        print("=" * 60)
        for lead_id in a:
            lead_track = tracking_history[tracking_history["Lead ID"] == lead_id]
            if not lead_track.empty:
                print(f"\n\u2192 Timeline for Lead ID: {lead_id}")
                print(
                    lead_track[["Step", "Comments", "New Monthly Income"]].to_string(
                        index=False
                    )
                )
        print("=" * 60 + "\n")

    OT['FOIR'] = (OT['Total Installment'] / OT['New Monthly Income'].replace(0, np.nan)).fillna(0)
    return OT

# ------------------------------------------------------------
# --- foir_cb.py ---
# ------------------------------------------------------------



def filter_cb(
        CB: pd.DataFrame,
        CB_Date: pd.DataFrame,
        Summary: pd.DataFrame,
        date_45: str,
        date_60: str,
        eval_all=None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    CB_Date['CCR_DATE']    = pd.to_datetime(CB_Date['CCR_DATE'])
    CB_Date['RETAIL_DATE'] = pd.to_datetime(CB_Date['RETAIL_DATE'])

    if eval_all == 'Yes':
        CB_Date_mod = CB_Date
    else:
        CB_Date_mod = CB_Date[
            (CB_Date['CCR_DATE'] >= date_45) &
            (CB_Date['RETAIL_DATE'] >= date_60)
        ]

    CB_dif = CB_Date.copy()
    CB_dif = CB_dif.drop(CB_Date_mod.index)

    CB_mod = CB[CB['LEAD_ID'].isin(CB_Date_mod['LEAD_ID'])].copy()
    closed_mask = CB_mod['DATE_CLOSED'].notna()
    CB_mod = CB_mod.fillna(0)

    CB_mod['PAST_DUE_AMOUNT']   = pd.to_numeric(CB_mod['PAST_DUE_AMOUNT'],   errors='coerce').fillna(0)
    CB_mod['WRITTENOFF_AMOUNT'] = pd.to_numeric(CB_mod['WRITTENOFF_AMOUNT'], errors='coerce').fillna(0)

    num_cols = CB_mod.select_dtypes(include=['number']).columns.difference(['LEAD_ID'])
    CB_mod.loc[closed_mask, num_cols] = 0
    CB_mod['Comments'] = np.where(closed_mask, 'closed account', '')

    CB_mod.loc[
        CB_mod['INSTITUTION'] == 'Kiara Microcredit Private Limited',
        ['PAST_DUE_AMOUNT', 'WRITTENOFF_AMOUNT']
    ] = 0
    CB_mod.loc[
        CB_mod['LOAN_CATEGORY_OWNERSHIP_TYPE'].isin(['SHG Group', 'SHG Group - Govt']),
        ['PAST_DUE_AMOUNT', 'WRITTENOFF_AMOUNT']
    ] = 0

    # TamilNadu_MT AU Bank Adjustment Removed:
    # WHAT: No past-due zeroing for AU Small Finance Bank in TamilNadu_MT.
    # WHY: TamilNadu_MT now follows identical policy to Tamil Nadu — both states treat AU Small Finance Bank past-due balances as regular delinquency without regional zeroing exception.
    # (Previously: CB_mod past-due was zeroed for TamilNadu_MT + AU Small Finance Bank; removed to align with Tamil Nadu.)

    # ── Ticket-size tenure lookup for unreliable bureau NOI (0-3 or 0-10) ──
    sax_amt  = pd.to_numeric(CB_mod['SANCTION_AMOUNT'], errors='coerce').fillna(0)
    bal_amt  = pd.to_numeric(CB_mod['CURRENT_BALANCE'], errors='coerce').fillna(0)
    prin_amt = np.where(sax_amt == 0, bal_amt, sax_amt)

    ticket_tenure_cond = [
        prin_amt <= 10_000,
        prin_amt <= 25_000,
        prin_amt <= 50_000,
        prin_amt <= 80_000,
    ]
    ticket_tenure_val = [4, 10, 20, 32]
    ticket_tenure = np.select(ticket_tenure_cond, ticket_tenure_val, default=52)

    raw_noi = pd.to_numeric(CB_mod['NO_OF_INSTALLMENTS'], errors='coerce').fillna(0)
    CB_mod['NO_OF_INSTALLMENTS'] = np.where(
        (raw_noi <= 10) & (CB_mod['CB_TYPE'] == 'CCR- MFI'),
        ticket_tenure, CB_mod['NO_OF_INSTALLMENTS']
    )

    CB_mod['INSTALLMENT_AMOUNT'] = pd.to_numeric(
        CB_mod['INSTALLMENT_AMOUNT'].astype(str), errors='coerce'
    ).fillna(0)
    CB_mod = CB_mod.reset_index(drop=True)

    CB_mod['Age'] = CB_mod['LEAD_ID'].map(Summary.set_index('LEAD_ID')['AGE'])

    print(f"CB filter: {len(CB_Date) - len(CB_Date_mod)} leads removed (CB expired), "
          f"{CB_Date_mod['LEAD_ID'].nunique()} leads retained")

    return CB_mod, CB_Date_mod


def filter_summary(
        Summary: pd.DataFrame,
        CB_Date_mod: pd.DataFrame,
        Pos: pd.DataFrame,
        inc: pd.DataFrame = None
) -> pd.DataFrame:
    Summary_mod = Summary[Summary['LEAD_ID'].isin(CB_Date_mod['LEAD_ID'])].copy()
    Summary_mod = Summary_mod.reset_index(drop=True)

    Summary_mod.loc[Summary_mod['LOAN CYCLE'] == 'CROSS SELL', 'LOAN CYCLE'] = 'CTL'
    Summary_mod.loc[
        Summary_mod['LOAN CYCLE'].isin(['IGL 3', 'IGL 4', 'IGL 5', 'IGL 6', 'IGL 7', 'IGL 8', 'IGL 9', 'IGL 10']),
        'LOAN CYCLE'
    ] = 'IGL 2'

    Summary_mod['BRANCH_NAME'] = Summary_mod['BRANCH_NAME'].str.lower()

    mtr_leads = Pos[Pos['Loan Product'].isin(FILTERED_PRODUCTS)]['CUST ID']
    Summary_mod['LOAN CYCLE'] = np.where(
        Summary_mod['ICUST_ID'].isin(mtr_leads) & (Summary_mod['LOAN CYCLE'] == 'MTL'),
        'MTL R', Summary_mod['LOAN CYCLE']
    )

    # TamilNadu_MT Branch Prefix Removed:
    # WHAT: No 'Mt_' prefix is added to BRANCH_NAME for TamilNadu_MT.
    # WHY: TamilNadu_MT now follows identical branch naming to Tamil Nadu — both states preserve raw branch names with only .capitalize() normalization.
    # (Previously: BRANCH_NAME was prefixed with 'Mt_' for TamilNadu_MT; removed to align with Tamil Nadu.)
    Summary_mod['BRANCH_NAME'] = Summary_mod['BRANCH_NAME'].str.capitalize()

    if inc is not None:
        inc = inc.drop_duplicates(subset=['CUST ID'], keep='first').copy()
        inc['Total Monthly Income'] = pd.to_numeric(inc['Total Monthly Income'], errors='coerce')
        inc_map = inc.set_index('CUST ID')['Total Monthly Income']
        mask = Summary_mod['ICUST_ID'].isin(inc['CUST ID'])
        Summary_mod['SVAMAAN_COB_INCOME'] = 25_000.0
        Summary_mod.loc[mask, 'SVAMAAN_COB_INCOME'] = (
            Summary_mod.loc[mask, 'ICUST_ID'].map(inc_map)
        )

    print(f"Summary filter: {Summary_mod['LEAD_ID'].nunique()} leads after CB date filter")
    print("Loan cycle distribution:\n" + Summary_mod['LOAN CYCLE'].value_counts().to_string())

    return Summary_mod

# ------------------------------------------------------------
# --- foir_consolidate.py ---
# ------------------------------------------------------------


def _dedupe_columns(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Drop duplicate-named columns (keep first) and warn if any were found."""
    dup_mask = df.columns.duplicated()
    if dup_mask.any():
        dup_cols = sorted(set(df.columns[dup_mask]))
        print(f"[cons_model_ot] WARNING: '{name}' had duplicate columns {dup_cols} - dropping extras, keeping first occurrence")
        df = df.loc[:, ~dup_mask]
    return df


def cons_model_ot(cmo: pd.DataFrame, OT: pd.DataFrame, ms, old_ms) -> pd.DataFrame:
    # Duplicate column names in either frame make pd.concat's column
    # alignment fail with InvalidIndexError, so strip duplicates first.
    cmo = _dedupe_columns(cmo, 'cmo')
    OT   = _dedupe_columns(OT, 'OT')

    # Reset indexes too, in case cmo/OT carry a non-unique row index
    # (a duplicated row index can independently trigger the same error).
    cmo = cmo.reset_index(drop=True)
    OT  = OT.reset_index(drop=True)

    try:
        cmo = pd.concat([cmo, OT], ignore_index=True, sort=False)
    except pd.errors.InvalidIndexError as e:
        cmo_dups = cmo.columns[cmo.columns.duplicated()].tolist()
        ot_dups  = OT.columns[OT.columns.duplicated()].tolist()
        raise pd.errors.InvalidIndexError(
            f"pd.concat failed even after de-duplication. "
            f"cmo duplicate cols: {cmo_dups}, OT duplicate cols: {ot_dups}. "
            f"Original error: {e}"
        )

    cmo = cmo.drop_duplicates(subset='Lead ID', keep='last')
    cmo['CAMS Submission Date']  = np.nan
    cmo['Fresh CB Date']         = np.nan
    cmo['Stage']                 = np.nan
    cmo[' ']                     = np.nan

    # Dedupe on LEAD ID before set_index, mirroring the cmo dedup above.
    # Without this, a repeated LEAD ID in ms/old_ms produces a non-unique
    # index and .map() raises InvalidIndexError ("Reindexing only valid
    # with uniquely valued Index objects").
    ms_dedup     = ms.drop_duplicates(subset='LEAD ID', keep='last')
    old_ms_dedup = old_ms.drop_duplicates(subset='LEAD ID', keep='last')

    ms_map     = ms_dedup.set_index('LEAD ID')[['CB DATE', 'CAMS Submission Date', 'Stage']]
    old_ms_map = old_ms_dedup.set_index('LEAD ID')[['CB DATE', 'CAMS Submission Date', 'Stage']]

    old_ms['CB DATE'] = pd.to_datetime(old_ms['CB DATE'], errors='coerce')
    cmo['CB DATE as on model run day'] = (cmo['Lead ID'].map(old_ms_map['CB DATE'])).fillna(cmo['CB DATE as on model run day'])

    cmo['Fresh CB Date']               = cmo['Lead ID'].map(ms_map['CB DATE'])
    cmo['CAMS Submission Date']        = cmo['Lead ID'].map(ms_map['CAMS Submission Date'])
    cmo['Stage']                       = cmo['Lead ID'].map(ms_map['Stage'])

    cmo[' ']                     = (cmo['CB DATE as on model run day'] == cmo['Fresh CB Date'])
    mask                         = (cmo[' '] == True) | (cmo['Fresh CB Date'].isna())
    removed                      = cmo[~mask].copy()

    cmo = cmo[mask].copy()

    cmo['Date'] = np.where(
        cmo['Date'].isna(), pd.Timestamp.now(), cmo['Date'])
    cmo['Date']                  = cmo['Date'].dt.date

    cmo = cmo[['Date', 'Lead ID', 'Product', 'Cust ID', 'State', 'Branch', 'Cust Name',
       'Credit Score', 'Comments', 'MFI Outstanding', 'MFI PastDue & Overdue',
       'Total Installment', 'Monthly Income', 'FOIR', 'New Monthly Income',
       'Lender Count', 'CB DATE as on model run day', 'Fresh CB Date', ' ',
       'CAMS Submission Date', 'Stage',]].reset_index(drop=True)
    return cmo

# ------------------------------------------------------------
# --- foir_model.py ---
# ------------------------------------------------------------



def Foir_Model(
    Bureau: dict,
    Pos: pd.DataFrame,
    run_date=None,
    mods=None,
    eval_all=None,
    OD_list=None,
    inc=None,
    a = None,
):
    today           = datetime.strptime(run_date, "%Y-%m-%d") if run_date else datetime.now()
    date_30        = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    date_60         = (today - timedelta(days=60)).strftime('%Y-%m-%d')
    processing_date = pd.Timestamp(run_date) if run_date else today.strftime('%Y-%m-%d')
    print(f"Processing date: {processing_date}")

    Summary, CB, CB_Date = Bureau[0], Bureau[1], Bureau[2]

    config = load_config()

    CB_mod, CB_Date_mod = filter_cb(CB, CB_Date, Summary, date_30, date_60, eval_all)
    print("CB filtered")

    Summary_mod = filter_summary(Summary, CB_Date_mod, Pos=Pos, inc=inc)
    print("Summary filtered")

    EMI = compute_emi_sheet(CB_mod, Summary_mod, config, processing_date)
    print(f"EMI rows     : {len(EMI):>6}, unique leads: {EMI['LEAD_ID'].nunique()}")

    Las = compute_las_sheet(EMI, CB_mod)
    print(f"LAS rows     : {len(Las):>6}, unique leads: {Las['LEAD_ID'].nunique()}")

    CV = compute_cv_sheet(EMI, Summary_mod, Las, config)
    print(f"CV  rows     : {len(CV):>6}, unique leads: {CV['Lead ID'].nunique()}")

    OT = compute_ot_sheet(CV, EMI)
    print(f"OT  rows     : {len(OT[OT_ORDER]):>6}, unique leads: {OT['Lead ID'].nunique()}")

    if mods != 'False':
        OT_m = modis(OT, Las, OD_list=OD_list, a=a)
        print('Output Modified')
        print("── Final OT Comments distribution ───────────────────────────")
        print(OT_m['Comments'].value_counts().to_string())
        label, count = "Total", len(OT)
        print(f"{label:<30} {count:>10}")
        Las.loc[Las['Remarks'] == 'SHG not considered', 'Remarks'] = '-'
        return EMI[EMI_ORDER], CV[CV_ORDER], OT_m[OT_ORDER2], Las[LAS_ORDER], processing_date

    print(OT['Comments'].value_counts())
    return EMI[EMI_ORDER], CV[CV_ORDER], OT[OT_ORDER], Las[LAS_ORDER], processing_date

# ------------------------------------------------------------
# --- autocams.py ---
# ------------------------------------------------------------



def parse_unf_dates(series: pd.Series) -> pd.Series:
    str_parsed   = pd.to_datetime(series, errors='coerce')
    needs_numeric = str_parsed.isna() & pd.to_numeric(series, errors='coerce').notna()

    if needs_numeric.any():
        numeric     = pd.to_numeric(series[needs_numeric], errors='coerce')
        nat_sentinel = np.iinfo(np.int64).min
        numeric     = numeric.replace(nat_sentinel, np.nan)
        magnitude   = numeric.abs().median()

        if magnitude > 1e15:
            parsed_num = pd.to_datetime(numeric, unit='ns',  errors='coerce')
        elif magnitude > 1e12:
            parsed_num = pd.to_datetime(numeric / 1_000, unit='ms', errors='coerce')
        elif magnitude > 1e9:
            parsed_num = pd.to_datetime(numeric, unit='ms',  errors='coerce')
        elif magnitude > 1e6:
            parsed_num = pd.to_datetime(numeric, unit='s',   errors='coerce')
        else:
            parsed_num = pd.to_datetime(numeric, unit='D', origin='1899-12-30', errors='coerce')

        str_parsed = str_parsed.copy()
        str_parsed[needs_numeric] = parsed_num

    bad    = str_parsed.isna() | (str_parsed.dt.year < 2000)
    result = str_parsed.dt.strftime('%Y-%m-%d')
    result[bad] = '0'
    return result


def format_lac_date(dt_series: pd.Series) -> pd.Series:
    bad       = dt_series.isna() | (dt_series.dt.year < 2000)
    formatted = dt_series.dt.strftime('%Y-%m-%d')
    formatted[bad] = '0'
    return formatted


def Autocams(
    unf: pd.DataFrame,
    lac: pd.DataFrame,
    cob: pd.DataFrame,
    pos: pd.DataFrame,
    drop_nas=None
) -> pd.DataFrame:
    lac = lac.replace('CCR- MFI',     'CCIR(Microfinance)')
    lac = lac.replace('CCR- RETAIL',  'CCIR(Retail)')
    lac = lac.replace('COAPP- RETAIL','Retail(CoApplicant)')
    lac = lac.copy()

    lac['Source'] = lac['Source'].str.strip()
    unf['Source'] = unf['Source'].str.strip()

    unf['DATE_OPENED']    = parse_unf_dates(unf['DATE_OPENED'])
    unf['Date_Reported']  = parse_unf_dates(unf['Date_Reported'])

    svmn = unf[unf['Source'] == 'MFI'].copy()
    unf  = unf[unf['Source'] != 'MFI'].copy()

    unf['UNIQUE_ID'] = (
        pd.to_numeric(unf['LEAD_ID'], errors='coerce')
        .fillna(0).astype(int).astype(str) + '_' + unf['Source']
    )
    lac['UNIQUE_ID'] = (
        pd.to_numeric(lac['LEAD_ID'], errors='coerce')
        .fillna(0).astype(int).astype(str) + '_' + lac['Source']
    )

    lac['Equifax ID'] = np.nan
    lac['Equifax ID'] = lac['UNIQUE_ID'].map(
        unf[['UNIQUE_ID', 'EQUIFAX_ID']].drop_duplicates('UNIQUE_ID').set_index('UNIQUE_ID')['EQUIFAX_ID']
    )

    err = lac[lac['Equifax ID'].isna()].copy()

    lac['Equifax ID']      = pd.to_numeric(lac['Equifax ID'],      errors='coerce').astype('Int64').astype(str)
    lac['LEAD_ID']         = pd.to_numeric(lac['LEAD_ID'],         errors='coerce').astype('Int64').astype(str)
    lac['Sanction Amount'] = pd.to_numeric(lac['Sanction Amount'], errors='coerce').round().astype('Int64').astype(str)
    lac['Current Balance'] = pd.to_numeric(lac['Current Balance'], errors='coerce').round().astype('Int64').astype(str)

    unf['EQUIFAX_ID']      = pd.to_numeric(unf['EQUIFAX_ID'],      errors='coerce').astype('Int64').astype(str)
    unf['LEAD_ID']         = pd.to_numeric(unf['LEAD_ID'],         errors='coerce').astype('Int64').astype(str)
    unf['Sanction_Amount'] = pd.to_numeric(unf['Sanction_Amount'], errors='coerce').round().astype('Int64').astype(str)
    unf['Current_Balance'] = pd.to_numeric(unf['Current_Balance'], errors='coerce').round().astype('Int64').astype(str)

    unf['UNIQUE_ID 2'] = (
        unf['EQUIFAX_ID'].astype(str)    + '_' +
        unf['LEAD_ID'].astype(str)       + '_' +
        unf['Source'].astype(str)        + '_' +
        unf['DATE_OPENED'].astype(str)   + '_' +
        unf['Sanction_Amount'].astype(str) + '_' +
        unf['Current_Balance'].astype(str) + '_' +
        unf['Date_Reported'].astype(str) + '_'
    )
    lac['UNIQUE_ID 2'] = (
        lac['Equifax ID'].astype(str)    + '_' +
        lac['LEAD_ID'].astype(str)       + '_' +
        lac['Source'].astype(str)        + '_' +
        format_lac_date(lac['Date Opened'])    + '_' +
        lac['Sanction Amount'].astype(str)     + '_' +
        lac['Current Balance'].astype(str)     + '_' +
        format_lac_date(lac['Date Reported'])  + '_'
    )

    sort_cols_unf = ['LEAD_ID', 'Source', 'DATE_OPENED',  'Sanction_Amount', 'Current_Balance', 'Date_Reported']
    sort_cols_lac = ['LEAD_ID', 'Source', 'Date Opened',  'Sanction Amount',  'Current Balance',  'Date Reported']
    unf = unf.sort_values(sort_cols_unf).reset_index(drop=True)
    lac = lac.sort_values(sort_cols_lac).reset_index(drop=True)

    lac = lac.map(lambda x: x.strip() if isinstance(x, str) else x)
    unf = unf.map(lambda x: x.strip() if isinstance(x, str) else x)
    lac = lac.drop_duplicates(subset='UNIQUE_ID 2').copy()

    unf['Adjusted_EMI']    = unf['UNIQUE_ID 2'].map(lac.set_index('UNIQUE_ID 2')['Final EMI'])
    unf['Include_in_FOIR'] = unf['UNIQUE_ID 2'].map(lac.set_index('UNIQUE_ID 2')['Include in FOIR'])
    unf['Remarks']         = unf['UNIQUE_ID 2'].map(lac.set_index('UNIQUE_ID 2')['Remarks'])

    unf2 = unf.copy()
    mask = (pd.to_numeric(unf2['Current_Balance']) <= 0) & (unf2['Adjusted_EMI'].isna())
    unf.loc[mask, 'Adjusted_EMI']    = 0
    unf.loc[mask, 'Include_in_FOIR'] = 'No'
    unf.loc[mask, 'Remarks']         = 'Balance is 0'

    cols2     = ['Adjusted_EMI', 'Remarks', 'Include_in_FOIR']
    leads_rem = unf[unf[cols2].isna().any(axis=1)].copy()

    unf['Include_in_FOIR'] = np.where(
        unf['Include_in_FOIR'] == 'Yes', 1,
        np.where(unf['Include_in_FOIR'] == 'No', 2, unf['Include_in_FOIR'])
    )
    unf2 = unf.copy()

    fin = pd.concat([unf, svmn])
    fin['LEAD_ID'] = pd.to_numeric(fin['LEAD_ID'], errors='coerce')

    if drop_nas != False:
        fin = fin[~fin['LEAD_ID'].isin(pd.to_numeric(leads_rem['LEAD_ID']))]

    fin = fin.merge(cob, how='left', left_on='LEAD_ID', right_on='LEAD ID')
    fin = fin[~fin['Stage'].isna()]

    fin['LOAN CYCLE'] = fin['LEAD_ID'].map(cob.set_index('LEAD ID')['LOAN CYCLE'])
    fin.loc[(fin['LOAN CYCLE'] == 'IGL1')                                     & (fin['Source'] == 'MFI'), 'Adjusted_EMI'] = 3000
    fin.loc[(fin['LOAN CYCLE'].isin(['IGL2', 'IGL3', 'IGL4', 'IGL5']))       & (fin['Source'] == 'MFI'), 'Adjusted_EMI'] = 4000
    fin.loc[(fin['LOAN CYCLE'] == 'MTL')                                      & (fin['Source'] == 'MFI'), 'Adjusted_EMI'] = 1600
    fin.loc[(fin['LOAN CYCLE'] == 'MTL R')                                    & (fin['Source'] == 'MFI'), 'Adjusted_EMI'] = 1600
    fin.loc[(fin['LOAN CYCLE'] == 'CTL')                                      & (fin['Source'] == 'MFI'), 'Adjusted_EMI'] = 1200

    pos_mask = (
        pos[pos['Loan Product'].str.contains('IGL')]
        .drop_duplicates(subset='CUST ID', keep='first')
    )
    fin['Loan Product'] = fin['ICUST_ID'].map(pos_mask.set_index('CUST ID')['Loan Product'])

    mask = (
        (~fin['Loan Product'].isna()) &
        (fin['Source'] == 'MFI') &
        fin['LOAN CYCLE'].isin(['IGL2', 'IGL3', 'IGL4', 'IGL5', 'IGL6', 'IGL7'])
    )
    fin.loc[mask, 'Adjusted_EMI'] = 850

    print(f"── AutoCAMS output: {len(fin)} rows, {fin['LEAD_ID'].nunique()} unique leads")
    print(f"   Unmatched (leads_rem): {leads_rem['LEAD_ID'].nunique()} leads")

    return fin, leads_rem, pos_mask

# ------------------------------------------------------------
# --- back_end.py ---
# ------------------------------------------------------------



def Back_End_Apps(demog, OT, cams, cdl):
    blanks = demog[demog['ACCOUNT STATUS'] == " "].copy()
    demog  = (
        demog[demog['ACCOUNT STATUS'] != " "]
        .sort_values('ACCOUNT STATUS')
        .drop_duplicates(keep='first', subset='CUSTOMER ID')
        .copy()
    )
    demog = demog[['CUSTOMER ID', 'CUSTOMER VOTER ID', 'CUSTOMER AADHAR NO', 'IFSC_CODE', 'AC_NO']].copy()
    demog = demog.rename(columns={
        'CUSTOMER VOTER ID': 'Voter ID',
        'CUSTOMER AADHAR NO': 'Aadhaar No',
        'IFSC_CODE': 'IFSC',
        'AC_NO': 'Account No',
    })

    blanks = blanks.merge(demog, how='left', on='CUSTOMER ID')
    blanks['Voter Check']   = blanks['CUSTOMER VOTER ID'] == blanks['Voter ID']
    blanks['Aadhaar Check'] = blanks['CUSTOMER AADHAR NO'] == blanks['Aadhaar No']
    blanks['IFSC Check']    = blanks['IFSC_CODE'] == blanks['IFSC']
    blanks['Account Check'] = blanks['Account No'] == blanks['AC_NO']

    blanks['Credit Score']    = blanks['LEAD ID'].map(OT.set_index('Lead ID')['Credit Score'])
    blanks['MFI Outstanding'] = blanks['LEAD ID'].map(OT.set_index('Lead ID')['MFI Outstanding'])
    blanks['Lender Count']    = blanks['LEAD ID'].map(OT.set_index('Lead ID')['Lender Count'])
    blanks['Comments']        = blanks['LEAD ID'].map(OT.set_index('Lead ID')['Comments'])

    apps = blanks[
        blanks['Comments'].isin([
            'Approve After Income Reassessment', 'Approve',
            'Approve After IC', 'Approve After IC- MT', 'Approve After IC- OD',
            'Approve AFTER IC - OD', 'Approve -OD', 'FOIR',
            'Approve AFTER IC - MT', 'Approve AFTER IC - OD ',
        ])
    ].copy()

    apps['CAMS Submission Date'] = apps['LEAD ID'].map(cams.set_index('LEAD ID')['CAMS Submission Date'])
    apps['COB Income']           = apps['LEAD ID'].map(cams.set_index('LEAD ID')['Household Total Monthly Income'])
    apps['COB Installment']      = apps['LEAD ID'].map(cams.set_index('LEAD ID')['Revised Monthly Installment'])

    cdl['CUST ID'] = pd.to_numeric(cdl['CUST ID'])
    cdl = cdl.drop_duplicates(subset='CUST ID', keep='first')
    apps['Old Income'] = apps['CUSTOMER ID'].map(cdl.set_index('CUST ID')['Total Monthly Income'])
    apps['DD']         = apps['CUSTOMER ID'].map(cdl.set_index('CUST ID')['Disbursement Date'])

    apps_ret = apps.copy()

    today = pd.Timestamp.now().date()
    apps["CAMS Submission Date"] = pd.to_datetime(
        apps["CAMS Submission Date"], errors="coerce", dayfirst=True
    )
    CAMS_NOT_FILLED = apps[apps["CAMS Submission Date"].dt.date != today].copy()
    CAMS_NOT_FILLED['BA Comment'] = 'CAMS Not Filled'
    apps2           = apps[apps["CAMS Submission Date"].dt.date == today].copy()

    apps2['FOIR'] = (pd.to_numeric(apps2['COB Installment'], errors='coerce') / pd.to_numeric(apps2['COB Income'], errors='coerce').replace(0, np.nan)).fillna(0)

    cols_check = ['Voter Check', 'Aadhaar Check', 'Account Check', 'IFSC Check']
    mask = apps2[cols_check].all(axis=1)

    ALL_TRUE = apps2[mask].copy().reset_index(drop=True)
    FALSE    = apps2[~mask].copy().reset_index(drop=True)
    FALSE['BA Comment'] = 'KYC/ Bank Issue'
    at_return = ALL_TRUE.copy()

    foir_meets = ALL_TRUE['FOIR'] <= 0.5
    mask = ALL_TRUE['FOIR'] > 0.5
    ALL_TRUE['COB Installment'] = pd.to_numeric(ALL_TRUE['COB Installment'], errors='coerce')
    ALL_TRUE['New Income'] = np.nan

    ALL_TRUE.loc[mask, 'New Income'] = (ALL_TRUE.loc[mask, 'COB Installment'].values / 0.47).round(-2)

    ALL_TRUE.loc[
        (ALL_TRUE['New Income'] > 25_000) & (ALL_TRUE['COB Installment'] <= 12_500),
        'New Income'
    ] = 25_000

    ALL_TRUE.loc[
        (ALL_TRUE['New Income'] > 75_000) & (ALL_TRUE['COB Installment'] <= 36_500),
        'New Income'
    ] = 75_000

    for col in ['New Income', 'Old Income', 'COB Income']:
        ALL_TRUE[col] = pd.to_numeric(ALL_TRUE[col], errors='coerce')
    has_old = ALL_TRUE['Old Income'].notna()
    ALL_TRUE.loc[has_old, 'New Income'] = (
        ALL_TRUE.loc[has_old, ['New Income', 'Old Income', 'COB Income']].max(axis=1)
    )

    old_nqa    = ALL_TRUE['Old Income'].between(25_000, 75_000, inclusive='right')
    old_qa     = (ALL_TRUE['Old Income'] <= 25_000) | (ALL_TRUE['Old Income'].isna())
    new_qa     = (
        (ALL_TRUE['New Income'] <= 25_000) |
        ((ALL_TRUE['New Income'].isna()) & (ALL_TRUE['COB Income'] <= 25_000))
    )
    new_nqa    = (
        ALL_TRUE['New Income'].between(25_000, 75_000, inclusive='right') |
        ((ALL_TRUE['New Income'].isna()) & ALL_TRUE['COB Income'].between(25_000, 75_000, inclusive='right'))
    )
    inc_change = ALL_TRUE['New Income'] != ALL_TRUE['COB Income']

    today    = datetime.now()
    date_1yr = today - timedelta(days=365)
    ALL_TRUE['DD'] = pd.to_datetime(ALL_TRUE['DD'])

    bac_condn2 = (
        old_qa & new_nqa & ALL_TRUE['Loan Type'].isin(['Mid Loan']),
        old_qa & new_nqa & (ALL_TRUE['DD'] > date_1yr),
        (ALL_TRUE['New Income'] > 75_000) | (ALL_TRUE['Old Income'] > 75_000),
        old_qa & new_nqa & inc_change,
        old_qa & new_nqa,
        old_nqa & new_qa,
        old_qa  & new_qa & inc_change,
        old_qa  & new_qa,
        old_nqa & new_nqa & inc_change,
        old_nqa & new_nqa,
    )
    bac_value2 = (
        'On hold (MTL NQA)', 'On hold (Recent QA)', 'On Hold (High Income)',
        'NQA- IC', 'Approve',
        'QA- IC',
        'QA- IC', 'Approve',
        'NQA- IC', 'Approve',
    )
    ALL_TRUE['BA Comment'] = np.select(bac_condn2, bac_value2, default='Approve')

    mask = (
        (ALL_TRUE['New Income'] > 75_000) &
        (ALL_TRUE['COB Installment'] <= 365_000) &
        (
            (ALL_TRUE['BA Comment'] == 'On hold (MTL NQA)') |
            (
                (ALL_TRUE['BA Comment'] == 'On Hold (High Income)') &
                (ALL_TRUE['Loan Type'] == 'MTL') &
                (ALL_TRUE['Old Income'] < 25_000)
            )
        )
    )
    ALL_TRUE.loc[mask, 'New Income']    = 75_000
    ALL_TRUE.loc[mask, 'BA Comment']    = 'NQA- IC'

    print("── BA Comment distribution (ALL_TRUE) ───────────────────────")
    print(ALL_TRUE['BA Comment'].value_counts().to_string())
    total_all = len(ALL_TRUE)
    total_false = len(FALSE)
    total_cams_not_filled = len(CAMS_NOT_FILLED)
    print(f"COB Income NaN: {ALL_TRUE['COB Income'].isna().sum()} / {len(ALL_TRUE)}")
    print(f"New Income NaN:  {ALL_TRUE['New Income'].isna().sum()} / {len(ALL_TRUE)}")
    print(f"new_qa True:     {new_qa.sum()}")
    print(f"new_nqa True:    {new_nqa.sum()}")
    print(f"{'ALL_TRUE (all KYC pass)':<40} {total_all:>6}")
    print(f"{'FALSE (KYC fail)':<40} {total_false:>6}")
    print(f"{'CAMS_NOT_FILLED':<40} {total_cams_not_filled:>6}")
    

    ALL_TRUE        = ALL_TRUE.loc[:, ~ALL_TRUE.columns.duplicated()]
    FALSE           = FALSE.loc[:, ~FALSE.columns.duplicated()]
    CAMS_NOT_FILLED = CAMS_NOT_FILLED.loc[:, ~CAMS_NOT_FILLED.columns.duplicated()]
    blank = pd.concat([ALL_TRUE, FALSE, CAMS_NOT_FILLED], ignore_index=True)

    return ALL_TRUE, FALSE, CAMS_NOT_FILLED, blank

# ------------------------------------------------------------
# --- scrub.py ---
# ------------------------------------------------------------



def Scrub(
    ms: pd.DataFrame,
    OD: pd.DataFrame,
    cons_disb: pd.DataFrame,
    cons_modelo: pd.DataFrame,
    cons_add_app: pd.DataFrame = None,
) -> pd.DataFrame:
    ms = ms[ms['Stage'] == 'CUSTOMER ON BOARDING CREATION'].copy()

    try:
        ms['Co Applicant CB Date'] = pd.to_datetime(
            ms['Co Applicant CB Date'], unit='D', origin='1899-12-30'
        )
    except ValueError:
        ms['Co Applicant CB Date'] = pd.to_datetime(
            ms['Co Applicant CB Date'], errors='coerce'
        )

    ms['CB DATE'] = pd.to_datetime(ms['CB DATE'])

    today    = datetime.now()
    date_45  = (today - timedelta(days=45)).strftime("%Y-%m-%d")
    date_60  = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    date_1yr = (today - timedelta(days=365)).strftime("%Y-%m-%d")

    ms_codn = [
        ms['CB DATE'] < date_45,
        (ms['Co Applicant CB Date'] < date_60)
            | (ms['Co Applicant CB Date'].dt.year > 2030)
            | (ms['Co Applicant CB Date'].isna()),
        (ms['MFI Credit Score'].isna()) | (ms['MFI Credit Score'] == 'NA'),
        (ms['CB REMARKS'] != 'Consumer record not found')
            & (ms['CB REMARKS'].notna()),
        (ms['CAMS Submission Date'] == 'NA')
            | (ms['CAMS Submission Date'].isna()),
    ]
    ms_val = [
        'App CB expired',
        'Co-app CB expired',
        'CB Repull',
        'CB Repull',
        'CAMS not filled',
    ]
    ms['Comments'] = np.select(ms_codn, ms_val, default='')
    ms.loc[
        ms['Comments'].isin(['App CB expired', 'Co-app CB expired', 'CB Repull']),
        'Action'
    ] = 'CB Issues'

    cmo = cons_modelo.drop_duplicates(subset='Lead ID')
    ms['Model Comments'] = ms['LEAD ID'].map(cmo.set_index('Lead ID')['Comments'])
    
    # Normalize legacy rejection suffixes from old cmo_old files
    ms['Model Comments'] = ms['Model Comments'].replace({
        'Poor Credit Score - Rejection': 'Poor Credit Score',
        'Overdue&WriteOff - Rejection': 'Overdue&WriteOff',
        'Rejection- OD': 'Reject- OD',
    })
    
    ms['CB_Date as on MR'] = (pd.to_datetime(ms['LEAD ID'].map(cmo.set_index('Lead ID')['CB DATE as on model run day']),
            format='%m/%d/%Y', errors='coerce'))

    # ── Normalise old-style Model Comments (no Approve / Reject suffix) ───────
    # Historical cons_modelo entries may carry bare labels like
    # 'Poor Credit Score' or 'Overdue&WriteOff' from model runs before the
    # Approve/Reject distinction existed.  Re-evaluate them here using the
    # Lender Count and MFI past-due data that cons_modelo already contains:
    #
    #   Poor Credit Score
    #     → '- Approve'  if lender_count <= 3  AND  past-due <= product overdue limit
    #     → '- Reject'   otherwise
    #
    #   Overdue&WriteOff
    #     → '- Reject'   always at this stage
    #       (leads on the Svamaan OD list are rescued later in Action assignment)
    # ─────────────────────────────────────────────────────────────────────────
    _cmo_idx = cmo.set_index('Lead ID')
    _lc   = _cmo_idx['Lender Count']          if 'Lender Count'          in cmo.columns else pd.Series(dtype=float)
    _pd_  = _cmo_idx['MFI PastDue & Overdue'] if 'MFI PastDue & Overdue' in cmo.columns else pd.Series(dtype=float)
    _pr   = _cmo_idx['Product']               if 'Product'               in cmo.columns else pd.Series(dtype=str)
    _nmi  = _cmo_idx['New Monthly Income']    if 'New Monthly Income'    in cmo.columns else pd.Series(dtype=float)

    ms['_lc']     = pd.to_numeric(ms['LEAD ID'].map(_lc),  errors='coerce').fillna(0)
    ms['_pd']     = pd.to_numeric(ms['LEAD ID'].map(_pd_), errors='coerce').fillna(0)
    ms['_od_lim'] = pd.to_numeric(
        ms['LEAD ID'].map(_pr).map(OVERDUE_LIM), errors='coerce'
    ).fillna(0)
    ms['_nmi']    = pd.to_numeric(ms['LEAD ID'].map(_nmi), errors='coerce').fillna(0)

    # PCS suffix removed — all Poor Credit Score leads keep bare label.
    # Historical suffixed variants are normalised to bare 'Poor Credit Score'.
    pcs_suffixed = ms['Model Comments'].astype(str).str.startswith('Poor Credit Score -')
    ms.loc[pcs_suffixed, 'Model Comments'] = 'Poor Credit Score'

    # OW suffix removed — all Overdue&WriteOff leads keep bare label.
    # Historical suffixed variants are normalised to bare 'Overdue&WriteOff'.
    ow_suffixed = ms['Model Comments'].astype(str).str.startswith('Overdue&WriteOff -')
    ms.loc[ow_suffixed, 'Model Comments'] = 'Overdue&WriteOff'

    ms.drop(columns=['_lc', '_pd', '_od_lim', '_nmi'], inplace=True)
    # ─────────────────────────────────────────────────────────────────────────

    model_run_mask = (ms['Action'].isna()) & (
        (ms['Comments'] == 'CAMS not filled')
        | (ms['Model Comments'].isna())
        | (ms['CB_Date as on MR'] != ms['CB DATE'])
    )
    ms.loc[model_run_mask, 'Action'] = 'Model Run'

    MODEL_SCRUB = ms[ms['Action'] == 'Model Run'].copy()
    ms = ms[ms['Action'] != 'Model Run'].copy()

    ms_order = [
        'LEAD ID', 'Customer ID', 'Loan Account Number', 'Inquiry Purpose',
        'Center', 'Customer Name', 'Relationship Type', 'Co Borrowers Name',
        'Co Applicant CB Date', 'Submission Date and Time', 'Members s Address',
        'State', 'Pin Code', 'Co Applicant Total Outstanding Balance', 'Voter ID',
        'Applicant Total Monthly Installment', 'Co-Applicant Total Monthly Installment',
        'Aadhar Number', 'PAN', 'Household Total Monthly Income', 'FOIR  %', 'DOB',
        'GENDER', 'Branch Name', 'CAMS Submission Date', 'Created Date',
        'CB STATUS', 'CB DATE', 'NO OF ACTIVE ACCOUNTS', 'TOT PAST DUE',
        'NO PAST DUE ACCNT', 'TOT BAL AMT', 'TOT MON PAY AMT', 'TOT WRT OFF AMT',
        'CB REMARKS', 'LOAN CYCLE', 'Product', 'LOANPROPOSEDAMT', 'Stage',
        'FOIR Override Value', 'Override Remark', 'Revised Monthly Installment',
        'MFI Total Outstanding', 'MFI total past overdue', 'MFI Credit Score',
        'Family Monthly Income', 'Model Comments', 'CB_Date as on MR'
    ]

    # Disqualifying Model Comments that result in outright rejection.
    # Includes both modern granular comments and legacy/historical variants
    # for backward compatibility when consolidating historical daily files.
    REJECTION_FLAGS = {
        # Overdue & Write-Off rejections
        'Overdue&WriteOff',

        # Poor Credit Score rejections (legacy bare label + trailing space variant + modern granular)
        'Poor Credit Score',
        'Poor Credit Score ',                       # Catches dirty/trailing whitespace in older Excel sheets

        # General scorecard rule failures
        'More than 3 Lenders',
        'More than 2 Lenders',
        'High Outstanding',
        'Reject- OD',
    }
    # TamilNadu_MT IGL1 Rejection Exclusion Removed:
    # WHAT: TamilNadu_MT IGL1 applicants are no longer excluded from scorecard rejection logic.
    # WHY: TamilNadu_MT now follows identical rejection policy to Tamil Nadu — both states apply REJECTION_FLAGS uniformly without a regional IGL1 carve-out.
    # (Previously: (State == TamilNadu_MT & LOAN CYCLE == IGL1) bypassed Rejections; removed to align with Tamil Nadu.)
    rej_mask = (
        ms['Action'].isna()
        & ms['Model Comments'].isin(REJECTION_FLAGS)
    )
    ms.loc[rej_mask, 'Action'] = 'Rejections'

    cdl = cons_disb.drop_duplicates(subset='CUST ID').set_index('CUST ID')
    ms['Old Income'] = ms['Customer ID'].map(cdl['Total Monthly Income'])
    ms['DD'] = pd.to_datetime(
        ms['Customer ID'].map(cdl['Disbursement Date']),
        format='%m/%d/%Y', errors='coerce'
    )

    ms['FOIR'] = (pd.to_numeric(ms['Revised Monthly Installment'], errors='coerce') / pd.to_numeric(ms['Household Total Monthly Income'], errors='coerce').replace(0, np.nan)).fillna(0)

    OD['CUST ID'] = OD['CUST ID'].astype('Int64')
    od_ids = set(OD['CUST ID'].dropna().unique())
    ms['is_OD'] = ms['Customer ID'].isin(od_ids)

    caa_ids = set(cons_add_app['LEAD ID'])
    ms['is_AA'] = ms['LEAD ID'].isin(caa_ids)

    ic_needed = (ms['Action'].isna()) & (
        (ms['FOIR'] > 0.5)
        | (ms['Old Income'].notna() & (ms['Old Income'] > ms['Household Total Monthly Income']))
    )

    def _compute_new_income(installment: pd.Series) -> pd.Series:
        ni = installment / 0.47
        ni = ni.where(~((ni > 25_000) & (installment < 12_500)), 25_000)
        ni = ni.where(~((ni > 75_000) & (installment < 36_500)), 75_000)
        return ni.round(-2)

    ms['Revised Monthly Installment'] = pd.to_numeric(
        ms['Revised Monthly Installment'].astype(str).str.replace(',', '', regex=False),
        errors='coerce'
    ).fillna(0)

    ms['Household Total Monthly Income'] = pd.to_numeric(
        ms['Household Total Monthly Income'].astype(str).str.replace(',', '', regex=False),
        errors='coerce'
    ).fillna(0)

    ms.loc[ic_needed, 'New Income'] = _compute_new_income(
        ms.loc[ic_needed, 'Revised Monthly Installment']
    )

    income_drop_ic = ic_needed & ms['Old Income'].notna() & (
            ms['Old Income'] > ms['Household Total Monthly Income']
        )
    ms.loc[income_drop_ic, 'New Income'] = (
        ms.loc[income_drop_ic, ['New Income', 'Old Income']]
        .max(axis=1).astype(float))

    ms.loc[ms['is_OD'] & ms['New Income'].isna(), 'New Income'] = (
        ms.loc[ms['is_OD'] & ms['New Income'].isna(), 'Household Total Monthly Income']
    )

    low_income_mask = ms['New Income'].isna() & (ms['Household Total Monthly Income'] < 13_000)
    ms.loc[low_income_mask, 'New Income'] = 13_000

    nqa_range   = ms['New Income'].between(25_000, 75_000, inclusive='right')
    hold_mtl    = (
        ms['Action'].isna() & nqa_range
        & (ms['LOAN CYCLE'] == 'MTL')
        & ((ms['Old Income'] <= 25_000) | (ms['Old Income'].isna())))
    ms.loc[hold_mtl,    'Action'] = 'On hold (MTL NQA)'

    hold_recent = (
        ms['Action'].isna() & nqa_range
        & (ms['Old Income'] <= 25_000)
        & (ms['DD'] > date_1yr))
    ms.loc[hold_recent, 'Action'] = 'On hold (Recent QA)'

    ms.loc[ms['Action'].isna(), '_base'] = np.where(
        ms.loc[ms['Action'].isna(), 'is_AA'], 'AA', 'FA'
    )

    direct_mask = ms['_base'].notna() & ~ic_needed & (ms['FOIR'] <= 0.5)
    ms.loc[direct_mask & ~ms['is_OD'] &  ms['is_AA'], 'Action'] = 'AA'
    ms.loc[direct_mask & ~ms['is_OD'] & ~ms['is_AA'], 'Action'] = 'FA'
    ms.loc[direct_mask &  ms['is_OD'] &  ms['is_AA'], 'Action'] = 'AA-OD'
    ms.loc[direct_mask &  ms['is_OD'] & ~ms['is_AA'], 'Action'] = 'FA-OD'

    has_ic   = ic_needed & ms['_base'].notna()

    qa_mask  = ms['New Income'] <= 25_000
    nqa_mask = ms['New Income'].between(25_000, 75_000, inclusive='right')
    man_mask = ms['New Income'] > 75_000

    def _build_tag(base: str, income_prefix: str, is_ic: bool, is_od: bool) -> str:
        parts = [income_prefix, 'IC'] if is_ic else [income_prefix]
        parts.append(base)
        if is_od:
            parts.append('OD')
        return ' '.join(parts)

    action_condn = [
        ms['_base'].notna() & has_ic & qa_mask  & ~ms['is_OD'],
        ms['_base'].notna() & has_ic & nqa_mask & ~ms['is_OD'],
        ms['_base'].notna() & has_ic & man_mask & ~ms['is_OD'],
        ms['_base'].notna() & has_ic & qa_mask  &  ms['is_OD'],
        ms['_base'].notna() & has_ic & nqa_mask &  ms['is_OD'],
        ms['_base'].notna() & has_ic & man_mask &  ms['is_OD'],
    ]
    action_val = [
        ms['_base'].map({'AA': 'QA IC-AA',  'FA': 'QA IC-FA'}),
        ms['_base'].map({'AA': 'NQA IC-AA', 'FA': 'NQA IC-FA'}),
        ms['_base'].map({'AA': 'Manual review', 'FA': 'Manual Slashing'}),
        ms['_base'].map({'AA': 'QA IC-OD',  'FA': 'QA IC-OD'}),
        ms['_base'].map({'AA': 'NQA IC-OD', 'FA': 'NQA IC-OD'}),
        ms['_base'].map({'AA': 'Manual review', 'FA': 'Manual Slashing'}),
    ]
    ms['Action'] = np.select(action_condn, action_val, default=ms['Action'])

    ms.drop(columns=['_base', 'is_OD', 'is_AA'], inplace=True)

    ms['New Income'] = ms['New Income'].round(-2)

    mask = (
        (ms['New Income'].isna()) &
        (ms['Household Total Monthly Income'] < 13_000) &
        ((ms['Old Income'].isna()) | (ms['Old Income'] <= 13_000)) &
        (ms['Action'].isin(['AA', 'FA'])))
    ms.loc[mask, 'New Income'] = 13_000
    ms.loc[mask & (ms['Action'] == 'FA'), 'Action'] = 'QA IC-FA'
    ms.loc[mask & (ms['Action'] == 'AA'), 'Action'] = 'QA IC-AA'

    NON_MR   = ms.copy()
    complete = pd.concat([NON_MR, MODEL_SCRUB,], join='outer')

    # Drop rows with a blank Action — they duplicate the Rejections rows.
    complete = complete[
        complete['Action'].notna() & (complete['Action'].astype(str).str.strip() != '')
    ].copy()

    rej_order       = ['LEAD ID', 'LOAN CYCLE', 'Customer ID', 'State', 'Branch Name',
                       'Customer Name', 'Model Comments']

    COB_REJECTIONS  = ms[ms['Action'] == 'Rejections'][rej_order].copy()

    IGLR_MTL_CTL    = MODEL_SCRUB[MODEL_SCRUB['LOAN CYCLE'] != 'IGL1'].copy()
    MODEL_SCRUB     = MODEL_SCRUB[ms_order].copy()

    ada_order = [
        'LEAD ID', 'Customer ID', 'Customer Name', 'State',
        'Household Total Monthly Income', 'Branch Name', 'CAMS Submission Date',
        'CB DATE', 'LOAN CYCLE', 'Revised Monthly Installment', 'MFI Credit Score', 'New Income',
    ]
    ADDITIONAL_APPROVALS = ms[ms['Action'].isin(['QA IC-FA', 'NQA IC-FA', 'FA', 'FA-OD','AA','QA IC-AA',                        'AA-OD','NQA IC-FA'])][ada_order].copy()

    print("── Scrub Action distribution ────────────────────────────────")
    print(complete['Action'].value_counts().to_string())
    label, count = "Total leads processed", len(complete)
    print(f"{label:<40} {count:>6}")

    return MODEL_SCRUB, COB_REJECTIONS, ADDITIONAL_APPROVALS, IGLR_MTL_CTL, complete

# ------------------------------------------------------------
# --- income_change.py ---
# ------------------------------------------------------------


def income_change(
    inc: pd.DataFrame,
    OT: pd.DataFrame,
) -> pd.DataFrame:
    """
    Distribute the new modelled income across applicant and co-applicant
    income heads for the CAMS income-change upload.

    The model outputs a 'New Monthly Income' per lead.  This function:
      1. Maps that value onto the income template via LEAD_ID.
         Falls back to the pre-filled FAMILY_MONTHLY_INCOME column when a
         lead is not present in OT (standalone / IC-only usage).
      2. Splits total income into applicant (40–45 %, random) and
         co-applicant (remainder).
      3. Splits app income into DailyEarningsCust (65–85 %, random) and
         AgricultureCust (remainder).
      4. Splits co-app income into AgricultureCoApp (65–85 %, random) and
         OtherAlliedActivitiesCoApp (remainder).
      5. Recomputes TotalHouseHoldIncomeCust, TotalHouseHoldIncomeCoApp,
         and FAMILY_MONTHLY_INCOME.

    Parameters
    ----------
    inc : pd.DataFrame
        Income template — one row per lead.  Must contain LEAD_ID and the
        income-head columns (RentalIncomeCust, PensionCust, …).
        FAMILY_MONTHLY_INCOME should already be populated for leads not
        present in OT.
    OT : pd.DataFrame
        OT sheet from Foir_Model.  Must contain 'Lead ID' and
        'New Monthly Income'.  Pass an empty DataFrame when running in
        standalone mode.

    Returns
    -------
    pd.DataFrame
        Updated copy of *inc* with all income columns populated.
    """
    inc = inc.copy()

    # ── 1. Resolve total income ───────────────────────────────────────────────
    # Use model income where available; fall back to FAMILY_MONTHLY_INCOME.
    inc['NEW INCOME FROM MODEL'] = (
        inc['LEAD_ID']
        .map(OT.set_index('Lead ID')['New Monthly Income'])
        .fillna(0)
    )
    no_model = inc['NEW INCOME FROM MODEL'] == 0
    if 'FAMILY_MONTHLY_INCOME' in inc.columns:
        inc.loc[no_model, 'NEW INCOME FROM MODEL'] = (
            inc.loc[no_model, 'FAMILY_MONTHLY_INCOME'].fillna(0)
        )

    n = len(inc)

    # ── 2. App / Co-app split  (rand 40–45 % for app) ────────────────────────
    rand_app_pct = np.random.uniform(0.40, 0.45, size=n)
    inc['app']    = (
        rand_app_pct * inc['NEW INCOME FROM MODEL'].astype(float)
    ).round().astype(int)
    inc['co app'] = inc['NEW INCOME FROM MODEL'].astype(int) - inc['app']

    inc = inc.fillna(0)

    # ── 3. Applicant: DailyEarnings / Agriculture split (rand 65–85 %) ───────
    rand_daily_pct        = np.random.uniform(0.65, 0.85, size=n)
    inc['DailyEarningsCust'] = (
        rand_daily_pct * inc['app'].astype(float)
    ).round().astype(int)
    inc['AgricultureCust']   = inc['app'] - inc['DailyEarningsCust']

    # ── 4. Applicant total ────────────────────────────────────────────────────
    inc['TotalHouseHoldIncomeCust'] = (
        inc['RentalIncomeCust'].fillna(0)
        + inc['PensionCust'].fillna(0)
        + inc['DailyEarningsCust'].fillna(0)
        + inc['SalaryCust'].fillna(0)
        + inc['HOUSE_GOVT_TF'].fillna(0)
        + inc['HOUSE_REMITTANCES'].fillna(0)
        + inc['HOUSE_AGRI_ALLIED'].fillna(0)
        + inc['AgricultureCust'].fillna(0)
        + inc['OtherAlliedActivitiesCust'].fillna(0)
    )

    # ── 5. Co-app: Agriculture / Other split (rand 65–85 %) ──────────────────
    rand_agri_pct              = np.random.uniform(0.65, 0.85, size=n)
    inc['AgricultureCoApp']    = (
        rand_agri_pct * inc['co app'].astype(float)
    ).round().astype(int)
    inc['OtherAlliedActivitiesCoApp'] = inc['co app'] - inc['AgricultureCoApp']

    # ── 6. Co-app total ───────────────────────────────────────────────────────
    inc['TotalHouseHoldIncomeCoApp'] = (
        inc['RentalIncomeCoApp'].fillna(0)
        + inc['PensionCoApp'].fillna(0)
        + inc['DailyEarningsCoApp'].fillna(0)
        + inc['SalaryCoApp'].fillna(0)
        + inc['COAPP_HOUSE_GOVT_TF'].fillna(0)
        + inc['COAPP_HOUSE_REMITTANCES'].fillna(0)
        + inc['COAPP_HOUSE_AGRI_ALLIED'].fillna(0)
        + inc['AgricultureCoApp'].fillna(0)
        + inc['OtherAlliedActivitiesCoApp'].fillna(0)
    )

    # ── 7. Family total ───────────────────────────────────────────────────────
    inc['FAMILY_MONTHLY_INCOME'] = (
        inc['TotalHouseHoldIncomeCust'] + inc['TotalHouseHoldIncomeCoApp']
    )

    return inc
