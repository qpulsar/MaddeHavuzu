import csv
import io
import openpyxl
from itempool.models import LearningOutcome, ItemPool

class ExcelOutcomeImportService:
    """
    Excel (.xlsx) ve CSV (.csv) dosyalarından Öğrenme Çıktılarını toplu olarak veritabanına kaydeden servis.
    """
    BLOOM_MAP = {
        'bilgi': LearningOutcome.BloomLevel.REMEMBERING,
        'hatırlama': LearningOutcome.BloomLevel.REMEMBERING,
        'anlama': LearningOutcome.BloomLevel.UNDERSTANDING,
        'kavrama': LearningOutcome.BloomLevel.UNDERSTANDING,
        'uygulama': LearningOutcome.BloomLevel.APPLYING,
        'analiz': LearningOutcome.BloomLevel.ANALYZING,
        'analiz etme': LearningOutcome.BloomLevel.ANALYZING,
        'sentez': LearningOutcome.BloomLevel.CREATING,
        'yaratma': LearningOutcome.BloomLevel.CREATING,
        'değerlendirme': LearningOutcome.BloomLevel.EVALUATING,
        'remembering': LearningOutcome.BloomLevel.REMEMBERING,
        'understanding': LearningOutcome.BloomLevel.UNDERSTANDING,
        'applying': LearningOutcome.BloomLevel.APPLYING,
        'analyzing': LearningOutcome.BloomLevel.ANALYZING,
        'evaluating': LearningOutcome.BloomLevel.EVALUATING,
        'creating': LearningOutcome.BloomLevel.CREATING,
    }

    def __init__(self, pool_id, uploaded_file):
        self.pool = ItemPool.objects.get(id=pool_id)
        self.uploaded_file = uploaded_file

    def process(self):
        filename = self.uploaded_file.name.lower()
        if filename.endswith('.csv'):
            return self._process_csv()
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            return self._process_excel()
        else:
            raise ValueError("Desteklenmeyen dosya formatı. Lütfen .xlsx veya .csv yükleyin.")

    def _process_excel(self):
        wb = openpyxl.load_workbook(self.uploaded_file, data_only=True)
        sheet = wb.active
        
        created_count = 0
        updated_count = 0

        # Başlık satırını atla
        first_row = True
        for row in sheet.iter_rows(values_only=True):
            if first_row:
                first_row = False
                continue
            if not row or not any(row):
                continue
                
            code = str(row[0]).strip() if row[0] is not None else ""
            if not code or code.lower() in ['kod', 'code']:
                continue

            description = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            level_raw = str(row[2]).strip().lower() if len(row) > 2 and row[2] is not None else "anlama"
            subject = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            order_val = 0
            if len(row) > 4 and row[4] is not None:
                try:
                    order_val = int(row[4])
                except ValueError:
                    order_val = 0

            bloom_level = self.BLOOM_MAP.get(level_raw, LearningOutcome.BloomLevel.UNDERSTANDING)

            obj, created = LearningOutcome.objects.update_or_create(
                pool=self.pool,
                code=code,
                defaults={
                    'description': description,
                    'level': bloom_level,
                    'subject': subject,
                    'order': order_val,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count

    def _process_csv(self):
        file_data = self.uploaded_file.read()
        try:
            text = file_data.decode('utf-8')
        except UnicodeDecodeError:
            text = file_data.decode('latin-1')

        reader = csv.reader(io.StringIO(text))
        first_row = True
        created_count = 0
        updated_count = 0

        for row in reader:
            if first_row:
                first_row = False
                continue
            if not row or not any(row):
                continue

            code = row[0].strip()
            if not code or code.lower() in ['kod', 'code']:
                continue

            description = row[1].strip() if len(row) > 1 else ""
            level_raw = row[2].strip().lower() if len(row) > 2 else "anlama"
            subject = row[3].strip() if len(row) > 3 else ""
            order_val = 0
            if len(row) > 4:
                try:
                    order_val = int(row[4])
                except ValueError:
                    order_val = 0

            bloom_level = self.BLOOM_MAP.get(level_raw, LearningOutcome.BloomLevel.UNDERSTANDING)

            obj, created = LearningOutcome.objects.update_or_create(
                pool=self.pool,
                code=code,
                defaults={
                    'description': description,
                    'level': bloom_level,
                    'subject': subject,
                    'order': order_val,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count
