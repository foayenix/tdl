"""The design contract, made executable.

DESIGN.md §1 is the token table and it wins over everything except the
artboards. §8 says plainly: **do not derive a colour** — no opacity tricks, no
`lighten()`, no computed dark theme. Every value is in DESIGN.md because it was
chosen.

That is only true if something checks it. These tests read `DESIGN.md` and
`src/styles/tokens.css` and compare them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DESIGN = REPO / "DESIGN.md"
TOKENS = REPO / "src" / "styles" / "tokens.css"

HEX = re.compile(r"#[0-9a-fA-F]{6}\b")

# DESIGN.md §1's table: | `token` | `#LIGHT` | `#DARK` | for |
TOKEN_ROW = re.compile(
    r"^\|\s*`([a-z0-9-]+)`\s*\|\s*`(#[0-9A-Fa-f]{6})`\s*\|\s*`(#[0-9A-Fa-f]{6})`\s*\|",
    re.MULTILINE,
)


@pytest.fixture(scope="module")
def design() -> str:
    return DESIGN.read_text()


@pytest.fixture(scope="module")
def tokens() -> str:
    return TOKENS.read_text()


@pytest.fixture(scope="module")
def light_block(tokens: str) -> str:
    start = tokens.index(":root {")
    return tokens[start : tokens.index(":root[data-theme=\"dark\"]")]


@pytest.fixture(scope="module")
def dark_block(tokens: str) -> str:
    return tokens[tokens.index(':root[data-theme="dark"]') :]


def without_comments(css: str) -> str:
    """Strip /* … */ so a comment saying "no box-shadows" is not a box-shadow."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def declared(block: str, token: str) -> str | None:
    found = re.search(rf"--{re.escape(token)}:\s*([^;]+);", block)
    return None if found is None else found.group(1).strip()


def test_the_token_table_was_found(design):
    rows = TOKEN_ROW.findall(design)
    assert len(rows) >= 20, "DESIGN.md §1's token table did not parse"


@pytest.mark.parametrize(
    ("token", "light", "dark"),
    TOKEN_ROW.findall(DESIGN.read_text()),
    ids=lambda value: value if value.startswith(("#", "-")) is False else value,
)
def test_every_token_in_design_md_is_declared_with_the_value_it_states(
    token, light, dark, light_block, dark_block
):
    assert declared(light_block, token) == light.lower(), f"{token} light"
    assert declared(dark_block, token) == dark.lower(), f"{token} dark"


def test_no_colour_in_the_stylesheet_was_invented(design, tokens):
    """Every hex in tokens.css must appear in DESIGN.md. This is the guardrail."""
    in_design = {value.lower() for value in HEX.findall(design)}
    in_css = {value.lower() for value in HEX.findall(tokens)}

    invented = in_css - in_design
    assert not invented, (
        "these colours are in tokens.css but not in DESIGN.md — either they were"
        f" derived, or DESIGN.md needs updating first: {sorted(invented)}"
    )


def test_the_dark_theme_is_authored_not_computed(light_block, dark_block):
    """Both themes are authored. Never generate one from the other."""
    for function in ("lighten(", "darken(", "color-mix(", "filter:", "invert("):
        assert function not in light_block
        assert function not in dark_block


def test_the_dark_theme_is_rebuilt_against_its_own_ground(dark_block):
    assert declared(dark_block, "ground") == "#0f1412"


def test_the_unsourced_row_tint_is_present_in_both_themes(light_block, dark_block):
    assert declared(light_block, "warn-row") == "#fdf6ec"
    assert declared(dark_block, "warn-row") == "#1f1a12"


class TestTheEvidenceRamp:
    """Six levels on a four-step ramp, polarity flipping at step 3."""

    @pytest.mark.parametrize("step", range(4))
    def test_every_step_is_declared_in_both_themes(self, step, light_block, dark_block):
        for part in ("bg", "fg", "ring"):
            assert declared(light_block, f"ev{step}-{part}") is not None
            assert declared(dark_block, f"ev{step}-{part}") is not None

    def test_the_polarity_flips_at_step_three(self, light_block, dark_block):
        assert declared(light_block, "ev3-bg") == "#14705b"
        assert declared(light_block, "ev3-fg") == "#ffffff"
        assert declared(dark_block, "ev3-bg") == "#6fd9b7"
        assert declared(dark_block, "ev3-fg") == "#08150f"


class TestTheRadiusScale:
    def test_only_the_five_chosen_radii_exist(self, tokens):
        """1 was added in session 16 — the artboards draw the unsourced mark at
        radius 1, and DESIGN.md §3 now lists it. Nothing else uses it."""
        radii = set(re.findall(r"--radius-[a-z]+:\s*(\d+)px", tokens))
        assert radii == {"1", "2", "3", "4", "5"}


class TestSpacing:
    def test_the_scale_is_the_one_design_md_lists(self, tokens):
        steps = sorted(int(v) for v in re.findall(r"--space-(\d+):", tokens))
        assert steps == [2, 4, 6, 7, 8, 12, 14, 16, 18, 20, 28, 40]

    def test_the_scale_is_not_forced_onto_an_eight_pixel_grid(self, tokens):
        """Artboard 01's "8px grid" caption is wrong; artboard 10 is the reference."""
        steps = {int(v) for v in re.findall(r"--space-(\d+):", tokens)}
        assert {6, 7, 14, 18} <= steps


class TestNoShadowsOrGradients:
    """Depth is hairlines and ground/surface contrast only (DESIGN.md §3)."""

    @pytest.mark.parametrize("path", sorted((REPO / "src" / "styles").glob("*.css")))
    def test_no_stylesheet_uses_one(self, path):
        css = without_comments(path.read_text())
        assert "box-shadow" not in css
        assert "gradient(" not in css
