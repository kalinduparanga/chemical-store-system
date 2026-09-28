"""
Reports and Historical Traceability Router.
"""

from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import date
from app.services.report_service import ReportService
from app.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/stock-balance")
def get_stock_balance():
    return ReportService.get_stock_balance_report()

@router.get("/daily")
def get_daily_movement(report_date: Optional[str] = None):
    r_date = report_date or str(date.today())
    return ReportService.get_daily_movement_report(r_date)

@router.get("/monthly-usage")
def get_monthly_usage(year_month: Optional[str] = None):
    ym = year_month or date.today().strftime("%Y-%m")
    return ReportService.get_monthly_usage_report(ym)

@router.get("/ammonia-audit")
def get_ammonia_audit():
    return ReportService.get_ammonia_audit_report()

@router.get("/physical-vs-system")
def get_physical_vs_system(start_date: Optional[str] = None, end_date: Optional[str] = None):
    return ReportService.get_physical_vs_system_report(start_date, end_date)

@router.get("/historical-transactions")
def get_historical_transactions(
    search: Optional[str] = None,
    transaction_type: Optional[str] = None,
    chemical_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    return ReportService.get_historical_transactions(
        search=search,
        transaction_type=transaction_type,
        chemical_id=chemical_id,
        start_date=start_date,
        end_date=end_date
    )
