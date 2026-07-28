import itertools
import math

import numpy as np
import pandas as pd
import pytest

from src.viz.descriptive import summarize, _print_gate, SPORT_COLORS


def _panel():
    # season 2019 (covid_era=False): 3 clean regular-season home games
    #   win (+7), loss (-3), tie (0, home_win=NA)
    #   + 1 neutral-site game (excluded), + 1 playoff game (excluded)
    # season 2020 (covid_era=True): 2 clean games: win (+1), loss (-6)
    rows = [
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=7,  covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=False, home_margin=-3, covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=pd.NA, home_margin=0,  covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=True,  relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=10, covid_era=False),
        dict(season=2019, is_playoff=True,  neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=14, covid_era=False),
        dict(season=2020, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=1,  covid_era=True),
        dict(season=2020, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=False, home_margin=-6, covid_era=True),
    ]
    df = pd.DataFrame(rows)
    df["sport"] = "nfl"
    df["home_win"] = df["home_win"].astype("boolean")
    return df


def test_exclusions_and_counts():
    out = summarize(_panel())
    r19 = out[out["season"] == 2019].iloc[0]
    assert r19["n_games"] == 3          # neutral + playoff excluded, tie kept
    assert r19["n_games_raw"] == 4      # regular-season games before exclusions (excl playoff)


def test_win_pct_and_margin_2019():
    out = summarize(_panel())
    r19 = out[out["season"] == 2019].iloc[0]
    # decided games = win, loss -> 0.5; tie excluded from win%
    assert r19["home_win_pct"] == pytest.approx(0.5)
    assert r19["home_win_se"] == pytest.approx(0.3535533905932738)
    # margin over win/loss/tie = (7 - 3 + 0)/3
    assert r19["mean_home_margin"] == pytest.approx(1.3333333333333333)
    assert r19["home_margin_se"] == pytest.approx(2.96273147243853)


def test_2020_values():
    out = summarize(_panel())
    r20 = out[out["season"] == 2020].iloc[0]
    assert r20["mean_home_margin"] == pytest.approx(-2.5)
    assert r20["home_margin_se"] == pytest.approx(3.5)


def test_pooled_fullcrowd_uses_only_noncovid():
    out = summarize(_panel())
    pooled = out[out["season"] == "pooled_fullcrowd"].iloc[0]
    # only 2019 is covid_era False -> pooled == 2019 numbers
    assert pooled["mean_home_margin"] == pytest.approx(1.3333333333333333)
    assert pooled["home_win_pct"] == pytest.approx(0.5)
    assert pooled["n_games"] == 3


def test_covid_era_flag_per_season():
    out = summarize(_panel())
    assert out[out["season"] == 2019].iloc[0]["covid_era"] == False  # noqa: E712
    assert out[out["season"] == 2020].iloc[0]["covid_era"] == True   # noqa: E712
    # pooled_fullcrowd is the full-crowd baseline -> not treated
    assert out[out["season"] == "pooled_fullcrowd"].iloc[0]["covid_era"] == False  # noqa: E712


def test_gate_keys_off_treated_season_not_hardcoded_2020(capsys):
    # NBA-style: the treated season is 2021 (not 2020). 2020 is full-crowd and
    # does NOT dip; the real dip is in 2021. The gate must PASS off 2021, which a
    # hardcoded-2020 check would miss (it would see 2020's non-dip and CHECK).
    table = pd.DataFrame([
        dict(sport="nba", season=2019, covid_era=False, home_win_pct=0.60, mean_home_margin=3.0),
        dict(sport="nba", season=2020, covid_era=False, home_win_pct=0.60, mean_home_margin=3.0),
        dict(sport="nba", season=2021, covid_era=True,  home_win_pct=0.55, mean_home_margin=0.9),
        dict(sport="nba", season="pooled_fullcrowd", covid_era=False,
             home_win_pct=0.59, mean_home_margin=2.5),
    ])
    _print_gate(table)
    out = capsys.readouterr().out
    assert "[PASS] nba" in out
    assert "treated=[2021]" in out


def test_gate_checks_reports_no_dip(capsys):
    # Treated season margin ABOVE pooled -> no dip -> CHECK (MLB-style).
    table = pd.DataFrame([
        dict(sport="mlb", season=2020, covid_era=True, home_win_pct=0.55, mean_home_margin=0.18),
        dict(sport="mlb", season="pooled_fullcrowd", covid_era=False,
             home_win_pct=0.53, mean_home_margin=0.04),
    ])
    _print_gate(table)
    out = capsys.readouterr().out
    assert "[CHECK] mlb" in out


def test_summarize_playoffs_flag_selects_the_postseason_slice():
    panel = _panel()
    reg = summarize(panel)                       # default: regular season, unchanged
    post = summarize(panel, playoffs=True)

    # the fixture's only playoff game is 2019, margin +14, a home win
    p19 = post[post["season"] == 2019].iloc[0]
    assert p19["n_games"] == 1
    assert p19["mean_home_margin"] == 14
    assert p19["home_win_pct"] == 1.0
    # the regular-season slice is untouched by the new parameter
    assert reg[reg["season"] == 2019].iloc[0]["n_games"] == 3
    assert list(reg.columns) == list(post.columns)
    # no 2020 playoff game in the fixture -> only 2019 + the pooled row
    assert set(post["season"]) == {2019, "pooled_fullcrowd"}


def test_sport_color_and_marker_dicts_match_across_modules():
    from src.models.twfe import SPORT_COLORS as a, MARKERS as am
    from src.viz.descriptive import SPORT_COLORS as b, MARKERS as bm
    assert a == b                          # two dicts that must never drift
    assert am == bm                        # markers carry sport identity under CVD


def _lum(hexcode):
    c = [int(hexcode[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


@pytest.mark.parametrize("sport,hexcode", list(SPORT_COLORS.items()))
def test_every_sport_color_clears_the_3to1_contrast_floor(sport, hexcode):
    # Parametrized (not a for-loop with one assert) so a second failing color
    # can't hide behind the first -- that's exactly what hid the nhl failure
    # when this test was first written against an assert-in-a-loop.
    ratio = 1.05 / (_lum(hexcode) + 0.05)
    assert ratio >= 3.0, f"{sport} {hexcode} contrast {ratio:.2f} < 3:1"


# Machado, Oliveira & Fernandes (2009) CVD transforms at severity 1.0, linear RGB.
# Copied verbatim from the dataviz skill's bundled scripts/validate_palette.js
# (the skill lives outside this repo, so "import" isn't available -- keep these
# constants in lockstep with that file by hand if either changes).
_MACHADO = {
    "protan": [[0.152286, 1.052583, -0.204868],
               [0.114503, 0.786281, 0.099216],
               [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968],
               [0.280085, 0.672501, 0.047413],
               [-0.011820, 0.042940, 0.968881]],
}
_CVD_FLOOR = 6.0  # validate_palette.js CVD_FLOOR -- WARN/legal-with-labels band starts here


def _lin(hexcode):
    c = [int(hexcode[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def _oklab(rgb):
    r, g, b = rgb
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _delta_e_cvd(h1, h2, kind):
    """OKLab Delta-E x100 between two hexes as seen under simulated protan/deutan."""
    sim = lambda rgb: [max(0, min(1, sum(_MACHADO[kind][i][k] * rgb[k] for k in range(3))))
                        for i in range(3)]
    a, b = _oklab(sim(_lin(h1))), _oklab(sim(_lin(h2)))
    return 100 * math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


@pytest.mark.parametrize("pair", list(itertools.combinations(SPORT_COLORS.items(), 2)))
def test_every_sport_color_pair_clears_the_cvd_floor(pair):
    # F4: contrast alone doesn't guard the property that actually got tight when
    # nhl moved to red -- a future edit could preserve contrast while collapsing
    # a pair under CVD. Floor (6.0), not target (8.0): this asserts a real
    # invariant, not today's exact measured value.
    (s1, h1), (s2, h2) = pair
    worst = min(_delta_e_cvd(h1, h2, "protan"), _delta_e_cvd(h1, h2, "deutan"))
    assert worst >= _CVD_FLOOR, f"{s1} {h1} vs {s2} {h2}: CVD dE {worst:.2f} < {_CVD_FLOOR}"
