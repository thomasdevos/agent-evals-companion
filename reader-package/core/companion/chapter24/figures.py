"""Draw the chapter 24 suite cost frontier. Standard library only."""
from pathlib import Path
from chapter24.programme import run

ROOT = Path(__file__).resolve().parents[1]


def esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def cents(row):
    return (row['request_cents'] + row['labelling_cents']
            + row['investigation_cents'] + row['infrastructure_cents'])


def order_of(report):
    order = list(report['selected']) + list(report['suite_health']['lost_cases'])
    direct = {row['task_id'] for row in report['baselines']['direct']['cost_rows']}
    if set(order) != direct or len(order) != len(direct):
        raise ValueError('suite order does not match the direct cost rows')
    return order


def cumulative(report, label, order):
    by = {row['task_id']: row for row in report['baselines'][label]['cost_rows']}
    total = 0
    points = []
    for index, case_id in enumerate(order, 1):
        total += cents(by[case_id])
        points.append((index, total))
    return points


def frontier_svg(report):
    order = order_of(report)
    frequent = len(report['selected'])
    curves = {label: cumulative(report, label, order) for label in ('direct', 'bounded-retry')}
    full = {label: report['baselines'][label]['account']['scenario_total_cents'] for label in curves}
    passes = {label: report['baselines'][label]['account']['scorecard']['passed'] for label in curves}
    requests = {label: report['baselines'][label]['ledger']['request_attempts'] for label in curves}
    if curves['direct'][-1][1] != full['direct'] or curves['bounded-retry'][-1][1] != full['bounded-retry']:
        raise ValueError('cumulative cents do not match the scenario total')
    width, height = 760, 520
    left, right, top, bottom = 72, 28, 132, 64
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = len(order)
    ymax = max(full.values()) * 1.08
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="28" font-family="sans-serif" font-size="18" fill="#111111">Figure 24.1. Suite cost frontier</text>',
        '<text x="24" y="50" font-family="sans-serif" font-size="12" fill="#333333">Hypothetical cents versus cases retained. The eligible frequent suite is built first.</text>',
        f'<text x="24" y="70" font-family="sans-serif" font-size="12" fill="#333333">Direct, frequent suite: {curves["direct"][frequent - 1][1]} cents. Direct, full suite: {full["direct"]} cents, {passes["direct"]} passes, {requests["direct"]} requests.</text>',
        f'<text x="24" y="88" font-family="sans-serif" font-size="12" fill="#333333">Bounded retry, frequent suite: {curves["bounded-retry"][frequent - 1][1]} cents. Bounded retry, full suite: {full["bounded-retry"]} cents, {passes["bounded-retry"]} passes, {requests["bounded-retry"]} requests.</text>',
        '<text x="24" y="108" font-family="sans-serif" font-size="12" fill="#333333">Direct sends fewer requests. Its total is higher because unsuccessful trials add investigation cents.</text>',
    ]
    axis_bottom = top + plot_h
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{axis_bottom}" stroke="#222222"/>')
    parts.append(f'<line x1="{left}" y1="{axis_bottom}" x2="{left + plot_w}" y2="{axis_bottom}" stroke="#222222"/>')
    parts.append(f'<text transform="rotate(-90 18 300)" x="18" y="300" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#111111">hypothetical cents</text>')
    parts.append(f'<text x="{left + plot_w / 2:.0f}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#111111">cases retained, frequent suite first</text>')
    parts.append(f'<text x="{left - 8}" y="{axis_bottom + 4}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#111111">0</text>')
    parts.append(f'<text x="{left - 8}" y="{top + 4}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#111111">{full["direct"]}</text>')
    mark = left + (frequent - 1) / (n - 1) * plot_w
    parts.append(f'<line x1="{mark:.2f}" y1="{top}" x2="{mark:.2f}" y2="{axis_bottom}" stroke="#888888" stroke-dasharray="3 3"/>')
    parts.append(f'<text x="{mark + 4:.2f}" y="{top + 14}" font-family="sans-serif" font-size="11" fill="#333333">eligible frequent suite</text>')

    def point(index, value):
        x = left + (index - 1) / (n - 1) * plot_w
        y = top + (1 - value / ymax) * plot_h
        return x, y

    styles = (('direct', '#111111', ''), ('bounded-retry', '#555555', '6 3'))
    for label, color, dash in styles:
        coords = [point(index, value) for index, value in curves[label]]
        rendered = ' '.join(f'{x:.2f},{y:.2f}' for x, y in coords)
        extra = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.8"{extra} points="{rendered}"/>')
        for suite, index in (('frequent', frequent), ('full', n)):
            value = curves[label][index - 1][1]
            x, y = point(index, value)
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="{color}" data-policy="{label}" '
                f'data-suite="{suite}" data-cases="{index}" data-cents="{value}"/>'
            )
    parts.append('<text x="560" y="28" font-family="sans-serif" font-size="12" fill="#111111">direct</text>')
    parts.append('<line x1="528" y1="24" x2="554" y2="24" stroke="#111111" stroke-width="1.8"/>')
    parts.append('<text x="560" y="46" font-family="sans-serif" font-size="12" fill="#555555">bounded retry</text>')
    parts.append('<line x1="528" y1="42" x2="554" y2="42" stroke="#555555" stroke-width="1.8" stroke-dasharray="6 3"/>')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def write(report, directory=None):
    destination = ROOT / 'assets' / 'chapter-24' if directory is None else Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    text = frontier_svg(report)
    (destination / 'frontier.svg').write_text(text)
    return text


def main():
    write(run('repair'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
