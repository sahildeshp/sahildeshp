"""Generate the GitHub profile README tiles as SVGs (light and dark) plus README.md.

Each SVG embeds only the glyphs it uses, so it renders in the site's typefaces
inside GitHub's <img> sandbox. Text is wrapped using real font metrics.
"""
import base64
import io
import math
import os
from xml.sax.saxutils import escape

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONTS = {
    "brico700": ("Brico", 700),
    "brico650": ("Brico", 650),
    "inst400": ("Inst", 400),
    "inst600": ("Inst", 600),
}
_tt = {k: TTFont(os.path.join(FONT_DIR, k + ".ttf")) for k in FONTS}

THEMES = {
    "light": dict(
        tile="#f3f5f8", stroke="#e2e6ec", ink="#10151c", text="#3a4352", muted="#5b667a",
        chip="#ffffff", chipstroke="#dde2e9", accent="#2647ff",
        role="#2647ff", rolefg="#ffffff", rolesoft="#dfe5ff",
        inv="#10151c", invfg="#ffffff", invmuted="#aeb7c6", invlink="#a9b8ff",
        dc="#cdd3dc", btn="#10151c", btnfg="#ffffff", btn2="#f3f5f8", btn2fg="#10151c", btn2stroke="#dde2e9",
    ),
    "dark": dict(
        tile="#151b23", stroke="#2a313c", ink="#f0f3f6", text="#c9d1d9", muted="#9198a1",
        chip="#212833", chipstroke="#2f3744", accent="#8ea2ff",
        role="#2647ff", rolefg="#ffffff", rolesoft="#dfe5ff",
        inv="#f0f3f6", invfg="#10151c", invmuted="#5b667a", invlink="#2647ff",
        dc="#3a4352", btn="#f0f3f6", btnfg="#10151c", btn2="#151b23", btn2fg="#f0f3f6", btn2stroke="#2f3744",
    ),
}

W = 840          # full tile width (README column at desktop)
HALF = 414       # half tile width; two halves sit in 420-wide canvases
GAP = 12         # horizontal gap between half tiles
VGAP = 8         # extra space under each row (the line box adds a few px more)
R = 24           # corner radius
PAD = 34


# ---------- text metrics and wrapping ----------

def width(text, font, size, spacing=0):
    tt = _tt[font]
    cmap = tt.getBestCmap()
    hmtx = tt["hmtx"]
    upm = tt["head"].unitsPerEm
    total = 0
    for ch in text:
        g = cmap.get(ord(ch))
        total += hmtx[g][0] if g else upm * 0.5
    return total * size / upm + spacing * len(text)


def wrap(words, font, size, maxw, spacing=0):
    """words: list of (word, color_key|None). Returns list of lines (lists of words)."""
    lines, cur = [], []
    for w in words:
        trial = " ".join(x[0] for x in cur + [w])
        if cur and width(trial, font, size, spacing) > maxw:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def plain(text):
    return [(w, None) for w in text.split()]


# ---------- SVG assembly ----------

class Svg:
    def __init__(self, w, h, theme, canvas=None, ox=0):
        self.w, self.h, self.t = w, h, THEMES[theme]
        self.cw, self.ch = canvas or (w, h)
        self.ox = ox
        self.parts, self.used = [], {}
        self.css = []

    def text(self, x, y, s, font, size, color, anchor="start", spacing=None, extra=""):
        self.used.setdefault(font, set()).update(s)
        fam, wt = FONTS[font]
        ls = f' letter-spacing="{spacing}"' if spacing is not None else ""
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-weight="{wt}" '
            f'font-size="{size}" fill="{color}" text-anchor="{anchor}"{ls}{extra}>{escape(s)}</text>'
        )

    def rich(self, x, y, line, font, size, default, spacing=None):
        """A line of (word, color_key) runs rendered with tspans."""
        s = " ".join(w for w, _ in line)
        self.used.setdefault(font, set()).update(s)
        fam, wt = FONTS[font]
        ls = f' letter-spacing="{spacing}"' if spacing is not None else ""
        spans = []
        for i, (word, ck) in enumerate(line):
            fill = self.t[ck] if ck else default
            sep = " " if i else ""
            spans.append(f'<tspan fill="{fill}">{escape(sep + word)}</tspan>')
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-weight="{wt}" '
            f'font-size="{size}"{ls} xml:space="preserve">{"".join(spans)}</text>'
        )

    def raw(self, s):
        self.parts.append(s)

    def _fontface(self, font, chars):
        opts = Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        opts.name_IDs = []
        opts.notdef_outline = True
        f = TTFont(os.path.join(FONT_DIR, font + ".ttf"))
        sub = Subsetter(options=opts)
        sub.populate(text="".join(sorted(chars)) + " ")
        sub.subset(f)
        f.flavor = "woff2"
        buf = io.BytesIO()
        f.save(buf)
        fam, wt = FONTS[font]
        b64 = base64.b64encode(buf.getvalue()).decode()
        return (f"@font-face{{font-family:{fam};font-weight:{wt};"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")

    def render(self, label):
        faces = "".join(self._fontface(f, c) for f, c in self.used.items())
        css = faces + "".join(self.css) + (
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.cw}" height="{self.ch}" '
            f'viewBox="0 0 {self.cw} {self.ch}" role="img" aria-label="{escape(label)}">'
            f'<style>{css}</style><g transform="translate({self.ox} 0)">{"".join(self.parts)}</g></svg>'
        )


def tile(svg, fill=None, stroke=True):
    t = svg.t
    fill = fill or t["tile"]
    st = f' stroke="{t["stroke"]}" stroke-width="1"' if stroke else ""
    svg.raw(f'<rect x="0.5" y="0.5" width="{svg.w-1}" height="{svg.h-1}" rx="{R}" fill="{fill}"{st}/>')


# ---------- tiles ----------

HEADLINE = [("I", None), ("design", None), ("and", None), ("validate", None), ("the", None),
            ("control", None), ("and", None), ("protection", None), ("systems", None),
            ("behind", None), ("HVDC", "accent"), ("transmission.", None)]


def hero(theme):
    size, lh = 50, 53
    lines = wrap(HEADLINE, "brico700", size, W - 2 * PAD, spacing=-1.4)
    h = PAD + 26 + 22 + 30 + len(lines) * lh + PAD - 4
    s = Svg(W, h, theme, canvas=(W, h + VGAP))
    t = s.t
    tile(s)
    s.text(PAD, PAD + 22, "Hi, I am Sahil.", "brico650", 21, t["ink"], spacing=-0.2)
    s.text(PAD, PAD + 46, "HVDC Control & Protection Engineer, Raleigh NC", "inst400", 16, t["muted"])
    y = PAD + 46 + 30 + size
    for line in lines:
        s.rich(PAD - 2, y, line, "brico700", size, t["ink"], spacing=-1.4)
        y += lh
    return s.render("I design and validate the control and protection systems behind HVDC transmission.")


def half(h, theme, side):
    return Svg(HALF, h, theme, canvas=(W // 2, h + VGAP), ox=0 if side == "left" else W // 2 - HALF)


def role(theme, h):
    s = half(h, theme, "left")
    t = s.t
    tile(s, fill=t["role"], stroke=False)
    s.css.append("@keyframes p{0%{r:5px;opacity:.8}80%,100%{r:15px;opacity:0}}"
                 ".ping{animation:p 2.4s cubic-bezier(0,0,.2,1) infinite}")
    s.raw(f'<circle cx="{PAD+5}" cy="{PAD+7}" r="5" fill="#7dffb0"/>'
          f'<circle class="ping" cx="{PAD+5}" cy="{PAD+7}" r="5" fill="#7dffb0"/>')
    s.text(PAD + 20, PAD + 12, "Current role", "inst600", 15, t["rolefg"])
    title = wrap(plain("HVDC Control & Protection Engineer"), "brico650", 31, HALF - 2 * PAD, spacing=-0.7)
    y = h - PAD - 66 - (len(title) - 1) * 34
    for line in title:
        s.rich(PAD, y, line, "brico650", 31, t["rolefg"], spacing=-0.7)
        y += 34
    s.text(PAD, h - PAD - 34, "Siemens Energy", "inst600", 16, t["rolefg"])
    s.text(PAD + width("Siemens Energy", "inst600", 16) + 12, h - PAD - 34,
           "Feb 2025 – Present", "inst400", 16, t["rolesoft"])
    s.text(PAD, h - PAD - 8, "Control and protection for HVDC links.", "inst400", 15, t["rolesoft"])
    return s.render("Current role: HVDC Control and Protection Engineer at Siemens Energy, since February 2025.")


PAST = [("SLB", "Control and Automation Engineer", "2023 – 2024"),
        ("Rivian Automotive", "Automation & Control Intern", "2022"),
        ("Honeywell International", "Electrical Controls Intern", "2022"),
        ("NC State, ADAC Lab", "Graduate Research Assistant", "2021")]


def before(theme, h):
    s = half(h, theme, "right")
    t = s.t
    tile(s)
    s.text(PAD, PAD + 12, "Before Siemens Energy", "inst600", 15, t["muted"])
    y = PAD + 46
    step = (h - PAD - y - 6) / (len(PAST) - 1) if len(PAST) > 1 else 0
    for i, (co, rl, yr) in enumerate(PAST):
        if i:
            s.raw(f'<path d="M{PAD} {y-27:.1f}H{HALF-PAD}" stroke="{t["stroke"]}" stroke-width="1"/>')
        s.text(PAD, y, co, "brico650", 17, t["ink"], spacing=-0.2)
        s.text(HALF - PAD, y, yr, "inst400", 14, t["muted"], anchor="end")
        s.text(PAD, y + 20, rl, "inst400", 14.5, t["text"])
        y += step
    return s.render("Before Siemens Energy: SLB, Rivian Automotive, Honeywell International, NC State ADAC Lab.")


def hvdc(theme):
    h = 272
    ox, oy = 40, 50
    s = Svg(W, h, theme, canvas=(W, h + VGAP))
    t = s.t
    tile(s)
    s.text(PAD, PAD + 12, "The system I work on", "inst600", 15, t["muted"])
    s.css.append("@keyframes f{to{stroke-dashoffset:-32}}"
                 ".fl{fill:none;stroke-width:2.5;stroke-linecap:round;stroke-dasharray:10 22;animation:f 1.6s linear infinite}"
                 ".rv{animation-direction:reverse}")
    ink, acc = t["ink"], t["accent"]
    wire = f'fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
    g = [f'<g transform="translate({ox} {oy})">',
         f'<path d="M264 114h232M264 146h232" stroke="{t["dc"]}" stroke-width="2" fill="none"/>',
         f'<path class="fl" stroke="{acc}" d="M264 114h232"/><path class="fl rv" stroke="{acc}" d="M264 146h232"/>',
         f'<g {wire}>'
         '<circle cx="46" cy="130" r="22"/><path d="M33 130c4-11 9-11 13 0s9 11 13 0"/><path d="M68 130h39"/>'
         '<circle cx="121" cy="130" r="14"/><circle cx="141" cy="130" r="14"/><path d="M155 130h45"/>'
         '<rect x="200" y="98" width="64" height="64" rx="6"/><path d="M200 162L264 98"/>'
         '<path d="M209 117c2-5 5-5 7 0s5 5 7 0"/><path d="M241 142h14M241 148h14"/>'
         '<rect x="496" y="98" width="64" height="64" rx="6"/><path d="M496 162L560 98"/>'
         '<path d="M505 114h14M505 120h14"/><path d="M537 145c2-5 5-5 7 0s5 5 7 0"/><path d="M560 130h45"/>'
         '<circle cx="619" cy="130" r="14"/><circle cx="639" cy="130" r="14"/><path d="M653 130h39"/>'
         '<circle cx="714" cy="130" r="22"/><path d="M701 130c4-11 9-11 13 0s9 11 13 0"/></g>',
         f'<path d="M232 56v42M528 56v42" stroke="{acc}" stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round" fill="none"/>',
         f'<rect x="150" y="20" width="164" height="36" rx="18" fill="{t["role"]}"/>',
         f'<rect x="446" y="20" width="164" height="36" rx="18" fill="{t["role"]}"/>', '</g>']
    s.raw("".join(g))
    for x in (232, 528):
        s.text(x + ox, oy + 43, "Control & protection", "inst600", 13.5, "#ffffff", anchor="middle")
    for x, y, lab in [(46, 182, "AC grid"), (232, 188, "Converter station"), (380, 188, "DC link"),
                      (528, 188, "Converter station"), (714, 182, "AC grid")]:
        s.text(x + ox, y + oy, lab, "inst400", 14, t["muted"], anchor="middle")
    s.text(282 + ox, 107 + oy, "+", "inst400", 14, t["muted"], anchor="middle")
    s.text(282 + ox, 164 + oy, "−", "inst400", 14, t["muted"], anchor="middle")
    return s.render("Simplified HVDC link: two AC grids joined by two converter stations and a DC link, "
                    "with a control and protection system on each converter station.")


def heading(theme, text):
    s = Svg(W, 64, theme)
    s.text(6, 46, text, "brico700", 32, s.t["ink"], spacing=-0.9)
    return s.render(text)


PROJECTS = [
    ("digital-twin", "Feb – Dec 2024", "Digital twin and control validation for drilling systems",
     "Simulink and Simscape model of Topdrive and Drawworks, with generated Beckhoff Structured Text validated on HIL.",
     ["Simulink", "Simscape", "HIL"], "https://sahildeshp.github.io/#projects"),
    ("jetbot", "Aug – Nov 2022", "Vision-based lane detection on NVIDIA JetBot",
     "ResNet-18 lane following with a digital PID controller, compared for stability and robustness.",
     ["ResNet-18", "PID", "JetBot"],
     "https://github.com/sahildeshp/Adaptive-Cruise-Control-and-Vision-based-Lane-Detection-of-NVIDIA-JetBot"),
    ("lyapunov", "Aug – Oct 2021", "Lyapunov-based nonlinear tracking control of a 2-link manipulator",
     "EMK, adaptive, and sliding-mode controllers in Simulink, compared on stability, control effort, and robustness.",
     ["MATLAB", "Simulink", "Nonlinear control"],
     "https://github.com/sahildeshp/Lyapunov-based-Non-Linear-Tracking-Control-of-a-2-link-Robotic-Manipulator"),
    ("terrain", "Jan – May 2021", "Terrain classification from IMU time series",
     "Conv1D, LSTM, and GRU models in Keras on accelerometer and gyroscope data, reaching 85% accuracy.",
     ["Keras", "LSTM", "Time series"],
     "https://github.com/sahildeshp/Terrain_Classification_from_Time_Series_Data"),
]


def project_layout(p):
    _, date, title, desc, tags, _ = p
    tl = wrap(plain(title), "brico650", 21, HALF - 2 * PAD - 44, spacing=-0.3)
    dl = wrap(plain(desc), "inst400", 15, HALF - 2 * PAD)
    h = PAD + 14 + 18 + len(tl) * 26 + 10 + len(dl) * 22 + 18 + 30 + PAD - 4
    return tl, dl, h


def project(theme, p, h, side):
    key, date, title, desc, tags, url = p
    tl, dl, _ = project_layout(p)
    s = half(h, theme, side)
    t = s.t
    tile(s)
    s.text(PAD, PAD + 12, date, "inst400", 14, t["muted"])
    y = PAD + 14 + 26
    for line in tl:
        s.rich(PAD, y, line, "brico650", 21, t["ink"], spacing=-0.3)
        y += 26
    y += 8
    for line in dl:
        s.rich(PAD, y, line, "inst400", 15, t["text"])
        y += 22
    # tags pinned to the bottom
    x, ty = PAD, h - PAD - 26
    for tag in tags:
        tw = width(tag, "inst600", 13) + 22
        s.raw(f'<rect x="{x}" y="{ty}" width="{tw:.1f}" height="28" rx="14" fill="{t["chip"]}" '
              f'stroke="{t["chipstroke"]}"/>')
        s.text(x + 11, ty + 18.5, tag, "inst600", 13, t["ink"])
        x += tw + 8
    # arrow badge, top right
    cx, cy = HALF - PAD - 14, PAD + 8
    s.raw(f'<circle cx="{cx}" cy="{cy}" r="18" fill="{t["chip"]}" stroke="{t["chipstroke"]}"/>'
          f'<path d="M{cx-4} {cy+4}l8-8M{cx-3} {cy-4}h7v7" fill="none" stroke="{t["ink"]}" '
          f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    return s.render(f"Project: {title}. {desc}")


SKILLS = [
    ("Control systems", ["MATLAB", "Simulink", "Stateflow", "PID", "Lyapunov methods", "SIL/HIL"]),
    ("PLC and automation", ["Beckhoff TwinCAT", "IEC 61131", "Rockwell Studio 5000", "LabVIEW", "EPLAN EEC"]),
    ("Power systems", ["HVDC", "IEC 61850", "Motor control", "VFDs"]),
    ("Industrial networks", ["Ethernet/IP", "Profibus", "Profinet", "MQTT", "OPC UA"]),
    ("Programming", ["Python", "Structured Text", "Ladder Logic", "PowerShell", "SQL"]),
    ("DevOps", ["Git", "GitLab CI/CD", "Azure DevOps"]),
]


def skills(theme):
    cols, gapx = 3, 26
    colw = (W - 2 * PAD - gapx * (cols - 1)) / cols
    layout = []
    for name, items in SKILLS:
        rows, x, row = [], 0, []
        for it in items:
            w = width(it, "inst600", 13.5) + 24
            if row and x + w > colw:
                rows.append(row)
                row, x = [], 0
            row.append((it, w))
            x += w + 7
        rows.append(row)
        layout.append((name, rows))
    block_h = lambda rows: 26 + len(rows) * 36
    row_heights = []
    for r in range(0, len(layout), cols):
        row_heights.append(max(block_h(rows) for _, rows in layout[r:r + cols]))
    h = PAD + 12 + 26 + sum(row_heights) + 20 * (len(row_heights) - 1) + PAD - 8
    s = Svg(W, h, theme, canvas=(W, h + VGAP))
    t = s.t
    tile(s)
    s.text(PAD, PAD + 12, "Skills", "inst600", 15, t["muted"])
    y0 = PAD + 12 + 30
    for i, (name, rows) in enumerate(layout):
        r, c = divmod(i, cols)
        x0 = PAD + c * (colw + gapx)
        y = y0 + sum(row_heights[:r]) + 20 * r
        s.text(x0, y + 12, name, "brico650", 16, t["ink"], spacing=-0.2)
        yy = y + 24
        for row in rows:
            x = x0
            for it, w in row:
                s.raw(f'<rect x="{x:.1f}" y="{yy}" width="{w:.1f}" height="29" rx="14.5" fill="{t["chip"]}" '
                      f'stroke="{t["chipstroke"]}"/>')
                s.text(x + 12, yy + 19.5, it, "inst600", 13.5, t["ink"])
                x += w + 7
            yy += 36
    return s.render("Skills: " + "; ".join(f"{n}: {', '.join(i)}" for n, i in SKILLS))


def contact(theme):
    h = 178
    s = Svg(W, h, theme, canvas=(W, h + VGAP))
    t = s.t
    tile(s, fill=t["inv"], stroke=False)
    s.text(PAD + 6, PAD + 14, "Contact", "inst600", 15, t["invmuted"])
    s.text(PAD + 6, PAD + 64, "Reach me at", "brico650", 38, t["invfg"], spacing=-1)
    email = "sahil.dshp@gmail.com"
    s.text(PAD + 6, PAD + 110, email, "brico650", 38, t["invlink"], spacing=-1)
    ew = width(email, "brico650", 38) - len(email) * 1
    s.raw(f'<path d="M{PAD+6} {PAD+120}h{ew:.1f}" stroke="{t["invlink"]}" stroke-opacity=".5" stroke-width="2"/>')
    return s.render("Contact: reach me at sahil.dshp@gmail.com")


BUTTONS = [("website", "Website", "primary"), ("resume", "Resume", "secondary"),
           ("linkedin", "LinkedIn", "secondary"), ("email", "Email", "secondary")]


def button(theme, label, kind):
    tw = width(label, "inst600", 15)
    w = int(tw + 2 * 22 + 22)
    h = 46
    s = Svg(w, h, theme, canvas=(w, h + VGAP))
    t = s.t
    bg, fg = (t["btn"], t["btnfg"]) if kind == "primary" else (t["btn2"], t["btn2fg"])
    st = "" if kind == "primary" else f' stroke="{t["btn2stroke"]}"'
    s.raw(f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="{(h-1)/2}" fill="{bg}"{st}/>')
    s.text(22, 29.5, label, "inst600", 15, fg)
    ax = 22 + tw + 10
    s.raw(f'<path d="M{ax:.1f} 27l7-7M{ax+1:.1f} 20h6v6" fill="none" stroke="{fg}" stroke-width="1.7" '
          f'stroke-linecap="round" stroke-linejoin="round"/>')
    return s.render(label)


# ---------- README ----------

BASE = "./assets"


def pic(name, alt, width_attr):
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{BASE}/{name}-dark.svg">'
            f'<img src="{BASE}/{name}-light.svg" alt="{escape(alt)}" width="{width_attr}"></picture>')


def link(url, inner):
    return f'<a href="{url}">{inner}</a>'


def main(out):
    os.makedirs(os.path.join(out, "assets"), exist_ok=True)

    def save(name, fn):
        for th in THEMES:
            with open(os.path.join(out, "assets", f"{name}-{th}.svg"), "w") as f:
                f.write(fn(th))

    save("hero", hero)
    rh = 300
    save("role", lambda th: role(th, rh))
    save("before", lambda th: before(th, rh))
    save("hvdc", hvdc)
    for key, label, kind in BUTTONS:
        save("btn-" + key, lambda th, label=label, kind=kind: button(th, label, kind))

    urls = {"website": "https://sahildeshp.github.io/",
            "resume": "https://sahildeshp.github.io/files/Resume%202025.pdf",
            "linkedin": "https://www.linkedin.com/in/sahildeshpande/",
            "email": "mailto:sahil.dshp@gmail.com"}
    full, half = "100%", "50%"
    rows = []
    rows.append(pic("hero", "I design and validate the control and protection systems behind HVDC transmission.", full))
    def btn_pct(label):  # same scale as the 840-wide tiles at any column width
        return f"{(int(width(label, 'inst600', 15) + 66)) / W * 100:.2f}%"
    rows.append(" ".join(link(urls[k], pic("btn-" + k, label, btn_pct(label)))
                         for k, label, _ in BUTTONS))
    rows.append(pic("role", "Current role: HVDC Control & Protection Engineer at Siemens Energy", half) +
                pic("before", "Before Siemens Energy: SLB, Rivian, Honeywell, NC State ADAC Lab", half))
    rows.append(pic("hvdc", "Simplified HVDC link with control and protection on each converter station", full))

    body = "\n<br>\n".join(rows)
    readme = (
        "<!-- Generated by tools/gen.py. Edit the content there and re-run it; do not hand-edit the SVGs. -->\n"
        f'<p align="center">\n{body}\n</p>\n'
    )
    with open(os.path.join(out, "README.md"), "w") as f:
        f.write(readme)


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
