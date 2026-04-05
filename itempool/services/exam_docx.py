"""
Sınav kağıdı Word (.docx) üretim servisi.
TestForm + ExamTemplate → python-docx → .docx bytes
"""
import io
from datetime import date
from docx import Document
from docx.shared import Pt, Mm, Twips
from docx.enum.section import WD_SECTION, WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def _set_columns(section, column_count, show_divider=False):
    """Bölümün sütun sayısını ayarlar."""
    section.start_type = WD_SECTION.CONTINUOUS
    sectPr = section._sectPr
    cols = sectPr.xpath('./w:cols')[0]
    cols.set(qn('w:num'), str(column_count))
    if show_divider:
        cols.set(qn('w:sep'), '1')
    cols.set(qn('w:space'), '708')  # 0.5 inch approx

def _resolve_variable(text: str, context: dict) -> str:
    """Şablon metin içindeki {variable} alanlarını doldurur."""
    if not text: return ""
    for key, val in context.items():
        text = text.replace(f'{{{key}}}', str(val))
    return text

def generate_exam_docx(test_form, template: "ExamTemplate", with_answer_key: bool = False) -> io.BytesIO:
    """
    Sınav formunu Word (.docx) formatında üretir.
    """
    doc = Document()
    
    # 1. Sayfa Ayarları
    section = doc.sections[0]
    # Kağıt boyutu (Basit eşleştirme)
    if template.page_size == 'A4':
        section.page_height = Mm(297)
        section.page_width = Mm(210)
    elif template.page_size == 'A5':
        section.page_height = Mm(210)
        section.page_width = Mm(148)
    
    section.top_margin = Mm(template.margin_top)
    section.bottom_margin = Mm(template.margin_bottom)
    section.left_margin = Mm(template.margin_left)
    section.right_margin = Mm(template.margin_right)

    # 2. Üst Bilgi (Header) - Word'de 3 sütunlu tablo en iyisidir
    var_context = {
        'form_name': test_form.name,
        'course': test_form.course.name if test_form.course else 'Genel',
        'semester': test_form.course.semester if test_form.course else 'Genel',
        'date': date.today().strftime('%d.%m.%Y'),
        'page': '1', # Word dynamic field insertion is complex, using static placeholder
        'total_pages': '?',
    }

    # Font ayarları (Default)
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(template.font_size)

    # Başlık Tablosu
    header_table = doc.add_table(rows=1, cols=3)
    header_table.width = section.page_width - section.left_margin - section.right_margin
    
    cells = header_table.rows[0].cells
    p_left = cells[0].paragraphs[0]
    p_left.text = _resolve_variable(template.header_left, var_context)
    p_left.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    p_center = cells[1].paragraphs[0]
    p_center.text = _resolve_variable(template.header_center, var_context)
    p_center.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    p_right = cells[2].paragraphs[0]
    p_right.text = _resolve_variable(template.header_right, var_context)
    p_right.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    if template.show_header_line:
        doc.add_paragraph().add_run("_" * 80).bold = True # Simple separator

    # 3. Öğrenci Bilgi Kutusu
    if template.show_student_info_box:
        box_table = doc.add_table(rows=1, cols=3)
        box_table.style = 'Table Grid'
        b_cells = box_table.rows[0].cells
        b_cells[0].text = "Ad Soyad:"
        b_cells[1].text = "No:"
        b_cells[2].text = "İmza:"
        doc.add_paragraph() # Spacer

    # 4. Sütun Ayarı (Sorular için)
    if template.column_count > 1:
        _set_columns(section, template.column_count, template.column_divider)

    # 5. Sorular
    form_items = test_form.form_items.select_related(
        'item_instance__item'
    ).prefetch_related('item_instance__item__choices').order_by('order')

    for fi in form_items:
        item = fi.item_instance.item
        
        # Soru Kökü
        p_stem = doc.add_paragraph()
        run_num = p_stem.add_run(f"{fi.order}. ")
        run_num.bold = True
        
        if template.show_question_points:
            run_pts = p_stem.add_run(f"({fi.points} puan) ")
            run_pts.italic = True
            
        p_stem.add_run(item.stem)
        
        # Şıklar (MCQ/TF)
        if item.item_type in ['MCQ', 'TF']:
            if fi.choice_overrides:
                choices = fi.choice_overrides
            else:
                choices = [{'label': c.label, 'text': c.text} for c in item.choices.all()]
            
            # Layout seçimi (Sayfa sütununa göre daraltılmış eşikler)
            max_len = max([len(str(c.get('text', ''))) for c in choices]) if choices else 0
            col_factor = template.column_count
            
            t_vert = 45 if col_factor == 1 else (28 if col_factor == 2 else 18)
            t_grid3 = 20 if col_factor == 1 else (10 if col_factor == 2 else 6)
            
            # 1 Sütun (Vertical)
            if max_len > t_vert or template.choice_layout == 'vertical':
                for c in choices:
                    p_choice = doc.add_paragraph()
                    p_choice.paragraph_format.left_indent = Pt(15)
                    p_choice.paragraph_format.space_after = Pt(template.choice_spacing)
                    p_choice.add_run(f"{c['label']}) ").bold = True
                    p_choice.add_run(str(c['text']))
            
            # Grid (2 veya 3 Sütun)
            else:
                cols_count = 3 if max_len < t_grid3 else 2
                choice_table = doc.add_table(rows=0, cols=cols_count)
                for i in range(0, len(choices), cols_count):
                    row_cells = choice_table.add_row().cells
                    for j in range(cols_count):
                        if i + j < len(choices):
                            c = choices[i+j]
                            row_cells[j].text = f"{c['label']}) {c['text']}"
                doc.add_paragraph() # Spacer after table

        elif item.item_type == 'SHORT_ANSWER':
            doc.add_paragraph("_________________________________________________")

        # Sorular arası boşluk
        doc.add_paragraph().paragraph_format.space_after = Pt(template.question_spacing)

    # 6. Cevap Anahtarı
    if with_answer_key:
        doc.add_page_break()
        doc.add_heading('Cevap Anahtarı', level=1)
        key_table = doc.add_table(rows=1, cols=2)
        key_table.style = 'Table Grid'
        key_table.rows[0].cells[0].text = "Soru No"
        key_table.rows[0].cells[1].text = "Doğru Cevap"
        
        for fi in form_items:
            row = key_table.add_row().cells
            row[0].text = str(fi.order)
            row[1].text = str(fi.item_instance.item.expected_answer or "-")

    # Çıktı
    target_stream = io.BytesIO()
    doc.save(target_stream)
    target_stream.seek(0)
    return target_stream
