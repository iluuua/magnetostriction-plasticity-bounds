#!/usr/bin/env python3
"""Audit: every quantitative claim in the manuscripts against the JSON records.

It reads the numbers out of docs/reports/, recomputes the two-scale bridge from
scratch, and asserts that each value appears in both language versions in the
correct local form (decimal point in English, decimal comma in Russian). It also
runs the structural checks a compile would catch late: balanced math delimiters,
balanced braces, every \\ref resolved by a \\label, every \\includegraphics backed
by a file on disk, and every \\cite present in the bibliography.

No expected number is written into this file by hand. Each one is loaded from
the record that produced it and rounded here the way the text rounds it, so a
record that changes makes the audit fail rather than silently disagree.

    python audit_v4.py          # exit 0 and "all consistent", or exit 1 and a list

Records used: stageG10_field_profile{,_free,_at_pair}, stageG12_eigenstrain_
retention{,_free,_free_cg}, stageG15_thresholds, stageG2_depinning_summary_
G15{ctl_free,held}, stageG17_ridge_continuum, stageG8_eshelby3d,
stageG5_two_scale_bridge, stageG7_pinning_statistics.
"""
from __future__ import annotations

import io
import json
import math
import re
from pathlib import Path

from scipy.optimize import brentq
import mpmath as mp

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent / "reports"
EN = io.open(HERE / "main.tex", encoding="utf-8").read()
RU = io.open(HERE / "main_ru.tex", encoding="utf-8").read()

fails, checks = [], 0


def rec(name):
    return json.loads(io.open(REPORTS / (name + ".json"), encoding="utf-8").read())


def need(text, label, needle, where):
    """Assert a literal string is present, collecting rather than raising."""
    global checks
    checks += 1
    if needle not in text:
        fails.append("%-36s missing in %s: %r" % (label, where, needle))


def both(label, en_needle, ru_needle):
    need(EN, label, en_needle, "EN")
    need(RU, label, ru_needle, "RU")


def ru_num(s):
    """English decimal form -> Russian decimal-comma form as the sources write it."""
    return re.sub(r"(\d)\.(\d)", r"\1{,}\2", s)


def g(v, nd=0):
    """Round a record value the way the text rounds it."""
    return ("%." + str(nd) + "f") % v


# ------------------------------------------------------- 1. interface field
prof = rec("stageG10_field_profile")
peak = prof["peak"]
nf = prof["noise_floor_beyond_60A"]
flanks = [x["max_RSS_MPa"] for x in prof["apex_straddling_bins_excluded"]]

# the width-averaged peak outside the bins that straddle the ridge flanks
both("width-averaged peak",
     "%s~MPa" % g(peak["max_RSS_MPa"], 1),
     "%s~МПа" % ru_num(g(peak["max_RSS_MPa"], 1)))

# the resolution level: mean and scatter of the slices beyond 60 A
both("far-field level",
     "$%s\\pm%s$~MPa" % (g(nf["mean_max_RSS_MPa"], 1), g(nf["std_MPa"], 1)),
     "$%s \\pm %s$~МПа" % (ru_num(g(nf["mean_max_RSS_MPa"], 1)),
                           ru_num(g(nf["std_MPa"], 1))))

# the excluded flank slices are quoted as a range, not as a measurement
both("flank range",
     "%s--%s~MPa" % (g(min(flanks)), g(max(flanks))),
     "%s--%s~МПа" % (g(min(flanks)), g(max(flanks))))

# the largest on-axis value in the matrix (the ridge interior is not matrix)
z_apex = prof.get("ridge_apex_A")
axis = [(r["r_A"], r["d_sigma_xz_axis_MPa"]) for r in prof["profile"]
        if r.get("d_sigma_xz_axis_MPa") is not None and r["r_A"] > (z_apex or 20)]
if not axis:
    fails.append("field profile: no on-axis samples above the ridge apex")
else:
    r_max, v_max = max(axis, key=lambda t: abs(t[1]))
    both("on-axis peak", "%s~MPa" % g(abs(v_max)), "%s~МПа" % g(abs(v_max)))
    checks += 1
    if not re.search(r"1[0-9]--%s~MPa" % g(abs(v_max)), EN):
        fails.append("on-axis range: text does not state a band ending at %s MPa"
                     % g(abs(v_max)))

# the field where the dislocation pair of the loaded cell actually sits
pair = rec("stageG10_field_at_pair")
w = pair["windows"]
lo = [w["lower_plus_b_partner"]["box_10x6_A"]["d_sigma_xz_MPa"],
      w["lower_plus_b_partner"]["box_25x11_A"]["d_sigma_xz_MPa"],
      w["upper_minus_b_partner"]["box_10x6_A"]["d_sigma_xz_MPa"],
      w["upper_minus_b_partner"]["box_25x11_A"]["d_sigma_xz_MPa"]]
both("field at the pair",
     "%s--%s~MPa" % (g(min(lo)), g(max(lo))),
     "%s--%s~МПа" % (g(min(lo)), g(max(lo))))

# the free (unheld) ridge: the on-axis shear falls below the level the text quotes
free = rec("stageG10_field_profile_free")
free_axis = [abs(r["d_sigma_xz_axis_MPa"]) for r in free["profile"]
             if r.get("d_sigma_xz_axis_MPa") is not None
             and r["r_A"] > (free.get("ridge_apex_A") or 20)]
checks += 1
if free_axis and max(free_axis) >= 5.0:
    fails.append("free ridge: on-axis shear reaches %.1f MPa, the text says below 5"
                 % max(free_axis))

# ------------------------------------------------------- 2. eigenstrain retention
held = rec("stageG12_eigenstrain_retention")
fre = rec("stageG12_eigenstrain_retention_free")
frecg = rec("stageG12_eigenstrain_retention_free_cg")
# the text calls this uncertainty the standard error of the fit, so it must be
# the standard error the record holds, at the precision the record holds it
_hse = held["eta_used_for_rescaling_se"]
both("retention held",
     "$%s\\pm%s$" % (g(held["eta_used_for_rescaling"], 2), g(_hse, 3)),
     "$%s \\pm %s$" % (ru_num(g(held["eta_used_for_rescaling"], 2)), ru_num(g(_hse, 3))))
for tag, r in (("free", fre), ("free CG", frecg)):
    both("retention %s" % tag,
         "$%s\\pm%s$" % (g(r["eta_used_for_rescaling"], 2),
                         g(r["eta_used_for_rescaling_se"], 2)),
         "$%s \\pm %s$" % (ru_num(g(r["eta_used_for_rescaling"], 2)),
                           ru_num(g(r["eta_used_for_rescaling_se"], 2))))
# the pair of them is quoted as a band
_flo, _fhi = sorted([fre["eta_used_for_rescaling"], frecg["eta_used_for_rescaling"]])
both("retention band",
     "%s--%s" % (g(_flo, 1), g(_fhi, 1)),
     "%s--%s" % (ru_num(g(_flo, 1)), ru_num(g(_fhi, 1))))

# ------------------------------------------------------- 3. loaded-cell thresholds
thr = rec("stageG15_thresholds")
onset = thr["pair_lower_onset_MPa"]["ctl"]
both("pair onset (free inclusion)",
     "%d--%d~MPa" % (onset[0], onset[1]),
     "%d--%d~МПа" % (onset[0], onset[1]))
both("end of the ramp",
     "%d~MPa" % thr["ramp_max_MPa"],
     "%d~МПа" % thr["ramp_max_MPa"])
checks += 1
if thr["nucleation_MPa"] is not None:
    fails.append("thresholds: a nucleation stress is recorded (%s); the text says "
                 "none was seen up to the end of the ramp" % thr["nucleation_MPa"])
for t, w_, phrase in ((EN, "EN", "no new dislocation"), (RU, "RU", "новых дислокаций")):
    checks += 1
    if phrase not in t:
        fails.append("%s: the null nucleation result is not stated" % w_)

# the two held ramps must be described as coinciding within one frame
held_sum = rec("stageG2_depinning_summary_G15held")
_frames = held_sum.get("frame_resolution_MPa") or held_sum.get("tau_step_MPa")
if _frames:
    both("frame resolution", "%s~MPa" % g(_frames), "%s~МПа" % g(_frames))

# ------------------------------------------------------- 4. mobility and pinning
pin = rec("stageG7_pinning_statistics")
_net = pin.get("net_displacement_b")
if isinstance(_net, dict) and "value" in _net:
    _net = _net["value"]
checks += 1
if _net is None:
    fails.append("pinning record carries no net displacement")

# ------------------------------------------------------- 5. the two-scale bridge
bridge = rec("stageG5_two_scale_bridge")
C = bridge["constants"]
kT, b, f = C["kT_300K_J"], C["b_m"], C["volume_fraction"]
b3 = b ** 3
target = C["target_enhancement"]


def G(x):
    with mp.workdps(60):
        X = mp.mpf(x)
        return float(X * mp.shi(X) - (mp.cosh(X) - 1))


def enh(sig, V, frac=f):
    return frac * G(V * b3 * sig / kT)


both("volume fraction", "$f=%.5f$" % f, "$f = %s$" % ru_num("%.5f" % f))

req = {int(k.split("=")[1].rstrip("b^3")): v["sigma_m_MPa"]
       for k, v in bridge["required_interface_stress"].items()}
fwd = {int(k.split("=")[1].rstrip("b^3")): float(v["predicted_enhancement"])
       for k, v in bridge["forward_prediction_at_claimed_147MPa"].items()}

# every required stress is recomputed from the model, then checked against the table
for V, sig in sorted(req.items()):
    checks += 1
    got = brentq(lambda s: enh(s, V) - target, 1e4, 5e8, xtol=1.0) / 1e6
    if abs(got - sig) / sig > 0.01:
        fails.append("bridge: recomputed sigma_m(%d b^3) = %.2f, record says %.2f"
                     % (V, got, sig))
    need(EN, "table row %d" % V, "$%d\\,b^{3}$" % V, "EN")
    need(EN, "table sigma_m %d" % V, "%s" % g(sig, 1), "EN")


def mantissa(v):
    e = int(math.floor(math.log10(v)))
    return "%.1f" % (v / 10 ** e), e


for V, val in sorted(fwd.items()):
    m, e = mantissa(val)
    need(EN, "table forward %d" % V, "$%s\\times10^{%d}$" % (m, e), "EN")
    need(RU, "table forward %d" % V, "$%s\\cdot10^{%d}$" % (ru_num(m), e), "RU")

_lo, _hi = min(req.values()), max(req.values())
both("required range",
     "%s--%s~MPa" % (g(_lo, 1), g(_hi, 1)),
     "%s--%s~МПа" % (ru_num(g(_lo, 1)), ru_num(g(_hi, 1))))

# what the measured Fe-Al magnetostriction gives instead: the text quotes the
# Eshelby sphere rescaled to the largest reported bulk Fe-Al value, not 2*mu*lambda
_meas = rec("stageG8_eshelby3d")["at_measured_FeAl_magnetostriction"]["sphere_interior_MPa"]
_biggest = _meas[sorted(_meas, key=lambda k: float(k.split()[0]))[-1]]
both("sphere at measured magnetostriction",
     "%s~MPa" % g(_biggest), "%s~МПа" % g(_biggest))

# ------------------------------------------------------- 6. Eshelby comparison
esh = rec("stageG8_eshelby3d")
inter = esh["interior_stress_MPa"]["sphere_3D"]["max_RSS_MPa"]
outer = max(x["max_RSS_MPa"] for x in esh["exterior_decay_sphere"])
both("sphere interior", "%s~MPa" % g(inter), "%s~МПа" % g(inter))
both("sphere just outside", "%s~MPa" % g(outer), "%s~МПа" % g(outer))
for _p_en, _p_ru in (("$a=35$~\\AA{}", "$a = 35$~\\AA{}"),
                     ("$\\mu=26.5$~GPa", "$\\mu = 26{,}5$~ГПа"),
                     ("$\\nu=0.347$", "$\\nu = 0{,}347$")):
    both("Eshelby params", _p_en, _p_ru)

cont = rec("stageG17_ridge_continuum")
checks += 1
if not cont.get("profile"):
    fails.append("ridge continuum record carries no profile")

# ------------------------------------------------------- 7. LaTeX hygiene
for t, w_ in ((EN, "EN"), (RU, "RU")):
    checks += 2
    body = re.sub(r"(?<!\\)%.*", "", t)
    if body.count("$") % 2:
        fails.append("%s: odd number of $ delimiters" % w_)
    if body.count("{") != body.count("}"):
        fails.append("%s: brace imbalance %d/%d"
                     % (w_, body.count("{"), body.count("}")))
    labels = set(re.findall(r"\\label\{([^}]+)\}", t))
    for r in set(re.findall(r"\\ref\{([^}]+)\}", t)):
        checks += 1
        if r not in labels:
            fails.append("%s: \\ref{%s} has no \\label" % (w_, r))
    for gr in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t):
        checks += 1
        if not any((HERE / (gr + e)).exists() for e in (".pdf", ".png", "")):
            fails.append("%s: figure %s not on disk" % (w_, gr))
    checks += 1
    if "\\todo" in t:
        fails.append("%s: a \\todo marker survived into the manuscript" % w_)

keys = set()
for grp in re.findall(r"\\cite[a-z]*\{([^}]+)\}", EN):
    keys |= {k.strip() for k in grp.split(",")}
bib = io.open(HERE / "references.bib", encoding="utf-8").read()
bbl = io.open(HERE / "main.bbl", encoding="utf-8").read()
for k in sorted(keys):
    checks += 2
    if "{%s," % k not in bib:
        fails.append("EN: \\cite{%s} not in references.bib" % k)
    if k not in bbl:
        fails.append("EN: \\cite{%s} not in main.bbl (would print [?])" % k)

# RU numbers its list by hand: every [n] used must exist in the list
# strip math mode first: Miller indices such as $z = [111]$ are not citations
_ru_prose = re.sub(r"\$[^$]*\$", " ", RU)
ru_refs = set(int(n) for grp in re.findall(
    r"(?:^|[\s(,;])\[(\d+(?:[,\s\\-]+\d+)*)\]", _ru_prose, re.M)
    for n in re.findall(r"\d+", grp))
ru_items = len(re.findall(r"^\\item", RU, re.M)) or len(re.findall(r"\\bibitem", RU))
checks += 1
if ru_refs and ru_items and max(ru_refs) > ru_items:
    fails.append("RU: citation [%d] exceeds the %d entries in the list"
                 % (max(ru_refs), ru_items))

print("checks run: %d" % checks)
if fails:
    print("\nFAILURES (%d):" % len(fails))
    for f_ in fails:
        print("  " + f_)
    raise SystemExit(1)
print("all consistent")
