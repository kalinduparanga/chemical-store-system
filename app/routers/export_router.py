"""
Export Router for downloading genuine Excel (.xlsx) and PDF (.pdf) reports.
"""

from fastapi import APIRouter, Response, HTTPException, Query
from typing import Optional
from datetime import date
from app.services.report_service import ReportService
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/export", tags=["Export"])

@router.get("/stock-balance/excel")
def export_stock_balance_excel():
    data = ReportService.get_stock_balance_report()
    content = ExportService.export_stock_balance_excel(data)
    filename = f"Stock_Balance_Report_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/stock-balance/pdf")
def export_stock_balance_pdf():
    data = ReportService.get_stock_balance_report()
    headers = ["Chemical", "Batch No", "Mfg Date", "Expiry Date", "Location", "Received Qty", "Current Stock", "Status"]
    rows = []
    for r in data:
        rows.append([
            r["chemical_name"], r["batch_number"], r["manufacturing_date"] or "N/A",
            r["expiry_date"], r["storage_location_name"], f"{r['received_quantity']:.1f} {r['unit']}",
            f"{r['current_quantity']:.1f} {r['unit']}", r["status"]
        ])
    content = ExportService.export_report_pdf("Stock Balance Report", headers, rows, landscape_mode=True)
    filename = f"Stock_Balance_Report_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@router.get("/daily/excel")
def export_daily_excel(report_date: Optional[str] = None):
    r_date = report_date or str(date.today())
    data = ReportService.get_daily_movement_report(r_date)
    content = ExportService.export_daily_report_excel(r_date, data)
    filename = f"Daily_Store_Movement_{r_date}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/daily/pdf")
def export_daily_pdf(report_date: Optional[str] = None):
    r_date = report_date or str(date.today())
    data = ReportService.get_daily_movement_report(r_date)
    headers = ["Chemical", "Batch", "Expiry Date", "Location", "Opening", "Rcvd", "Used", "Trf In", "Trf Out", "Closing", "Unit"]
    rows = []
    for r in data:
        rows.append([
            r["chemical_name"], r["batch_number"], r["expiry_date"], r["storage_location"],
            f"{r['opening_stock']:.1f}", f"{r['received']:.1f}", f"{r['used']:.1f}",
            f"{r['transfer_in']:.1f}", f"{r['transfer_out']:.1f}", f"{r['closing_stock']:.1f}", r["unit"]
        ])
    content = ExportService.export_report_pdf(f"Daily Store Movement ({r_date})", headers, rows, landscape_mode=True)
    filename = f"Daily_Store_Movement_{r_date}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@router.get("/monthly-usage/excel")
def export_monthly_usage_excel(year_month: Optional[str] = None):
    ym = year_month or date.today().strftime("%Y-%m")
    data = ReportService.get_monthly_usage_report(ym)
    content = ExportService.export_monthly_usage_excel(ym, data)
    filename = f"Monthly_Chemical_Usage_{ym}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/monthly-usage/pdf")
def export_monthly_usage_pdf(year_month: Optional[str] = None):
    ym = year_month or date.today().strftime("%Y-%m")
    data = ReportService.get_monthly_usage_report(ym)
    headers = ["Chemical Name", "Batch Number", "Expiry Date", "Location", "Trans Count", "Total Qty Used", "Purposes"]
    rows = []
    for r in data:
        rows.append([
            r["chemical_name"], r["batch_number"], r["expiry_date"], r["storage_location"],
            r["transaction_count"], f"{r['total_quantity_used']:.2f} {r['unit']}", r.get("purposes") or "—"
        ])
    content = ExportService.export_report_pdf(f"Monthly Chemical Usage ({ym})", headers, rows, landscape_mode=True)
    filename = f"Monthly_Chemical_Usage_{ym}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@router.get("/ammonia-audit/excel")
def export_ammonia_audit_excel():
    audit_data = ReportService.get_ammonia_audit_report()
    content = ExportService.export_ammonia_audit_excel(audit_data)
    filename = f"Ammonia_Audit_Report_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/ammonia-audit/pdf")
def export_ammonia_audit_pdf():
    audit_data = ReportService.get_ammonia_audit_report()
    headers = ["Barrel ID", "Batch No", "Original (kg)", "Current (kg)", "Supplier", "Expiry Date", "Location", "Status"]
    rows = []
    for b in audit_data.get("barrels", []):
        rows.append([
            b["barrel_id"], b["batch_number"], f"{b['original_quantity']:.1f}",
            f"{b['current_quantity']:.1f}", b["supplier_name"] or "—", b["expiry_date"],
            b["location_name"], b["status"]
        ])
    content = ExportService.export_report_pdf("Ammonia Barrels & Dilution Audit", headers, rows, landscape_mode=True)
    filename = f"Ammonia_Audit_Report_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@router.get("/physical-vs-system/excel")
def export_physical_vs_system_excel(start_date: Optional[str] = None, end_date: Optional[str] = None):
    data = ReportService.get_physical_vs_system_report(start_date, end_date)
    content = ExportService.export_physical_vs_system_excel(data)
    filename = f"Physical_vs_System_Reconciliation_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/physical-vs-system/pdf")
def export_physical_vs_system_pdf(start_date: Optional[str] = None, end_date: Optional[str] = None):
    data = ReportService.get_physical_vs_system_report(start_date, end_date)
    headers = ["Date & Time", "Location", "Chemical", "Physical Qty", "System Qty", "Variance", "Remarks", "Inspector"]
    rows = []
    for r in data:
        rows.append([
            f"{r['date']} {r['time']}", r["storage_location_name"], r["chemical_name"],
            f"{r['physical_quantity']:.2f} {r['unit']}", f"{r['system_quantity']:.2f} {r['unit']}",
            f"{r['variance']:+.2f} {r['unit']}", r.get("remarks") or "—", r["operator_name"]
        ])
    content = ExportService.export_report_pdf("Physical vs System Stock Reconciliation", headers, rows, landscape_mode=True)
    filename = f"Physical_vs_System_Reconciliation_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@router.get("/historical-records/excel")
def export_historical_records_excel(
    search: Optional[str] = None,
    transaction_type: Optional[str] = None,
    chemical_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    data = ReportService.get_historical_transactions(
        search=search, transaction_type=transaction_type, chemical_id=chemical_id,
        start_date=start_date, end_date=end_date
    )
    content = ExportService.export_historical_records_excel(data)
    filename = f"Historical_Transactions_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
