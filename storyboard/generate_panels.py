"""Render storyboard panels from shots.json with a hosted image model.

Prompts are assembled cinematography-first (shot size, lens, camera height,
eyeline) because that is what separates a board from a portrait. Character
reference images are passed on every call so faces hold across panels, and the
blockout SVG can be passed as a composition reference so the model keeps the
framing you already decided.

    export GEMINI_API_KEY=...   # or OPENAI_API_KEY
    python3 generate_panels.py --provider gemini
    python3 generate_panels.py --provider openai --shots 10 11
    python3 generate_panels.py --provider gemini --ref refs/sable.png --compose

Stdlib only — no pip install required.
"""

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKOUTS = os.path.join(HERE, "blockouts")
PANELS = os.path.join(HERE, "panels")

DEFAULT_MODEL = {"gemini": "gemini-3-pro-image-preview", "openai": "gpt-image-1"}


def build_prompt(spec, shot):
    """Camera first, then blocking, then medium. Scene description comes last."""
    cast = ", ".join(f"{k.title()}: {v}" for k, v in spec["characters"].items())
    return (
        f"{shot['camera']}. "
        f"{shot['action']} "
        f"Cast — {cast}. "
        f"Rendered as: {spec['style']}. "
        f"Single panel, 16:9, no caption text or borders drawn in the image."
    )


def _b64_file(path):
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def _post(url, payload, headers, timeout=180):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise SystemExit(f"{exc.code} from {url.split('?')[0]}\n{detail}")


def call_gemini(prompt, model, refs, key):
    parts = [{"text": prompt}]
    for path in refs:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        parts.append({"inline_data": {"mime_type": mime, "data": _b64_file(path)}})
    data = _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"contents": [{"parts": parts}],
         "generationConfig": {"responseModalities": ["IMAGE"]}},
        {"x-goog-api-key": key},
    )
    for part in data["candidates"][0]["content"]["parts"]:
        blob = part.get("inlineData") or part.get("inline_data")
        if blob:
            return base64.b64decode(blob["data"])
    raise SystemExit("no image part in Gemini response")


def call_openai(prompt, model, refs, key):
    if refs:
        # Multipart edits endpoint — reference images condition the render.
        boundary = "----storyboard"
        chunks = []
        for name, value in (("model", model), ("prompt", prompt), ("size", "1536x1024")):
            chunks.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
                .encode()
            )
        for path in refs:
            mime = mimetypes.guess_type(path)[0] or "image/png"
            with open(path, "rb") as fh:
                blob = fh.read()
            chunks.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; '
                f'filename="{os.path.basename(path)}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
                + blob + b"\r\n"
            )
        chunks.append(f"--{boundary}--\r\n".encode())
        req = urllib.request.Request(
            "https://api.openai.com/v1/images/edits", data=b"".join(chunks),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=240) as resp:
            data = json.load(resp)
    else:
        data = _post(
            "https://api.openai.com/v1/images/generations",
            {"model": model, "prompt": prompt, "size": "1536x1024", "n": 1},
            {"Authorization": f"Bearer {key}"},
        )
    return base64.b64decode(data["data"][0]["b64_json"])


def rasterize(svg_path, png_path):
    """Blockout SVG -> PNG so it can ride along as a composition reference."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    exe = "/opt/pw-browsers/chromium"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=exe if os.path.exists(exe) else None)
        page = browser.new_page(viewport={"width": 960, "height": 540})
        page.goto("file://" + os.path.abspath(svg_path))
        page.screenshot(path=png_path)
        browser.close()
    return png_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=("gemini", "openai"), default="gemini")
    ap.add_argument("--model")
    ap.add_argument("--shots", nargs="*", help="shot ids; default all")
    ap.add_argument("--ref", action="append", default=[],
                    help="character reference image; repeatable")
    ap.add_argument("--compose", action="store_true",
                    help="also pass the blockout as a composition reference")
    ap.add_argument("--dry-run", action="store_true", help="print prompts, call nothing")
    args = ap.parse_args()

    spec = json.load(open(os.path.join(HERE, "shots.json")))
    shots = [s for s in spec["shots"]
             if not args.shots or s["id"] in args.shots]
    model = args.model or DEFAULT_MODEL[args.provider]

    if not args.dry_run:
        env = "GEMINI_API_KEY" if args.provider == "gemini" else "OPENAI_API_KEY"
        key = os.environ.get(env)
        if not key:
            raise SystemExit(f"{env} is not set")

    os.makedirs(PANELS, exist_ok=True)
    for shot in shots:
        prompt = build_prompt(spec, shot)
        if args.dry_run:
            print(f"\n=== SHOT {shot['id']} ===\n{prompt}")
            continue

        refs = list(args.ref)
        if args.compose:
            svg = os.path.join(BLOCKOUTS, f"shot_{shot['id']}.svg")
            png = os.path.join(PANELS, f"blockout_{shot['id']}.png")
            if rasterize(svg, png):
                refs.append(png)
            else:
                print("  (playwright missing — skipping composition reference)",
                      file=sys.stderr)

        fn = call_gemini if args.provider == "gemini" else call_openai
        print(f"shot {shot['id']}: rendering via {args.provider}/{model} ...")
        out = os.path.join(PANELS, f"shot_{shot['id']}.png")
        with open(out, "wb") as fh:
            fh.write(fn(prompt, model, refs, key))
        print("  ->", os.path.relpath(out, HERE))


if __name__ == "__main__":
    main()
