#!/usr/bin/env python3
"""Evaluate a conditional dilute-inclusion estimate of creep enhancement.

For a scalar resolved-shear amplitude tau_m decaying as (a/r)^3, an assumed
activation volume V*, and equal positive/negative stress biases, the model is
f*x0*integral((cosh(u)-1)/u^2, 0, x0), x0 = V* tau_m / kT.
The zero lower limit is the dilute approximation. This scalar model omits
angular stress structure, overlapping fields, and changes in dislocation
population. V* is an input in units of b^3, not measured by this script.
Functions use Pa and SI constants; JSON reports MPa and dimensionless rates.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

from scipy.integrate import quad
from scipy.optimize import brentq

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "reports" / "stageG5_two_scale_bridge.json"

KT_300 = 1.380649e-23 * 300.0  # J
B_BURGERS = 4.05e-10 / math.sqrt(2.0)  # m
B3 = B_BURGERS**3  # m^3
MU_AL = 26.5e9  # Pa
# Approximate conversion of 0.35 wt% using densities 3.85 and 2.70 g/cm^3.
F_VOL = 0.00246  # inclusion volume fraction
TARGET = 0.25  # +25% creep enhancement


def enhancement(sigma_m: float, v_star_b3: float, f: float = F_VOL) -> float:
    """Return relative rate increase for shear amplitude sigma_m [Pa].

    The historical argument name sigma_m denotes a resolved-shear amplitude,
    not pressure or a von Mises invariant. f is the inclusion volume fraction.
    """
    if not all(math.isfinite(v) for v in (sigma_m, v_star_b3, f)):
        raise ValueError("Model inputs must be finite")
    if sigma_m < 0 or v_star_b3 < 0 or not 0 <= f < 1:
        raise ValueError("Use nonnegative amplitudes and volumes, and 0 <= f < 1")
    x0 = v_star_b3 * B3 * sigma_m / KT_300
    if x0 <= 0:
        return 0.0

    # sinh avoids cancellation of cosh(u) - 1 for weak biases.
    def integrand(u):
        return 0.5 if u == 0 else 2 * (math.sinh(u / 2) / u) ** 2

    val, _ = quad(integrand, 0.0, x0, limit=200)
    return f * x0 * val


def required_sigma(v_star_b3: float, target: float = TARGET, f: float = F_VOL) -> float:
    """Invert the model for a shear amplitude [Pa], within 0--500 MPa."""
    if not math.isfinite(target) or target < 0:
        raise ValueError("Target enhancement must be finite and nonnegative")
    lo, hi = 0.0, 5e8
    if enhancement(hi, v_star_b3, f) < target:
        return float("nan")
    return brentq(lambda s: enhancement(s, v_star_b3, f) - target, lo, hi, xtol=1e3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    res = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": "Eshelby r^-3 exterior field + thermally activated glide; "
        "<rate>/rate0 - 1 = f*x0*INT_0^x0 (cosh u - 1)/u^2 du, x0 = V* sigma_m / kT",
        "constants": {
            "kT_300K_J": KT_300,
            "b_m": B_BURGERS,
            "mu_Al_Pa": MU_AL,
            "volume_fraction": F_VOL,
            "target_enhancement": TARGET,
        },
        "assumptions": {
            "stress_amplitude": "scalar resolved shear in Pa",
            "activation_volumes": "assumed sensitivity range, not MD measurements",
            "bias_average": "equal positive and negative biases, giving cosh",
            "radial_lower_limit": "zero, dilute approximation",
            "volume_fraction": "0.35 wt%, densities 3.85/2.70 g/cm^3, approximately 0.00246",
        },
        "required_interface_stress": {},
        "forward_prediction_at_claimed_147MPa": {},
        "what_real_magnetostriction_gives": {},
    }

    for v in (19, 30, 50, 70, 100, 142):
        s_req = required_sigma(v)
        res["required_interface_stress"][f"V*={v}b^3"] = {
            "sigma_m_MPa": round(s_req / 1e6, 1),
            "note": "resolved-shear amplitude needed for +25% within the stated model",
        }
        fwd = enhancement(147e6, v)
        res["forward_prediction_at_claimed_147MPa"][f"V*={v}b^3"] = {
            "predicted_enhancement": f"{fwd:.3e}",
            "vs_measured_0.25": "overshoots by " + f"{fwd / TARGET:.2e}" + "x",
        }

    for lam in (2e-5, 4e-5, 1e-4):
        res["what_real_magnetostriction_gives"][f"lambda_s={lam:.0e}"] = {
            "sigma_matrix_MPa": round(2 * MU_AL * lam / 1e6, 2),
            "route": "2*mu_Al*lambda_s elastic scale; not a geometry-resolved interface stress",
        }

    res["claimed_by_manuscript_MPa"] = 147.0
    res["our_eigenstrain_eps"] = 0.00194
    res["our_eigenstrain_in_ppm"] = 1940
    reqs = [
        res["required_interface_stress"][k]["sigma_m_MPa"] for k in res["required_interface_stress"]
    ]
    reals = [
        res["what_real_magnetostriction_gives"][k]["sigma_matrix_MPa"]
        for k in res["what_real_magnetostriction_gives"]
    ]
    res["verdict"] = (
        f"Under the model assumptions, +25% requires {min(reqs):.1f}-{max(reqs):.1f} MPa "
        f"for the assumed activation volumes. The comparison scale 2*mu*lambda spans "
        f"{min(reals):.1f}-{max(reals):.1f} MPa. Neither calculation measures the actual "
        f"strain or the stress distribution of an Al13Fe4 inclusion."
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
