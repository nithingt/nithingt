# Storyboard pipeline

Panels are generated one at a time and composited into the page separately.
Models garble small caption text and drift panel borders, so page furniture —
frames, shot numbers, captions, the date/page slug — is laid out in HTML, not
drawn. A revision means re-rendering one panel, not the whole page.

```
blockout.py        composition: shot size, camera height, where bodies sit
   |               -> blockouts/shot_XX.svg
generate_panels.py prompt = camera + blocking + medium, with references
   |               -> panels/shot_XX.png
compose_page.py    panels + captions + form furniture
                   -> page.html
```

`compose_page.py` uses a finished render when one exists and falls back to the
blockout when it doesn't, so the page is viewable at every stage.

## Run it

```bash
python3 blockout.py                            # composition pass
python3 generate_panels.py --dry-run           # inspect prompts, no API calls

export GEMINI_API_KEY=...                      # or OPENAI_API_KEY
python3 generate_panels.py --provider gemini --compose \
        --ref refs/sable.png --ref refs/roon.png
python3 compose_page.py
```

| Flag | Effect |
| --- | --- |
| `--provider` | `gemini` (default) or `openai` |
| `--model` | override; defaults to `gemini-3-pro-image-preview` / `gpt-image-1` |
| `--shots 10 11` | re-render specific shots only |
| `--ref PATH` | character reference image, repeatable — this is what holds faces across panels |
| `--compose` | pass the blockout as a composition reference so framing survives |
| `--dry-run` | print assembled prompts and exit |

Stdlib only. `--compose` rasterizes the blockout via Playwright if it is
installed; without it the flag is skipped with a warning and prompts still carry
the camera description.

## Model choice

| Need | Reach for |
| --- | --- |
| Character consistency from reference images | Gemini 3 Pro Image |
| Conversational shot refinement | GPT-Image-1 |
| A locked house line style | Flux.1 dev + a style LoRA trained on ~20 of your own boards |
| Exact framing | Flux/SDXL + ControlNet scribble, fed the blockout SVG |
| Sketch feel, least control | Midjourney with `--sref` |

Hosted models refuse recognizable actors and trademarked designs; for a specific
likeness you need local weights and your own character LoRA.

## Prompting

Prompt the **cinematography**, not the scene. "Pepper is surprised" returns a
portrait; "low-angle medium close-up, 35mm, subject right of frame, eyeline off
lens" returns a board. `shots.json` is ordered that way on purpose — `camera`
leads, `action` follows, `style` is applied last and shared across every panel so
the page holds together.
