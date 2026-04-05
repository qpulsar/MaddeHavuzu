import base64
import io
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.image import Image

class DocxHeaderService:
    """
    Word (.docx) dosyalarını WeasyPrint uyumlu temiz HTML'e dönüştüren servis.
    Özellikle sınav başlıklarındaki tabloları ve logoları yakalamak için optimize edilmiştir.
    """

    @staticmethod
    def convert_to_html(file_path):
        try:
            doc = Document(file_path)
        except Exception as e:
            return f"<p style='color:red'>Dosya okuma hatası: {str(e)}</p>"

        html_output = ['<div class="docx-header-container" style="width: 100%;">']
        
        # Word belgesindeki ana öğeleri sırayla işle (Paragraf ve Tablolar)
        for block in DocxHeaderService._iter_block_items(doc):
            if isinstance(block, str): # Paragraph text/html
                html_output.append(block)
            else: # Table object
                html_output.append(DocxHeaderService._table_to_html(block))

        html_output.append('</div>')
        return "".join(html_output)

    @staticmethod
    def _iter_block_items(parent):
        """Word belgesindeki öğeleri (paragraf/tablo) sırasıyla döner."""
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        from docx.document import Document as DocumentClass

        if isinstance(parent, DocumentClass):
            parent_elm = parent.element.body
        else:
            parent_elm = parent._element

        for child in parent_elm.iterchildren():
            if child.tag.endswith('p'):
                yield DocxHeaderService._paragraph_to_html(Paragraph(child, parent))
            elif child.tag.endswith('tbl'):
                yield Table(child, parent)

    @staticmethod
    def _paragraph_to_html(para):
        """Paragrafı HTML'e çevirir, içindeki resimleri Base64'e dönüştürür."""
        text_parts = []
        alignment = DocxHeaderService._get_alignment(para.alignment)
        
        # Inline öğeleri (run) işle
        for run in para.runs:
            # Resim kontrolü
            img_html = DocxHeaderService._extract_run_images(run)
            if img_html:
                text_parts.append(img_html)
            
            # Metin stili
            text = run.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if not text.strip() and not img_html: continue
            
            style = ""
            if run.bold: style += "font-weight: bold;"
            if run.italic: style += "font-style: italic;"
            if run.underline: style += "text-decoration: underline;"
            if run.font.size: style += f"font-size: {run.font.size.pt}pt;"
            
            if style:
                text_parts.append(f'<span style="{style}">{text}</span>')
            else:
                text_parts.append(text)

        content = "".join(text_parts)
        if not content.strip(): return ""
        
        return f'<p style="text-align: {alignment}; margin: 2pt 0;">{content}</p>'

    @staticmethod
    def _table_to_html(table):
        """Word tablosunu HTML <table>'e çevirir."""
        html = ['<table style="width: 100%; border-collapse: collapse; margin-bottom: 5pt;">']
        for row in table.rows:
            html.append('  <tr>')
            for cell in row.cells:
                # Hücre içindeki nesneleri işle (paragraf/iç tablo)
                cell_content = []
                for block in DocxHeaderService._iter_block_items(cell):
                    if isinstance(block, str):
                        cell_content.append(block)
                    else:
                        cell_content.append(DocxHeaderService._table_to_html(block))
                
                # Kenarlık ve padding ayarları
                html.append(f'    <td style="border: 0.5pt solid #eee; padding: 4pt; vertical-align: middle;">{"".join(cell_content)}</td>')
            html.append('  </tr>')
        html.append('</table>')
        return "".join(html)

    @staticmethod
    def _extract_run_images(run):
        """Run içindeki resimleri bulup base64 olarak döndürür."""
        try:
            # Drawing elementleri içindeki resimleri yakala
            inline_shapes = run._element.xpath('.//wp:inline | .//wp:anchor')
            if not inline_shapes: return ""
            
            images_html = []
            # Run'ın bağlı olduğu dökümanın part'larını kullanarak resim datasını al
            doc_part = run.part
            
            for shape in inline_shapes:
                blips = shape.xpath('.//a:blip')
                for blip in blips:
                    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    image_part = doc_part.related_parts[rId]
                    image_bytes = image_part.blob
                    ext = image_part.content_type.split('/')[-1]
                    b64 = base64.b64encode(image_bytes).decode('utf-8')
                    
                    # Genişlik ayarı (EMU biriminden px/pt'ye yaklaşık çevrim)
                    extent = shape.xpath('.//wp:extent')[0]
                    cx = int(extent.get('cx')) // 12700 # Approx conversion from EMU to pt
                    
                    images_html.append(f'<img src="data:image/{ext};base64,{b64}" style="max-height: 80pt; width: {cx}pt; vertical-align: middle;">')
            
            return "".join(images_html)
        except Exception:
            return ""

    @staticmethod
    def _get_alignment(docx_align):
        if docx_align == WD_ALIGN_PARAGRAPH.CENTER: return "center"
        if docx_align == WD_ALIGN_PARAGRAPH.RIGHT: return "right"
        if docx_align == WD_ALIGN_PARAGRAPH.JUSTIFY: return "justify"
        return "left"
