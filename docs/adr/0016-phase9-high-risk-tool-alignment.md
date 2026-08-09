# ADR 0016: Fail-safe reroute deterministic high-risk intent evidence

- Status: Accepted
- Date: 2026-08-09

## Decision

Before tool dispatch, compare learned intent with the deterministic safety
classifier. Only when deterministic evidence is high risk and the learned model
disagrees, reroute to the typed high-risk intent. Ordinary low/medium-risk
single-intent routing remains learned. Every override is counted in the report.

## Evidence

On the same checkpoint and 36-scenario dev Harness, two high-risk alignment
overrides reduced unsafe high-risk error from 0.0556 to zero. Task success rose
from 0.8889 to 0.9167 and False-success stayed zero. Three non-high-risk failures
remain visible; the guard does not rewrite Judge outcomes.

## Consequences

The combined v3 Harness passes the predeclared development safety and utility
gates, so a new formal repeated experiment may be frozen. This result does not
authorize sealed evaluation of the screening checkpoint and does not justify
replacing learned routing with rules. Override rate and failure categories must
be reported alongside model metrics.
