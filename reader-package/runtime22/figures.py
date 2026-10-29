"""Draw the chapter 22 monitoring figures. Standard library only."""
from pathlib import Path
import drift

SEED = 20261006


def clamped_z(z):
    """Figure 22.1 plots negative z scores as zero."""
    if z is None:
        return None
    if z < 0:
        return 0.0
    return z


def series(injected):
    return drift.analyse(drift.aggregate(drift.generate(SEED, injected)))


def esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def px(value):
    return format(value, '.2f')


def num(value):
    return format(value, '.4f')


def segments(points):
    groups = []
    current = []
    for point in points:
        if point[1] is None:
            if current:
                groups.append(current)
                current = []
        else:
            current.append(point)
    if current:
        groups.append(current)
    return groups


def frame(width, height, title, ylabel, caption):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="64" y="28" font-family="sans-serif" font-size="18" fill="#111111">{esc(title)}</text>',
        f'<text transform="rotate(-90 18 250)" x="18" y="250" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#111111">{esc(ylabel)}</text>',
        f'<text x="64" y="{height - 16}" font-family="sans-serif" font-size="12" fill="#333333">{esc(caption)}</text>',
    ]


def chart(title, ylabel, caption, prepared, vmax, threshold=None):
    width, height = 760, 460
    left, right, top, bottom = 72, 24, 58, 72
    plot_w = width - left - right
    plot_h = height - top - bottom
    vmax = vmax if vmax > 0 else 1
    parts = frame(width, height, title, ylabel, caption)
    axis_bottom = top + plot_h
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{axis_bottom}" stroke="#222222"/>')
    parts.append(f'<line x1="{left}" y1="{axis_bottom}" x2="{left + plot_w}" y2="{axis_bottom}" stroke="#222222"/>')
    parts.append(f'<text x="{left - 8}" y="{px(axis_bottom + 4)}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#111111">0</text>')
    parts.append(f'<text x="{left - 8}" y="{top + 4}" text-anchor="end" font-family="sans-serif" font-size="11" fill="#111111">{esc(num(vmax))}</text>')
    for day in (20, 40, 60, 79):
        x = left + (day - 20) / 59 * plot_w
        parts.append(f'<text x="{px(x)}" y="{axis_bottom + 18}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#111111">{day}</text>')
    parts.append(f'<text x="{left + plot_w / 2}" y="{axis_bottom + 36}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#111111">day</text>')
    if threshold is not None and 0 <= threshold <= vmax:
        y = top + (1 - threshold / vmax) * plot_h
        parts.append(f'<line x1="{left}" y1="{px(y)}" x2="{left + plot_w}" y2="{px(y)}" stroke="#666666" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="{left + 6}" y="{px(y - 4)}" font-family="sans-serif" font-size="11" fill="#333333">threshold {threshold:g}</text>')

    def xy(day, value):
        x = left + (day - 20) / 59 * plot_w
        y = None if value is None else top + (1 - value / vmax) * plot_h
        return x, y

    for name, rows, color, dash in prepared:
        mapped = [xy(row['day'], row['value']) for row in rows]
        for group in segments(mapped):
            points = ' '.join(px(x) + ',' + px(y) for x, y in group)
            extra = f' stroke-dasharray="{dash}"' if dash else ''
            parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.6"{extra} points="{points}"/>')
        for row, (x, y) in zip(rows, mapped):
            if y is None:
                continue
            raw = '' if row['raw'] is None else f' data-raw="{num(row["raw"])}"'
            parts.append(
                f'<circle cx="{px(x)}" cy="{px(y)}" r="2.4" fill="{color}" data-series="{esc(name)}" '
                f'data-day="{row["day"]}"{raw} data-z="{num(row["value"])}"/>'
            )
    parts.append('<text x="520" y="28" font-family="sans-serif" font-size="12" fill="#111111">injected</text>')
    parts.append('<line x1="490" y1="24" x2="514" y2="24" stroke="#111111" stroke-width="1.6"/>')
    parts.append('<text x="520" y="46" font-family="sans-serif" font-size="12" fill="#555555">null</text>')
    parts.append('<line x1="490" y1="42" x2="514" y2="42" stroke="#555555" stroke-width="1.6" stroke-dasharray="5 3"/>')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def z_rows(rows):
    return [dict(day=row['day'], value=clamped_z(row['z']), raw=row['z']) for row in rows]


def cusum_rows(rows):
    return [dict(day=row['day'], value=row['cusum'], raw=row['cusum']) for row in rows]


def write(root=None):
    root = Path(__file__).resolve().parent if root is None else Path(root)
    assets = root / 'assets'
    assets.mkdir(exist_ok=True)
    injected, null = series(True), series(False)
    z_prepared = (
        ('null', z_rows(null), '#555555', '5 3'),
        ('injected', z_rows(injected), '#111111', ''),
    )
    z_max = max(row['value'] or 0 for _, rows, _, _ in z_prepared for row in rows)
    z_svg = chart(
        'Figure 22.1',
        'z score (negative values clamped to 0)',
        'Seed 20261006. Baseline days 0-19 are omitted. Missing collection days plot no z score.',
        z_prepared,
        z_max * 1.1,
    )
    c_prepared = (
        ('null', cusum_rows(null), '#555555', '5 3'),
        ('injected', cusum_rows(injected), '#111111', ''),
    )
    c_max = max(row['value'] for _, rows, _, _ in c_prepared for row in rows)
    c_svg = chart(
        'CUSUM',
        'CUSUM',
        'Missing days hold the CUSUM state. The line shows the chapter cusum field. Threshold h = 5.',
        c_prepared,
        max(c_max, 5) * 1.1,
        threshold=5,
    )
    (assets / 'figure-22-1-z.svg').write_text(z_svg)
    (assets / 'cusum.svg').write_text(c_svg)


def main():
    write()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
