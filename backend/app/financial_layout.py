"""Read borderless financial rows using PDF word coordinates, without repairing digits."""

import re

from .financial_metrics import clean_label, row_metric, source_number


def financial_layout(page):
    words = page.get_text("words", sort=True)
    lines = []
    for word in sorted(words, key=lambda w: (w[1], w[0])):
        line = next((line for line in reversed(lines[-4:]) if abs(line[0][1] - word[1]) < 2), None)
        if line is None:
            lines.append([word])
        else:
            line.append(word)
    lines = [sorted(line, key=lambda w: w[0]) for line in lines]
    anchor = next(
        (line for line in lines if clean_label(" ".join(w[4] for w in line[:2])) == "total income"), None
    )
    if anchor is None:
        return None
    numeric = [w for w in anchor[2:] if source_number(w[4]) is not None]
    years = [w for w in words if re.fullmatch(r"20\d{2}", w[4]) and 0 < anchor[0][1] - w[1] < 150]
    if not numeric or not years:
        return None
    # Select the closest header line above the income row. Percentage columns have no year.
    header_y = max(w[1] for w in years)
    years = [w for w in years if abs(w[1] - header_y) < 2]
    bases = [w for w in words if w[4].lower() in {"standalone", "consolidated"} and 0 < header_y - w[1] < 180]
    if not bases:
        return None
    base_y = max(w[1] for w in bases)
    bases = [w for w in bases if abs(w[1] - base_y) < 2]
    columns = []
    for value in numeric:
        year = min(years, key=lambda w: abs(w[2] - value[2]))
        if abs(year[2] - value[2]) > 12:
            continue
        basis = min(bases, key=lambda w: abs((w[0] + w[2]) / 2 - (year[0] + year[2]) / 2))
        columns.append((value[2], year[4], basis[4].lower()))
    if len(columns) < 2 or len({c[0] for c in columns}) != len(columns):
        return None
    left = min(w[0] for w in numeric) - 20
    rows = [["Accounting basis", *[c[2] for c in columns]], ["Year ended March 31", *[c[1] for c in columns]]]
    for line in lines:
        if line[0][1] <= header_y:
            continue
        label = " ".join(w[4] for w in line if w[2] < left)
        if not row_metric([label])[0]:
            continue
        cells = [label]
        for edge, _, _ in columns:
            values = [w for w in line if abs(w[2] - edge) < 3 and source_number(w[4]) is not None]
            cells.append(values[0][4] if len(values) == 1 else "")
        rows.append(cells)
    return rows if len(rows) >= 5 else None
