"""
Sihirbaz adımları (kaynak: omr_analysis/ui_helpers.py STEPS).

View'lar `wizard_context(test_id, step)` sonucunu şablon bağlamına ekler;
`optik/_stepper.html` ve `optik/_wizard_nav.html` bunu çizer.
"""
from django.urls import reverse

# (etiket, url adı)
STEPS = [
    ("Test Bilgileri", "optik:test_edit"),
    ("Form Yükleme", "optik:upload_forms"),
    ("Madde Bilgileri", "optik:answer_key"),
    ("Kayıt Listesi", "optik:records"),
    ("Puanlama", "optik:scoring"),
]


def wizard_context(test_id: str, step: int) -> dict:
    """step: 1..5 (etkin adım)."""
    steps = []
    for i, (label, url_name) in enumerate(STEPS, start=1):
        steps.append({
            'number': i,
            'label': label,
            'url': reverse(url_name, args=[test_id]),
            'state': 'done' if i < step else ('active' if i == step else 'todo'),
        })
    prev_step = steps[step - 2] if step > 1 else None
    next_step = steps[step] if step < len(steps) else None
    return {'wizard_steps': steps, 'wizard_step': step,
            'wizard_prev': prev_step, 'wizard_next': next_step}
