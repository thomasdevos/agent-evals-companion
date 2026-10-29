"""Draw the chapter 16 conversation figures from a results file. Standard library only."""
import argparse
import json
import sys
from pathlib import Path

PERSONAS = ('cooperative', 'literal', 'noisy', 'abandon', 'drift')
CANDIDATES = ('vague', 'specific')
FIELDS = ('persona', 'candidate', 'outcome', 'questions', 'useful', 'unnecessary')
FILL = {
    'completed': '#d9d9d9',
    'unknown': '#ffffff',
    'abandoned': '#bdbdbd',
    'failed': '#969696',
    'error': '#737373',
}


def esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def load_rows(data):
    if type(data) is not dict or type(data.get('rows')) is not list or not data['rows']:
        raise ValueError('results require a nonempty rows list')
    rows = []
    for row in data['rows']:
        if type(row) is not dict or any(key not in row for key in FIELDS):
            raise ValueError('row is missing figure fields')
        rows.append(row)
    return rows


def sort_key(row):
    persona, candidate = row['persona'], row['candidate']
    return (PERSONAS.index(persona) if persona in PERSONAS else len(PERSONAS), persona,
            CANDIDATES.index(candidate) if candidate in CANDIDATES else len(CANDIDATES), candidate)


def outcome_svg(rows):
    ordered = sorted(rows, key=sort_key)
    personas = []
    for row in ordered:
        if row['persona'] not in personas:
            personas.append(row['persona'])
    candidates = []
    for row in ordered:
        if row['candidate'] not in candidates:
            candidates.append(row['candidate'])
    completed = sum(row['outcome'] == 'completed' for row in ordered)
    questions = sum(row['questions'] for row in ordered)
    useful = sum(row['useful'] for row in ordered)
    unnecessary = sum(row['unnecessary'] for row in ordered)
    cell_w, cell_h = 170, 52
    left, top = 130, 78
    width = left + cell_w * len(candidates) + 24
    height = top + cell_h * len(personas) + 56
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="32" font-family="sans-serif" font-size="18" fill="#111111">Persona and agent outcomes</text>',
        f'<text x="24" y="54" font-family="sans-serif" font-size="12" fill="#333333">{completed} completed / {len(ordered)} attempted. {useful} useful replies / {questions} questions. Unnecessary questions: {unnecessary}.</text>',
    ]
    for index, candidate in enumerate(candidates):
        x = left + index * cell_w + cell_w / 2
        parts.append(f'<text x="{x}" y="74" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#111111">{esc(candidate)}</text>')
    lookup = {(row['persona'], row['candidate']): row for row in ordered}
    for r_index, persona in enumerate(personas):
        y = top + r_index * cell_h
        parts.append(f'<text x="24" y="{y + 30}" font-family="sans-serif" font-size="13" fill="#111111">{esc(persona)}</text>')
        for c_index, candidate in enumerate(candidates):
            row = lookup.get((persona, candidate))
            x = left + c_index * cell_w
            outcome = row['outcome'] if row else 'missing'
            fill = FILL.get(outcome, '#ffffff')
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 8}" fill="{fill}" stroke="#222222" '
                f'data-persona="{esc(persona)}" data-candidate="{esc(candidate)}" data-outcome="{esc(outcome)}"/>'
            )
            if row:
                parts.append(f'<text x="{x + 10}" y="{y + 22}" font-family="sans-serif" font-size="13" fill="#111111">{esc(outcome)}</text>')
                parts.append(
                    f'<text x="{x + 10}" y="{y + 38}" font-family="sans-serif" font-size="11" fill="#333333">'
                    f'questions {row["questions"]}, useful {row["useful"]}</text>'
                )
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def question_svg(rows):
    ordered = sorted(rows, key=sort_key)
    maximum = max(row['questions'] for row in ordered) or 1
    row_h = 28
    left, top, width = 180, 56, 720
    height = top + row_h * len(ordered) + 36
    scale = 460 / maximum
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="28" font-family="sans-serif" font-size="18" fill="#111111">Questions and useful replies</text>',
        '<text x="24" y="48" font-family="sans-serif" font-size="12" fill="#333333">Gray bars are questions. Black bars are useful replies.</text>',
    ]
    for index, row in enumerate(ordered):
        y = top + index * row_h
        label = f'{row["persona"]} / {row["candidate"]}'
        parts.append(f'<text x="16" y="{y + 16}" font-family="sans-serif" font-size="12" fill="#111111">{esc(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{row["questions"] * scale:.2f}" height="16" fill="#bdbdbd"/>')
        parts.append(f'<rect x="{left}" y="{y + 4}" width="{row["useful"] * scale:.2f}" height="16" fill="#222222"/>')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def write_figures(data, out):
    rows = load_rows(data)
    destination = Path(out)
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        'persona-agent-outcomes.svg': outcome_svg(rows),
        'question-use.svg': question_svg(rows),
    }
    for name, text in files.items():
        (destination / name).write_text(text)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.input).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print('cannot read results: ' + str(exc), file=sys.stderr)
        return 2
    try:
        write_figures(data, args.out)
    except ValueError as exc:
        print('cannot draw figures: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
