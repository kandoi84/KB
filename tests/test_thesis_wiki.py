import pytest
from pathlib import Path
from src.kb_runtime.thesis_wiki import ThesisWiki

def test_thesis_update(tmp_path):
    wiki = ThesisWiki(tmp_path)
    isin = "INE123456789"
    content = "Bullish on expansion."
    
    wiki.update_thesis(isin, content)
    
    thesis_file = wiki.get_thesis_file(isin)
    assert thesis_file.exists()
    assert content in thesis_file.read_text()

def test_add_note(tmp_path):
    wiki = ThesisWiki(tmp_path)
    isin = "INE123456789"
    note_id = "note_1"
    content = "Capex increasing."
    links = ["v1", "v2"]
    
    wiki.add_note(isin, note_id, content, links)
    
    note_path = tmp_path / "companies" / isin / "notes" / f"{note_id}.md"
    assert note_path.exists()
    text = note_path.read_text()
    assert content in text
    assert "v1" in text
    assert "v2" in text

def test_list_notes(tmp_path):
    wiki = ThesisWiki(tmp_path)
    isin = "INE123456789"
    
    wiki.add_note(isin, "n1", "content 1")
    wiki.add_note(isin, "n2", "content 2")
    
    notes = wiki.list_notes(isin)
    assert len(notes) == 2
    assert any("n1.md" in n.name for n in notes)
    assert any("n2.md" in n.name for n in notes)

def test_get_note_content(tmp_path):
    wiki = ThesisWiki(tmp_path)
    isin = "INE123456789"
    note_id = "n1"
    content = "secret info"
    
    wiki.add_note(isin, note_id, content)
    
    res = wiki.get_note_content(isin, note_id)
    assert content in res
