"""Composite finished panels into a storyboard page.

Caption text, shot numbers, and page furniture are laid out here rather than
drawn by the image model — models garble small text and drift panel borders,
and a revision should mean re-rendering one panel, not the whole page.

Uses panels/shot_XX.png when it exists, otherwise falls back to the blockout.

    python3 compose_page.py            # -> page.html
"""

import base64
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "page.html")

FONTS = ("https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800"
         "&family=Barlow:wght@400;500&family=Caveat:wght@600"
         "&family=IBM+Plex+Mono:wght@400;500&display=swap")

CSS = """
:root {
  --paper: #f4f2ee;  --ink: #14161a;   --caption: #3d4046;
  --rule: #c9c4ba;   --pencil: #2f3238; --surround: #e9e6df;
  --chrome: #55585f; --sheet-shadow: rgba(20, 22, 26, .18);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --surround: #212429; --chrome: #9aa0a8; --sheet-shadow: rgba(0, 0, 0, .55);
  }
}
:root[data-theme="dark"] {
  --surround: #212429; --chrome: #9aa0a8; --sheet-shadow: rgba(0, 0, 0, .55);
}

body { background: var(--surround); padding: 32px 16px 64px;
       font-family: Barlow, system-ui, sans-serif; }

.sheet {
  max-width: 860px; margin: 0 auto; background: var(--paper); color: var(--ink);
  padding: 40px 46px 52px; box-shadow: 0 18px 44px var(--sheet-shadow);
}

.masthead { display: flex; align-items: flex-start; justify-content: space-between;
            gap: 24px; }
.masthead h1 { font-family: Archivo, system-ui, sans-serif; font-weight: 800;
               font-size: 27px; letter-spacing: -.01em; margin: 0;
               text-wrap: balance; }
.masthead h1 em { font-style: normal; font-weight: 500; }
.slug { display: flex; gap: 10px; flex: none; }
.slug div { border: 2px solid var(--ink); min-width: 84px; padding: 3px 8px 12px; }
.slug span { font-family: Archivo, system-ui, sans-serif; font-size: 8.5px;
             font-weight: 700; letter-spacing: .1em; }
.slug b { font-family: Caveat, cursive; font-weight: 600; font-size: 22px;
          display: block; line-height: 1; margin-top: 2px; }
.masthead-rule { border: 0; border-top: 1px solid var(--rule); margin: 18px 0 0; }

.board { display: flex; flex-direction: column; gap: 34px; margin-top: 30px; }
.shot { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 18px;
        align-items: start; }
.tag { font-family: Caveat, cursive; font-weight: 600; font-size: 25px;
       color: var(--pencil); padding-top: 4px; line-height: 1.1; }

.frame { border: 4px solid var(--ink); background: var(--paper); overflow: hidden;
         line-height: 0; }
.frame svg, .frame img { width: 100%; height: auto; display: block; }

.caption { font-size: 14.5px; line-height: 1.45; color: var(--caption);
           margin: 9px 0 0; max-width: 62ch; }
.caption strong { color: var(--ink); font-weight: 500; }
.data { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10.5px;
        letter-spacing: .01em; color: var(--chrome); margin: 6px 0 0;
        overflow-x: auto; white-space: nowrap; padding-bottom: 2px; }
.data i { font-style: normal; color: var(--rule); padding: 0 6px; }

.footer { display: flex; justify-content: space-between; gap: 16px;
          margin-top: 40px; padding-top: 12px; border-top: 1px solid var(--rule);
          font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 10px;
          color: var(--chrome); }

@media (max-width: 620px) {
  .sheet { padding: 26px 20px 34px; }
  .shot { grid-template-columns: 1fr; gap: 6px; }
  .tag { padding-top: 0; }
}
"""


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def panel_markup(shot_id):
    """Finished render if we have one, blockout if we don't."""
    png = os.path.join(HERE, "panels", f"shot_{shot_id}.png")
    if os.path.exists(png):
        with open(png, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" alt="Shot {shot_id}">', "render"
    svg = os.path.join(HERE, "blockouts", f"shot_{shot_id}.svg")
    with open(svg) as fh:
        return fh.read().split("?>")[-1].strip(), "blockout"


def main():
    spec = json.load(open(os.path.join(HERE, "shots.json")))
    rows, sources = [], []

    for shot in spec["shots"]:
        art, source = panel_markup(shot["id"])
        sources.append(source)
        lens, *rest = [p.strip() for p in shot["camera"].split(",")]
        height = next((p for p in rest if "camera" in p or "angle" in p), rest[0])
        rows.append(
            f'      <div class="shot">\n'
            f'        <div class="tag">{esc(shot["label"])}</div>\n'
            f'        <div>\n'
            f'          <div class="frame">{art}</div>\n'
            f'          <p class="caption">{esc(shot["caption"])}</p>\n'
            f'          <p class="data">{esc(lens.upper())}<i>/</i>{esc(height)}'
            f'<i>/</i>16:9<i>/</i>{source}</p>\n'
            f'        </div>\n      </div>'
        )

    counts = f'{sources.count("render")} rendered, {sources.count("blockout")} blockout'
    html = f"""<title>Nightshift Page 5</title>
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}</style>

<div class="sheet">
  <header class="masthead">
    <h1>&ldquo;{esc(spec["production"])}&rdquo; <em>Storyboards</em></h1>
    <div class="slug">
      <div><span>DATE</span><b>&mdash;</b></div>
      <div><span>PAGE</span><b>{spec["page"]}</b></div>
    </div>
  </header>
  <hr class="masthead-rule">

  <main class="board">
{chr(10).join(rows)}
  </main>

  <footer class="footer">
    <span>SEQ 02 &middot; SHOTS {spec["shots"][0]["id"]}&ndash;{spec["shots"][-1]["id"]}</span>
    <span>{counts}</span>
  </footer>
</div>
"""
    with open(PAGE, "w") as fh:
        fh.write(html)
    print(f"wrote page.html ({counts})")


if __name__ == "__main__":
    main()
