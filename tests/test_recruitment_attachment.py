import io, zipfile
from services.mail_attachment_processor import classify_attachment, _docx_text

def test_offer_attachment_classification():
    assert classify_attachment('Offer_Letter.pdf') == 'OFFER_LETTER'
    assert classify_attachment('salary_structure.pdf') == 'COMPENSATION_BREAKUP'

def test_docx_text_extraction():
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('word/document.xml','<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>Joining date confirmed</w:t></w:r></w:p></w:body></w:document>')
    assert 'Joining date confirmed' in _docx_text(output.getvalue())
