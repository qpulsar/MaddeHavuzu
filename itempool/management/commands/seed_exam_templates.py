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


BAUN_LOGO_SVG = '''<svg width="75" height="75" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="48" fill="none" stroke="#0f7b88" stroke-width="3"/>
  <circle cx="50" cy="50" r="44" fill="#0f7b88"/>
  <circle cx="50" cy="50" r="32" fill="#ffffff"/>
  <circle cx="50" cy="50" r="30" fill="#0f7b88"/>
  <path id="topArcBAUN" fill="none" d="M 12 50 A 38 38 0 1 1 88 50" />
  <text font-family="Arial, sans-serif" font-size="7.5" font-weight="bold" fill="#ffffff">
    <textPath href="#topArcBAUN" startOffset="50%" text-anchor="middle">BALIKESİR ÜNİVERSİTESİ</textPath>
  </text>
  <path id="botArcBAUN" fill="none" d="M 88 50 A 38 38 0 0 1 12 50" />
  <text font-family="Arial, sans-serif" font-size="7" font-weight="bold" fill="#ffffff">
    <textPath href="#botArcBAUN" startOffset="50%" text-anchor="middle">★ 1992 ★</textPath>
  </text>
  <path d="M 32 55 Q 50 40 68 55 Q 50 62 32 55 Z" fill="#ffffff"/>
  <circle cx="50" cy="42" r="5" fill="#ffffff"/>
  <path d="M 36 60 Q 50 68 64 60" stroke="#ffffff" stroke-width="2" fill="none"/>
</svg>'''


NEF_LOGO_SVG = '''<svg width="75" height="75" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="48" fill="none" stroke="#b84c7d" stroke-width="3"/>
  <circle cx="50" cy="50" r="44" fill="#b84c7d"/>
  <circle cx="50" cy="50" r="32" fill="#ffffff"/>
  <circle cx="50" cy="50" r="30" fill="#0f7b88"/>
  <path id="topArcNEF" fill="none" d="M 10 50 A 40 40 0 1 1 90 50" />
  <text font-family="Arial, sans-serif" font-size="6.2" font-weight="bold" fill="#ffffff">
    <textPath href="#topArcNEF" startOffset="50%" text-anchor="middle">NECATİBEY EĞİTİM FAKÜLTESİ</textPath>
  </text>
  <path id="botArcNEF" fill="none" d="M 88 50 A 38 38 0 0 1 12 50" />
  <text font-family="Arial, sans-serif" font-size="7" font-weight="bold" fill="#ffffff">
    <textPath href="#botArcNEF" startOffset="50%" text-anchor="middle">★ 1910 ★</textPath>
  </text>
  <path d="M 35 56 C 42 50, 48 53, 50 56 C 52 53, 58 50, 65 56 L 65 44 C 58 40, 52 42, 50 45 C 48 42, 42 40, 35 44 Z" fill="#ffffff"/>
  <circle cx="50" cy="38" r="4" fill="#ffffff"/>
</svg>'''


def _make_nef_header_html():
    """Balıkesir Üniversitesi Necatibey Eğitim Fakültesi resmi kurumsal sınav başlığı HTML'i."""
    return f'''<table width="100%" style="border-collapse:collapse; font-family:Arial, sans-serif; margin-bottom:4px;">
<tr>
<td style="width:18%; text-align:left; vertical-align:middle;">
{BAUN_LOGO_SVG}
</td>
<td style="width:64%; text-align:center; vertical-align:middle;">
<div style="font-size:13pt; font-weight:bold; color:#000; letter-spacing:0.3px; line-height:1.2;">BALIKESİR ÜNİVERSİTESİ NECATİBEY EĞİTİM FAKÜLTESİ</div>
<div style="font-size:12pt; font-weight:bold; color:#000; margin-top:4px;">{{semester}} Yarıyıl Sonu Sınavı</div>
</td>
<td style="width:18%; text-align:right; vertical-align:middle;">
{NEF_LOGO_SVG}
<div style="font-size:10pt; font-weight:bold; color:#000; margin-top:2px;">{{date}}</div>
</td>
</tr>
</table>
<table width="100%" style="border-collapse:collapse; font-family:Arial, sans-serif; font-size:9.5pt; color:#000; margin-top:6px; line-height:1.5;">
<tr>
<td style="text-align:left;">
<strong>Ders Kodu ve Adı:</strong> <span style="text-decoration:underline; font-weight:bold;">{{course_code}} {{course}}</span>
</td>
<td style="text-align:right;">
<strong>Ders Sorumlusu:</strong> <span style="text-decoration:underline; font-weight:bold;">{{teacher_name}}</span>
</td>
</tr>
<tr>
<td colspan="2" style="padding-top:4px;">
<table width="100%" style="border-collapse:collapse; font-size:9.5pt;">
<tr>
<td style="text-align:left; width:45%;">
<strong>Öğrenci Adı Soyadı:</strong> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>
</td>
<td style="text-align:center; width:35%;">
<strong>Numarası:</strong> <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>
</td>
<td style="text-align:right; width:20%;">
<strong>S ü r e :</strong> 3 0 &nbsp; d k
</td>
</tr>
</table>
</td>
</tr>
</table>
<div style="border-bottom:2px solid #000; margin-top:6px; margin-bottom:10px;"></div>'''


TEMPLATES = [
    {
        'name': 'Necatibey Eğitim Fakültesi (Kurumsal)',
        'is_default': True,
        'is_shared': True,
        'column_count': 1,
        'column_divider': False,
        'font_family': 'Arial, sans-serif',
        'font_size': 10,
        'question_spacing': 12,
        'choice_layout': 'vertical',
        'header_html': _make_nef_header_html(),
        'footer_html': _make_footer_html('{page} / {total_pages}'),
        'show_student_info_box': False,
        'show_header_line': False,
        'show_footer_line': True,
    },
    {
        'name': 'Standart (1 Sütun)',
        'is_default': False,
        'is_shared': True,
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
        'is_shared': True,
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
        'is_shared': True,
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
        'is_shared': True,
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
        'is_shared': True,
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
