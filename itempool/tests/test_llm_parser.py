import pytest
from itempool.services.llm_client import parse_json_from_llm

def test_parse_json_from_llm_standard():
    raw = '{"improved_stem": "Test", "improved_choices": []}'
    parsed = parse_json_from_llm(raw)
    assert parsed == {"improved_stem": "Test", "improved_choices": []}

def test_parse_json_from_llm_markdown_wrapper():
    raw = '```json\n{"outcome_id": 5, "score": 0.9, "reason": "Uygun"}\n```'
    parsed = parse_json_from_llm(raw)
    assert parsed == {"outcome_id": 5, "score": 0.9, "reason": "Uygun"}

def test_parse_json_from_llm_markdown_with_extra_text():
    raw = 'İşte sonucunuz:\n```json\n["Çeldirici 1", "Çeldirici 2"]\n```\nUmarım faydalı olur.'
    parsed = parse_json_from_llm(raw)
    assert parsed == ["Çeldirici 1", "Çeldirici 2"]

def test_parse_json_from_llm_invalid():
    raw = 'Hata: API Key bulunamadı'
    parsed = parse_json_from_llm(raw)
    assert parsed is None
