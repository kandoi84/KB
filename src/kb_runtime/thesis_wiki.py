"""Thesis Wiki for the Live KB.

Manages per-company markdown files that track the analyst's thesis,
linking qualitative notes to specific versions of structured and vector data.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

class ThesisWiki:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.wiki_dir = root_dir / "companies"
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

    def _get_company_dir(self, isin: str) -> Path:
        company_dir = self.wiki_dir / isin
        company_dir.mkdir(parents=True, exist_ok=True)
        return company_dir

    def get_thesis_file(self, isin: str) -> Path:
        return self._get_company_dir(isin) / "thesis.md"

    def update_thesis(self, isin: str, content: str, author: str = "Analyst"):
        """Update the main thesis file with a timestamped entry."""
        file_path = self.get_thesis_file(isin)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = f"\n\n## Update: {timestamp}\n**Author**: {author}\n\n{content}\n"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def add_note(self, isin: str, note_id: str, content: str, links: List[str] = None):
        """
        Add a dated research note.
        Links can be version_ids from the storage layer.
        """
        notes_dir = self._get_company_dir(isin) / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        
        note_path = notes_dir / f"{note_id}.md"
        
        # Header with metadata
        header = f"--- \n- isin: {isin}\n- date: {datetime.now().isoformat()}\n- links: {json.dumps(links or [])}\n---\n\n"
        
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(header + content)

    def list_notes(self, isin: str) -> List[Path]:
        notes_dir = self._get_company_dir(isin) / "notes"
        if not notes_dir.exists():
            return []
        return sorted(notes_dir.glob("*.md"), reverse=True)

    def get_note_content(self, isin: str, note_id: str) -> str:
        note_path = self._get_company_dir(isin) / "notes" / f"{note_id}.md"
        if not note_path.exists():
            raise FileNotFoundError(f"Note {note_id} not found for {isin}")
        return note_path.read_text(encoding="utf-8")
