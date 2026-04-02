# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**MaddeHavuzu** (Turkish for "Item Pool") is a Django-based exam question management and test creation system, built on top of NefOptik (an optical form grading system). The project manages question banks, test form creation, AI-assisted learning outcome mapping, and item analysis.

Primary language of the application UI and codebase comments is **Turkish**.

## Development Commands

### Setup
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in values
python manage.py migrate
python manage.py createsuperuser
```

### Run
```bash
python manage.py runserver
```

### Migrations
```bash
python manage.py makemigrations <app_name>
python manage.py migrate
```

### Testing
```bash
pytest                              # all tests
pytest itempool/tests/              # single module
pytest grading/tests/               # grading module only
pytest -k test_name                 # single test
```

### Internationalization
```bash
python manage.py makemessages -l tr
python manage.py compilemessages
```

## Architecture

### Two Django Apps

**`grading/`** — Inherited from NefOptik, preserved mostly intact:
- Parses TXT-format optical answer sheet files (`parsers/configurable.py`)
- Grades exams and computes statistics (Cronbach's α, KR-20, cheating detection)
- Key models: `UserProfile` (with roles), `FileFormatConfig`, `UploadSession`, `StudentResult`
- Custom auth backend: `ApprovedUserBackend` — users require admin approval before login

**`itempool/`** — New item pool system, all URLs under `/havuz/`:
- Item bank with versioning, forking, and audit logging
- Word document (.docx) import with draft/preview/commit workflow
- AI-powered learning outcome suggestions via Google Gemini
- Test form creation wizard (Blueprint and SpecificationTable-based)
- Item analysis metrics linked to grading upload sessions

### Key itempool Models

| Model | Purpose |
|-------|---------|
| `ItemPool` | Container for exam questions; has course, semester, level metadata |
| `Item` / `ItemChoice` | Central question repository; `item_type`: MCQ/TF/SHORT_ANSWER/OPEN; choices A–J (max 10); `max_choices` (2-10, default 4); `expected_answer`, `scoring_rubric` for non-MCQ types |
| `ItemInstance` | Pool-specific reference to an Item with learning outcome mapping; supports forking |
| `LearningOutcome` | Bloom's taxonomy-aligned objectives belonging to a pool |
| `PoolPermission` | Fine-grained per-user access control on pools |
| `ImportBatch` / `DraftItem` | Temporary storage during Word import before committing to Items |
| `OutcomeSuggestion` | AI suggestion (PENDING → ACCEPTED/REJECTED); never auto-applied |
| `TestForm` / `FormItem` | Exam instance composed of selected items with ordering and point values |
| `Blueprint` / `SpecificationTable` | Templates/rules for question distribution across learning outcomes |
| `ItemAnalysisResult` | Difficulty (p), discrimination (r), distractor efficiency, risk score 0-100 |
| `ItemAuditLog` | Immutable change log for all item modifications |
| `StudentGroup` | Course-semester student group; `get_applied_item_instance_ids()` returns IDs of all previously applied items for repeat prevention |
| `ExamApplication` | Links a `TestForm` to a `StudentGroup` with application date; unique_together `(test_form, group)` |
| `ExamTemplate` | Print layout config: page size, column count (1-3), fonts, margins, header/footer text with `{form_name}`, `{page}`, `{total_pages}` variables |

### Integration Between Apps

- `UploadSession` (grading) ↔ `ItemAnalysisResult` (itempool): links optical grading data to per-item metrics
- `StudentResult` (grading) ↔ `FormItem` (itempool): maps student answers to form questions
- `UploadSession.test_form` FK (nullable): links an optical reading session to a specific `TestForm` for outcome reporting
- Risk scoring thresholds: 0-30 green, 31-60 yellow, 61-100 red

### Services

- `itempool/services/llm_client.py` — `LLMClient` abstract base + `GeminiClient` implementation; uses `GEMINI_API_KEY` from env
- `itempool/services/import_docx.py` — Docx parsing: extract questions/choices → DraftItem → commit to Item
- `itempool/services/item_analysis.py` — Difficulty index, discrimination coefficient, distractor efficiency calculations
- `itempool/services/form_builder.py` / `form_generation.py` — Blueprint/specification-based item selection for TestForm
- `itempool/services/exam_pdf.py` — `generate_exam_pdf(test_form, template, with_answer_key=False) → bytes` via WeasyPrint
- `itempool/services/answer_key.py` — `generate_answer_key_from_form(tf) → str`; `get_outcome_performance(upload_session) → list[dict]`

### Seed Data

```bash
python manage.py seed_exam_templates   # creates 5 default ExamTemplate records
```

### Frontend Stack

- Bootstrap 5.3 + HTMX (served via CDN) for dynamic partial updates
- Django templates with Turkish UI text
- REST API endpoints under `/havuz/api/` (DRF, token + session auth, 50 items/page pagination)

## Environment Configuration

Key `.env` variables:
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL` or individual `DB_*` variables (defaults to SQLite in dev)
- `GEMINI_API_KEY`, `GEMINI_MODEL` (required for AI suggestion features)

## User Roles

Defined in `grading/models/user_profile.py`: `INSTRUCTOR`, `COORDINATOR`, `ASSISTANT`, `ADMIN`. All new users require admin approval (`UserStatus.APPROVED`) before they can log in.
