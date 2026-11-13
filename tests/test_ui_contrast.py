import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _luminance(color):
    value = color.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return sum(
        channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722))
    )


def _contrast(foreground, background):
    light, dark = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_small_text_tokens_meet_wcag_aa_on_documented_surfaces():
    css = (ROOT / "apps/clinician-web/src/style.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = {}
    for selector_list, body in re.findall(r"([^{}]+)\{([^{}]+)\}", css):
        for selector in selector_list.split(","):
            rules[selector.strip()] = body

    surfaces = {
        ".eyebrow": "#ffffff",
        ".timeline p": "#ffffff",
        ".severity": "#f8f3e2",
        ".severity.critical": "#faeae3",
        ".pill": "#eff4f0",
        ".hash": "#ffffff",
        ".callout": "#ffffff",
        ".timestamp": "#ffffff",
        ".local-badge": "#f6f9f2",
        ".status-badge": "#faf8ec",
        ".status-badge.approved": "#edf7ee",
        ".verified p": "#ffffff",
        ".finding p": "#ffffff",
        ".author-label": "#ffffff",
        ".page-heading p": "#ffffff",
        ".login-copy>p": "#ffffff",
        ".count.blocked": "#fbede4",
        ".count.clear": "#eaf4e2",
        ".notice": "#eff7e9",
        ".danger-button": "#ffffff",
    }
    failures = []
    for selector, background in surfaces.items():
        body = rules.get(selector)
        color = re.search(r"(?<!-)color:(#[0-9a-fA-F]{6})", body or "")
        if not color:
            failures.append(
                f"{selector}: missing explicit accessible foreground override"
            )
            continue
        ratio = _contrast(color.group(1), background)
        if ratio < 4.5:
            failures.append(f"{selector}: contrast {ratio:.2f}:1 is below 4.5:1")

    muted = re.search(r"--muted:(#[0-9a-fA-F]{6})", css)
    assert muted and _contrast(muted.group(1), "#ffffff") >= 4.5
    assert not failures, "\n".join(failures)
