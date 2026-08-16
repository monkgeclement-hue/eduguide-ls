from docx import Document

doc = Document('EduGuide_LS_Master_Refinement_Pack.docx')
print("=== EduGuide Refinement Pack ===\n")
for para in doc.paragraphs:
    text = para.text.strip()
    if text:
        print(text)
