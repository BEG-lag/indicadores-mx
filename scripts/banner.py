"""Generate assets/banner.svg from the dataset.

    uv run python scripts/banner.py

The line is the real FIX exchange rate (monthly last value, from the first DOF
publication in the data to the latest), and the ticker shows the latest value of
four series. The footer states the date the banner was generated from, so it never
claims more than it knows. The animation is disabled under prefers-reduced-motion.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from indicadores_mx import store
from indicadores_mx.catalog import SERIES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "banner.svg"


def monthly_last(observations: list[store.Obs]) -> list[tuple[str, Decimal]]:
    by_month: dict[str, Decimal] = {}
    for obs in observations:
        by_month[obs.key[:7]] = Decimal(obs.value)
    return sorted(by_month.items())


def fmt(value: str, decimals: int) -> str:
    return f"{Decimal(value):,.{decimals}f}"


def main() -> None:
    data = store.load_all()
    fix = monthly_last(data["fix"])
    total = sum(len(v) for v in data.values())
    as_of = max(o.key for o in data["fix"])
    first_year = fix[0][0][:4]

    x0, y0, w, h = 640, 92, 500, 190
    lo = min(v for _, v in fix)
    hi = max(v for _, v in fix)
    points = []
    for i, (_, value) in enumerate(fix):
        x = x0 + i / (len(fix) - 1) * w
        y = y0 + h - float((value - lo) / (hi - lo)) * h
        points.append(f"{x:.1f},{y:.1f}")
    path = "M" + " L".join(points)
    area = f"{path} L{x0 + w:.1f},{y0 + h} L{x0},{y0 + h} Z"
    last_x, last_y = points[-1].split(",")

    ticker = []
    labels = {"fix": "FIX", "udis": "UDI", "tiie-28": "TIIE 28", "inpc": "INPC"}
    decimals = {s.id: s.decimals for s in SERIES}
    for i, (sid, label) in enumerate(labels.items()):
        obs = data[sid][-1]
        suffix = "%" if sid.startswith("tiie") else ""
        x = x0 + i * 128
        ticker.append(
            f'<g class="tick" style="animation-delay:{1.2 + i * 0.15:.2f}s">'
            f'<text x="{x}" y="326" class="mono" font-size="11" fill="#969dab" letter-spacing="1.5">{label}</text>'
            f'<text x="{x}" y="350" class="mono" font-size="19" font-weight="700" fill="#eceee6">{fmt(obs.value, decimals[sid])}{suffix}</text>'
            f"</g>"
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400" width="1200" height="400" role="img" aria-labelledby="title desc">
  <title id="title">indicadores-mx</title>
  <desc id="desc">Open dataset and free static JSON and CSV API of Mexico's official economic indicators, each value traceable to its Diario Oficial de la Federación note. The line is the FIX exchange rate, monthly, from {first_year} to {as_of[:7]}. As of {as_of} the dataset holds {total:,} values.</desc>
  <defs>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M40 0H0V40" fill="none" stroke="#191d27" stroke-width="1"/>
    </pattern>
    <radialGradient id="glow" cx="0.8" cy="0.2" r="0.75">
      <stop offset="0" stop-color="#cfff45" stop-opacity="0.12"/>
      <stop offset="0.55" stop-color="#cfff45" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#cfff45" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#cfff45" stop-opacity="0"/>
    </linearGradient>
    <style>
      .mono {{ font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace; }}
      .serif {{ font-family: 'Cormorant Garamond', 'Iowan Old Style', Georgia, 'Times New Roman', serif; font-style: italic; }}
      .sans {{ font-family: Inter, ui-sans-serif, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
      .line {{ stroke-dasharray: 2600; stroke-dashoffset: 2600; animation: draw 2.4s cubic-bezier(.3,.7,.2,1) 0.2s forwards; }}
      .area {{ opacity: 0; animation: fade 1s ease 1.4s forwards; }}
      .tick {{ opacity: 0; animation: fade 0.6s ease forwards; }}
      .dot {{ animation: pulse 2.4s ease-in-out 2.6s infinite; }}
      @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
      @keyframes fade {{ to {{ opacity: 1; }} }}
      @keyframes pulse {{ 50% {{ opacity: 0.25; }} }}
      @media (prefers-reduced-motion: reduce) {{
        .line {{ animation: none; stroke-dashoffset: 0; }}
        .area, .tick {{ animation: none; opacity: 1; }}
        .dot {{ animation: none; }}
      }}
    </style>
  </defs>

  <rect width="1200" height="400" fill="#0a0c10"/>
  <rect width="1200" height="400" fill="url(#grid)" opacity="0.7"/>
  <rect width="1200" height="400" fill="url(#glow)"/>

  <g>
    <circle class="dot" cx="69" cy="75" r="5" fill="#cfff45"/>
    <text x="86" y="80" class="mono" font-size="13" letter-spacing="3" fill="#969dab">OPEN DATA · STATIC API · DOF</text>
    <text x="60" y="168" class="mono" font-size="66" font-weight="700" fill="#eceee6" letter-spacing="-1">indicadores<tspan fill="#cfff45">-mx</tspan></text>
    <text x="64" y="222" class="serif" font-size="31" fill="#eceee6">los indicadores oficiales de México,</text>
    <text x="64" y="257" class="serif" font-size="31" fill="#cfff45">trazables al Diario Oficial.</text>
    <text x="64" y="306" class="sans" font-size="15" fill="#969dab">FIX · UDIS · TIIE · INPC · inflación · salario mínimo · UMA</text>
    <text x="64" y="330" class="sans" font-size="15" fill="#969dab">JSON + CSV · JSON Schema · GitHub Pages · CC0</text>
    <text x="64" y="364" class="mono" font-size="13" fill="#ffb648">beg-lag.github.io/indicadores-mx</text>
  </g>

  <g>
    <text x="{x0}" y="70" class="mono" font-size="12" fill="#969dab">tipo de cambio FIX, pesos por dólar · {first_year} a {as_of[:4]}</text>
    <line x1="{x0}" x2="{x0 + w}" y1="{y0 + h + 0.5}" y2="{y0 + h + 0.5}" stroke="#232838"/>
    <path class="area" d="{area}" fill="url(#fill)"/>
    <path class="line" d="{path}" fill="none" stroke="#cfff45" stroke-width="2" stroke-linejoin="round"/>
    <circle class="dot" cx="{last_x}" cy="{last_y}" r="4" fill="#cfff45"/>
    {"".join(ticker)}
  </g>

  <text x="1140" y="384" text-anchor="end" class="mono" font-size="11" fill="#969dab" opacity="0.8">data as of {as_of} · {total:,} values · unofficial mirror</text>
</svg>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(fix)} months of FIX, {total} values)")


if __name__ == "__main__":
    main()
