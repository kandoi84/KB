#!/usr/bin/env python3
"""Small, dependency-free checks for KB's documented Markdown conventions."""
from pathlib import Path
import re
from datetime import date
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"\n]*")?\)')
errors = []


def fail(path, message):
    errors.append(f'{path.relative_to(ROOT)}: {message}')


def local_target(page, target):
    target = target.strip('<>')
    if target.startswith('#') or urlsplit(target).scheme or target.startswith('//'):
        return None
    return (page.parent / unquote(target.split('#', 1)[0].split('?', 1)[0])).resolve()


pages = sorted(ROOT.rglob('*.md'))
for page in pages:
    content = page.read_text(encoding='utf-8')
    link_text = re.sub(r'```.*?```|`[^`\n]*`', '', content, flags=re.S)
    targets = [local_target(page, target) for target in LINK.findall(link_text)]
    for target in targets:
        if target is not None and not target.exists():
            fail(page, f'broken file link: {target}')
    relative = page.relative_to(ROOT)
    if relative.parts[0] != 'topics' or len(relative.parts) < 3:
        continue
    if '{{' in content or '}}' in content:
        fail(page, 'replace template placeholders')
    stage = relative.parts[2]
    if stage in {'notes', 'analysis', 'wiki'}:
        raw_root = ROOT / 'topics'
        evidence = [p for p in targets if p and p.is_file()
                    and p.is_relative_to(raw_root)
                    and len(p.relative_to(raw_root).parts) >= 3
                    and p.relative_to(raw_root).parts[1] == 'raw']
        if not evidence:
            fail(page, 'missing link to a raw source or source register')
    if relative.parts[1] in {'voice-practice', 'codex-work'} and stage == 'notes':
        session_fields = dict(re.findall(r'^(Session type|Session ID|Date|Source|Limitations):[ \t]*(.*)$', content, re.M))
        for field in ('Session type', 'Session ID', 'Date', 'Source', 'Limitations'):
            if not session_fields.get(field, '').strip():
                fail(page, f'missing session field: {field}')
        if session_fields.get('Session type') not in {'voice', 'codex', 'combined'}:
            fail(page, 'invalid session type')
        try:
            date.fromisoformat(session_fields.get('Date', ''))
        except ValueError:
            fail(page, 'session Date must be a valid YYYY-MM-DD date')
        if not LINK.search(session_fields.get('Source', '')):
            fail(page, 'session Source must include a Markdown link')
    if stage == 'wiki':
        fields = dict(re.findall(r'^(Status|Reviewer|Approval date|Evidence cutoff):\s*(.*?)\s*$', content, re.M))
        if fields.get('Status') not in {'draft', 'curated'}:
            fail(page, 'Status must be draft or curated')
        for field in ('Reviewer', 'Approval date', 'Evidence cutoff'):
            if not fields.get(field):
                fail(page, f'missing {field}')
        if fields.get('Status') == 'curated':
            for field in ('Reviewer', 'Approval date', 'Evidence cutoff'):
                if fields.get(field, '').lower() in {'', 'pending', 'unknown'}:
                    fail(page, f'curated page needs a completed {field}')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', fields.get('Approval date', '')):
                fail(page, 'approval date must use YYYY-MM-DD')

# Each source-register row must have a metadata block, including in templates.
for register in sorted(ROOT.rglob('SOURCES.md')):
    content = register.read_text(encoding='utf-8')
    ids = re.findall(r'^\| ([A-Z][A-Z0-9-]*[0-9]) \|', content, re.M)
    blocks = dict(re.findall(r'^### Metadata: (\S+)\n(.*?)(?=^### Metadata: |\Z)', content, re.M | re.S))
    if not ids:
        fail(register, 'no source rows with stable IDs')
    required = ('Source type', 'Quality grade', 'Quality reason', 'Source confidence',
                'Source confidence reason', 'Published date', 'Observed date', 'Data class',
                'Time-sensitive market/pricing', 'Freshness policy', 'Freshness status', 'Freshness as of')
    for source_id in ids:
        if source_id not in blocks:
            fail(register, f'missing metadata for {source_id}')
            continue
        fields = dict(re.findall(r'^([^:\n]+):[ \t]*(.*)$', blocks[source_id], re.M))
        for field in required:
            if not fields.get(field, '').strip():
                fail(register, f'{source_id}: missing {field}')
        for field in ('Quality grade', 'Source confidence'):
            if fields.get(field) not in {'high', 'medium', 'low', 'unknown'}:
                fail(register, f'{source_id}: invalid {field}')
        if fields.get('Time-sensitive market/pricing') not in {'yes', 'no', 'unknown'}:
            fail(register, f'{source_id}: invalid market/pricing flag')
        if fields.get('Freshness status') not in {'current', 'review-needed', 'stale', 'historical-only', 'unknown'}:
            fail(register, f'{source_id}: invalid freshness status')
        classes = {x.strip() for x in fields.get('Data class', '').split(',')}
        if not classes <= {'price-market', 'consensus', 'guidance', 'historical-reported', 'session-record', 'research-other'}:
            fail(register, f'{source_id}: invalid data class')
        if classes & {'price-market', 'consensus'} and fields.get('Time-sensitive market/pricing') != 'yes':
            fail(register, f'{source_id}: market/consensus sources need yes pricing flag')
        for field in ('Published date', 'Observed date', 'Freshness as of'):
            value = fields.get(field, '')
            if value == 'unknown':
                continue
            try:
                date.fromisoformat(value)
            except ValueError:
                fail(register, f'{source_id}: invalid {field} date')

for topic in sorted((ROOT / 'topics').iterdir()):
    if not topic.is_dir():
        continue
    for folder in ('raw', 'notes', 'analysis', 'wiki'):
        if not (topic / folder).is_dir():
            fail(topic, f'missing {folder}/ folder')
    for filename in ('README.md', 'raw/SOURCES.md', 'analysis/evidence-gaps.md'):
        if not (topic / filename).is_file():
            fail(topic, f'missing {filename}')

    gap = topic / 'analysis/evidence-gaps.md'
    if gap.is_file():
        gap_text = gap.read_text(encoding='utf-8')
        for field in ('Question', 'Supporting sources', 'Conflicting evidence', 'Missing data', 'Conclusion confidence', 'Freshness status', 'Next evidence'):
            if not re.search(r'^' + re.escape(field) + r':[ \t]*\S', gap_text, re.M):
                fail(gap, f'missing evidence/gap field: {field}')

if errors:
    print('\n'.join(errors))
    print(f'FAIL: {len(errors)} issue(s).')
    sys.exit(1)
print(f'PASS: checked {len(pages)} Markdown files. Human evidence review is still required.')
