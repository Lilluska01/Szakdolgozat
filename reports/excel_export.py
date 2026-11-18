from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from config.config import Config
from reports.report_service import ReportService

class ExcelExport:
    def __init__(self, service=None):
        self.service = service or ReportService()

    def export(self, path=None):
        Config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = path or (Config.REPORT_DIR / 'jelenleti_riport.xlsx')
        wb = Workbook()
        daily = wb.active
        daily.title = 'Napi összesítés'
        daily.append(['Dátum', 'Belépések', 'Kilépések', 'Összes esemény'])
        for row in self.service.get_daily_stats():
            daily.append([row['day'], row['entries'] or 0, row['exits'] or 0, row['total'] or 0])
        users = wb.create_sheet('Hallgatók')
        users.append(['Azonosító', 'Név', 'Neptun-kód', 'Belépések', 'Kilépések', 'Események'])
        for row in self.service.get_user_stats():
            users.append([row['id'], row['name'], row['neptun'] or '', row['entries'] or 0, row['exits'] or 0, row['total_scans'] or 0])
        for sheet in wb.worksheets:
            sheet.freeze_panes = 'A2'; sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='17365D')
                cell.alignment = Alignment(vertical='center')
            sheet.row_dimensions[1].height = 24
            for column in sheet.columns:
                width = min(36, max(12, max(len(str(cell.value or '')) for cell in column) + 2))
                sheet.column_dimensions[get_column_letter(column[0].column)].width = width
        wb.save(path)
        return str(path)
