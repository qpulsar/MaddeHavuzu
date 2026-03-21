"""
Varsayılan sınav kağıdı şablonlarını veritabanına ekler.
Kullanım: python manage.py seed_exam_templates
"""
from django.core.management.base import BaseCommand
from itempool.models import ExamTemplate


TEMPLATES = [
    {
        'name': 'Standart (1 Sütun)',
        'is_default': True,
        'column_count': 1,
        'column_divider': False,
        'font_family': 'Times New Roman, serif',
        'font_size': 11,
        'question_spacing': 12,
        'choice_layout': 'vertical',
        'header_center': '{form_name}',
        'header_left': '{course} — {semester}',
        'header_right': 'Tarih: {date}',
        'footer_center': '{page} / {total_pages}',
        'show_student_info_box': True,
    },
    {
        'name': '2 Sütun',
        'is_default': False,
        'column_count': 2,
        'column_divider': True,
        'font_family': 'Times New Roman, serif',
        'font_size': 10,
        'question_spacing': 8,
        'choice_layout': 'vertical',
        'header_center': '{form_name}',
        'header_left': '{course} — {semester}',
        'header_right': 'Tarih: {date}',
        'footer_center': '{page} / {total_pages}',
        'show_student_info_box': True,
    },
    {
        'name': 'Yoğun (3 Sütun)',
        'is_default': False,
        'column_count': 3,
        'column_divider': True,
        'font_family': 'Arial, sans-serif',
        'font_size': 9,
        'question_spacing': 6,
        'choice_layout': 'horizontal',
        'header_center': '{form_name}',
        'header_left': '',
        'header_right': '',
        'footer_center': '{page} / {total_pages}',
        'show_student_info_box': False,
    },
    {
        'name': 'Geniş Kenar (Not Alanı)',
        'is_default': False,
        'column_count': 1,
        'column_divider': False,
        'font_family': 'Georgia, serif',
        'font_size': 11,
        'question_spacing': 14,
        'margin_right': 45,
        'choice_layout': 'vertical',
        'header_center': '{form_name}',
        'header_left': '{course}',
        'header_right': 'Tarih: {date}',
        'footer_center': 'Sayfa {page} / {total_pages}',
        'show_student_info_box': True,
    },
    {
        'name': 'Sade (Başlık Yok)',
        'is_default': False,
        'column_count': 1,
        'column_divider': False,
        'font_family': 'Arial, sans-serif',
        'font_size': 12,
        'question_spacing': 14,
        'header_left': '',
        'header_center': '',
        'header_right': '',
        'footer_center': '{page}',
        'show_header_line': False,
        'show_footer_line': False,
        'show_student_info_box': False,
    },
]


class Command(BaseCommand):
    help = 'Varsayılan sınav kağıdı şablonlarını ekler'

    def handle(self, *args, **options):
        created = 0
        for tpl in TEMPLATES:
            obj, was_created = ExamTemplate.objects.update_or_create(
                name=tpl['name'],
                defaults=tpl
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {obj.name}'))
            else:
                self.stdout.write(f'  ~ {obj.name} (güncellendi)')

        self.stdout.write(self.style.SUCCESS(
            f'\nTamamlandı: {created} yeni şablon eklendi.'
        ))
