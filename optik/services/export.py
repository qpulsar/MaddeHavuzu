"""
Export Service
==============
Puanlama sonuçlarını farklı formatlarda export etme.

Formatlar:
- TSV (Tab-separated values)
- CSV (Comma-separated values)
- XLSX (Excel)

Detail Levels:
- 0: Özet (student_no, total_score, booklet)
- 1: Detay (her madde için sütun)

Kaynak: omr_analysis/service_export.py

Farklar:
- CSV `csv` modülüyle yazılır (virgül/tırnak içeren değerler doğru kaçırılır).
- XLSX sütun genişliklerinde `chr(64 + idx)` yerine `get_column_letter`
  (26'dan fazla sütunda bozuluyordu).
"""

import csv
import io
from typing import List, Any, Tuple

from optik.services import scoring as scoring_service


def prepare_export_data(
    batch_id: str,
    detail_level: int = 0
) -> Tuple[List[str], List[List[Any]]]:
    """
    Export için veriyi hazırla.
    
    Args:
        batch_id: Batch ID
        detail_level: 0=özet, 1=detay
        
    Returns:
        (columns, rows) tuple
        
    Örnek:
        columns = ["student_no", "total_score", "booklet"]
        rows = [
            ["202422102345", 85.5, "B"],
            ["202433344556", 72.0, "A"]
        ]
    """
    
    # Scores'u al
    scores = scoring_service.get_batch_scores(batch_id)
    
    if not scores:
        return ([], [])
    
    records = scores.get("records", [])
    
    if not records:
        return ([], [])
    
    # Base columns
    base_cols = ["student_no", "total_score", "class_code", "seating_cell_id", "booklet"]
    
    # Detail level 1: Her madde için sütun ekle
    item_cols = []
    if detail_level == 1:
        # Tüm maddeleri bul
        all_items = set()
        for rec in records:
            item_scores = rec.get("item_scores", {})
            all_items.update(item_scores.keys())
        
        # Q1, Q2, Q3... şeklinde sırala
        def item_sort_key(item_id: str) -> int:
            try:
                return int(item_id.replace("Q", ""))
            except Exception:
                return 999999
        
        item_cols = sorted(list(all_items), key=item_sort_key)
    
    columns = base_cols + item_cols
    
    # Rows oluştur
    rows = []
    for rec in records:
        row = []
        
        # Base columns
        row.append(rec.get("student_no", ""))
        row.append(rec.get("summary", {}).get("total_points", 0))
        row.append(rec.get("class_code", ""))
        row.append((rec.get("seating") or {}).get("cell_id", ""))
        row.append(rec.get("booklet", ""))
        
        # Item columns (detail level 1)
        if detail_level == 1:
            item_scores = rec.get("item_scores", {})
            for item_id in item_cols:
                if item_id in item_scores:
                    # Madde puanı
                    points = item_scores[item_id].get("points", 0)
                    row.append(points)
                else:
                    row.append("")
        
        rows.append(row)
    
    return (columns, rows)


def export_to_tsv(batch_id: str, detail_level: int = 0) -> bytes:
    """
    TSV formatında export.
    
    Args:
        batch_id: Batch ID
        detail_level: 0=özet, 1=detay
        
    Returns:
        TSV içeriği (bytes)
    """
    
    columns, rows = prepare_export_data(batch_id, detail_level)
    
    if not columns:
        return b"No data"
    
    # TSV oluştur
    lines = []
    
    # Header
    lines.append("\t".join(columns))
    
    # Rows
    for row in rows:
        lines.append("\t".join(str(val) for val in row))
    
    content = "\n".join(lines)
    return content.encode("utf-8")


def export_to_csv(batch_id: str, detail_level: int = 0) -> bytes:
    """
    CSV formatında export.
    
    Args:
        batch_id: Batch ID
        detail_level: 0=özet, 1=detay
        
    Returns:
        CSV içeriği (bytes)
    """
    
    columns, rows = prepare_export_data(batch_id, detail_level)
    
    if not columns:
        return b"No data"
    
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def export_to_xlsx(batch_id: str, detail_level: int = 0) -> bytes:
    """
    Excel (XLSX) formatında export.
    
    Args:
        batch_id: Batch ID
        detail_level: 0=özet, 1=detay
        
    Returns:
        Excel dosyası (bytes)
    """
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError("openpyxl gerekli. Yükleyin: pip install openpyxl")
    
    columns, rows = prepare_export_data(batch_id, detail_level)
    
    if not columns:
        # Boş workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Scores"
        ws["A1"] = "No data"
        
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()
    
    # Workbook oluştur
    wb = Workbook()
    ws = wb.active
    ws.title = "Scores"
    
    # Header row (bold, mavi arka plan)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    # Data rows
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            
            # Total score sütununu bold yap
            if columns[col_idx - 1] == "total_score":
                cell.font = Font(bold=True)
    
    # Sütun genişliklerini ayarla
    for col_idx, col_name in enumerate(columns, 1):
        if col_name == "student_no":
            ws.column_dimensions[get_column_letter(col_idx)].width = 15
        elif col_name == "total_score":
            ws.column_dimensions[get_column_letter(col_idx)].width = 12
        elif col_name.startswith("Q"):
            ws.column_dimensions[get_column_letter(col_idx)].width = 8
        else:
            ws.column_dimensions[get_column_letter(col_idx)].width = 12
    
    # Auto-filter ekle
    ws.auto_filter.ref = ws.dimensions
    
    # Freeze first row
    ws.freeze_panes = "A2"
    
    # BytesIO'ya kaydet
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    
    return buf.read()


def get_export_filename(batch_id: str, format: str, detail_level: int) -> str:
    """
    Export dosya adı oluştur.
    
    Args:
        batch_id: Batch ID
        format: tsv, csv, xlsx
        detail_level: 0=özet, 1=detay
        
    Returns:
        Dosya adı
    """
    
    detail_suffix = "summary" if detail_level == 0 else "detail"
    
    return f"{batch_id}_scores_{detail_suffix}.{format}"
