"""
Sınav kağıdı PDF üretim servisi.
TestForm + ExamTemplate → WeasyPrint → PDF bytes
"""
from datetime import date
from django.template.loader import render_to_string
from django.conf import settings


def _resolve_variable(text: str, context: dict) -> str:
    """Şablon metin içindeki {variable} alanlarını doldurur."""
    for key, val in context.items():
        text = text.replace(f'{{{key}}}', str(val))
    return text


def _get_choice_layout_class(fi, template) -> str:
    """Soru seçeneklerinin uzunluğuna göre en uygun CSS sınıfını döner."""
    template_layout = template.choice_layout
    if template_layout != 'auto':
        return template_layout

    item = fi.item_instance.item
    if item.item_type not in ['MCQ', 'TF']:
        return 'vertical'

    # Şık metinlerini al (override varsa onu kullan)
    if fi.choice_overrides:
        texts = [str(c.get('text', '')) for c in fi.choice_overrides]
    else:
        texts = [str(c.text) for c in item.choices.all()]

    if not texts:
        return 'vertical'

    max_len = max(len(t) for t in texts)
    
    # Sayfa sütun sayısına göre eşik değerleri daralt
    # 1 sütun: 22/55, 2 sütun: 12/30, 3 sütun: 8/20
    col_factor = template.column_count
    t3 = 22 if col_factor == 1 else (12 if col_factor == 2 else 8)
    t2 = 55 if col_factor == 1 else (30 if col_factor == 2 else 20)

    if max_len < t3:     return 'grid-3'
    elif max_len < t2:   return 'grid-2'
    else:                return 'vertical'


def generate_exam_pdf(test_form, template: "ExamTemplate", with_answer_key: bool = False) -> bytes:
    """
    test_form: TestForm instance
    template: ExamTemplate instance
    with_answer_key: True ise cevap anahtarı sayfası eklenir
    returns: PDF içeriği (bytes)
    """
    from weasyprint import HTML

    tpl = template # Define tpl early

    # Şablon değişkenleri
    var_context = {
        'form_name': test_form.name,
        'course': test_form.course.name if test_form.course else 'Genel',
        'semester': test_form.course.semester if test_form.course else 'Genel',
        'date': date.today().strftime('%d.%m.%Y'),
        'page': '<span class="page-number"></span>',
        'total_pages': '<span class="total-pages"></span>',
    }

    # Özel HTML başlık varsa çöz (resolve)
    header_html_resolved = None
    if tpl.header_html:
        header_html_resolved = _resolve_variable(tpl.header_html, var_context)

    header_ctx = {
        'left': _resolve_variable(tpl.header_left, var_context),
        'center': _resolve_variable(tpl.header_center, var_context),
        'right': _resolve_variable(tpl.header_right, var_context),
        'show_line': tpl.show_header_line,
        'html': header_html_resolved,
    }
    footer_ctx = {
        'left': _resolve_variable(tpl.footer_left, var_context),
        'center': _resolve_variable(tpl.footer_center, var_context),
        'right': _resolve_variable(tpl.footer_right, var_context),
        'show_line': tpl.show_footer_line,
    }

    form_items = test_form.form_items.select_related(
        'item_instance__item'
    ).prefetch_related('item_instance__item__choices').order_by('order')

    # Her soru için layout sınıfını hesapla
    for fi in form_items:
        fi.layout_class = _get_choice_layout_class(fi, template)

    html_string = render_to_string('itempool/exam_print.html', {
        'test_form': test_form,
        'form_items': form_items,
        'template': tpl,
        'header': header_ctx,
        'footer': footer_ctx,
        'with_answer_key': with_answer_key,
        'STATIC_URL': settings.STATIC_URL,
    })

    pdf_bytes = HTML(string=html_string, base_url=settings.BASE_DIR).write_pdf()
    return pdf_bytes
