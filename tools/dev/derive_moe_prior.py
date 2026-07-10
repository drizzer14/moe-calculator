# -*- coding: utf-8 -*-
"""DEV-ONLY: derive the UNIVERSAL_CV prior baked into domain/moe_estimate.py.

Run on a DEV machine (Python 3) with network. NOT shipped in the .wotmod and NOT used at
runtime -- it exists solely to produce one constant. The offline estimator needs a single
universal coefficient of variation (sigma/mu) for its single-sample prior; we obtain it by
fitting each tank's (mu, sigma) from a published MoE table (three known percentile points:
65/85/95) and averaging sigma/mu across the whole roster.

    python tools/dev/derive_moe_prior.py            # fetches tomato.gg once
    python tools/dev/derive_moe_prior.py page.html  # parse a saved copy instead

Output: the recommended UNIVERSAL_CV (median across tanks -- robust to outliers), the mean,
the spread, and the mean normal-fit residual at the 85th point (a sanity check on the
normality assumption). Copy the printed constant into moe_estimate.UNIVERSAL_CV.

The value is aggregate-derived (a single scalar), not the table itself; runtime stays fully
offline. If the source is unreachable, the constant may be hand-set -- record its provenance.
"""
from __future__ import print_function

import re
import sys
import math

URL = "https://tomato.gg/moe/EU"
_AGENT = "Mozilla/5.0 (compatible; MoE-prior-derive/1.0)"
_RECORD_RX = re.compile(r'"65":(\d+),"85":(\d+),"95":(\d+),"100":(\d+),"id":(\d+)')

# Probit z-values for the three known percentiles (scipy.stats.norm.ppf).
Z65 = 0.38532046640756773
Z85 = 1.0364333894937898
Z95 = 1.6448536269514722


def _fetch(url):
    try:
        from urllib.request import Request, urlopen
    except ImportError:  # py2 fallback
        from urllib2 import Request, urlopen
    req = Request(url, headers={"User-Agent": _AGENT})
    return urlopen(req, timeout=30).read().decode("utf-8", "replace")


def _ols_mu_sigma(points):
    """OLS of damage on z over the (z, d) points -> (mu, sigma)."""
    n = float(len(points))
    zbar = sum(z for z, _d in points) / n
    dbar = sum(d for _z, d in points) / n
    sxx = sum((z - zbar) ** 2 for z, _d in points)
    if sxx <= 0:
        return None
    sxy = sum((z - zbar) * (d - dbar) for z, d in points)
    sigma = sxy / sxx
    return (dbar - sigma * zbar, sigma)


def main():
    text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else _fetch(URL)
    cvs = []
    residuals = []
    for m in _RECORD_RX.finditer(text):
        d65, d85, d95 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (0 < d65 < d85 < d95):
            continue
        fit = _ols_mu_sigma([(Z65, d65), (Z85, d85), (Z95, d95)])
        if fit is None:
            continue
        mu, sigma = fit
        if mu <= 0 or sigma <= 0:
            continue
        cvs.append(sigma / mu)
        residuals.append(abs((mu + sigma * Z85) - d85) / float(d85))

    if not cvs:
        raise SystemExit("No MoE records parsed -- source markup may have changed.")

    cvs.sort()
    n = len(cvs)
    median = cvs[n // 2] if n % 2 else 0.5 * (cvs[n // 2 - 1] + cvs[n // 2])
    mean = sum(cvs) / n
    sd = math.sqrt(sum((c - mean) ** 2 for c in cvs) / n)
    print("tanks fitted        : %d" % n)
    print("UNIVERSAL_CV (median): %.4f   <-- bake this" % median)
    print("            (mean)   : %.4f (sd %.4f)" % (mean, sd))
    print("mean 85th residual  : %.2f%% (normality sanity check)" % (100.0 * sum(residuals) / n))


if __name__ == "__main__":
    main()
