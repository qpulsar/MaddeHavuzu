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


def generate_exam_pdf(test_form, template: "ExamTemplate", with_answer_key: bool = False) -> bytes:
    """
    test_form: TestForm instance
    template: ExamTemplate instance
    with_answer_key: True ise cevap anahtarı sayfası eklenir
    returns: PDF içeriği (bytes)
    """
    from weasyprint import HTML

    # Şablon değişkenleri
    var_context = {
        'form_name': test_form.name,
        'course': test_form.course.name if test_form.course else 'Genel',
        'semester': test_form.course.semester if test_form.course else 'Genel',
        'date': date.today().strftime('%d.%m.%Y'),
        'page': '<span class="page-number"></span>',
        'total_pages': '<span class="total-pages"></span>',
    }

    tpl = template

    header_ctx = {
        'left': _resolve_variable(tpl.header_left, var_context),
        'center': _resolve_variable(tpl.header_center, var_context),
        'right': _resolve_variable(tpl.header_right, var_context),
        'show_line': tpl.show_header_line,
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
