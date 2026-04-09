"""
Varsayılan sınav kağıdı şablonlarını veritabanına ekler.
GrapesJS tabanlı header/footer tasarımlarıyla birlikte.
Kullanım: python manage.py seed_exam_templates
"""
from django.core.management.base import BaseCommand
from itempool.models import ExamTemplate


def _make_header_html(left='', center='', right=''):
    """3 sütunlu başlık HTML'i üretir (GrapesJS çıktısı formatında)."""
    return f'''<table width="100%" style="border-collapse:collapse;font-family:inherit;">
<tr>
<td style="width:33%;text-align:left;padding:4px;vertical-align:middle;">
<span style="font-size:10pt;color:#333;">{left}</span>
</td>
<td style="width:34%;text-align:center;padding:4px;vertical-align:middle;">
<strong style="font-size:12pt;">{center}</strong>
</td>
<td style="width:33%;text-align:right;padding:4px;vertical-align:middle;">
<span style="font-size:10pt;color:#333;">{right}</span>
</td>
</tr>
</table>'''


def _make_footer_html(text=''):
    """Basit alt bilgi HTML'i üretir."""
    if not text:
        return ''
    return f'<div style="text-align:center;font-size:9pt;color:#666;">{text}</div>'


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
        'header_html': _make_header_html(
            left='{course} — {semester}',
            center='{form_name}',
            right='Tarih: {date}'
        ),
        'footer_html': _make_footer_html('{page} / {total_pages}'),
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
        'header_html': _make_header_html(
            left='{course} — {semester}',
            center='{form_name}',
            right='Tarih: {date}'
        ),
        'footer_html': _make_footer_html('{page} / {total_pages}'),
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
        'header_html': _make_header_html(
            left='',
            center='{form_name}',
            right=''
        ),
        'footer_html': _make_footer_html('{page} / {total_pages}'),
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
        'header_html': _make_header_html(
            left='{course}',
            center='{form_name}',
            right='Tarih: {date}'
        ),
        'footer_html': _make_footer_html('Sayfa {page} / {total_pages}'),
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
        'header_html': '',
        'footer_html': _make_footer_html('{page}'),
        'show_header_line': False,
        'show_footer_line': False,
        'show_student_info_box': False,
    },
]


class Command(BaseCommand):
    help = 'Varsayılan sınav kağıdı şablonlarını ekler (GrapesJS formatında)'

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
