# Section parsers, one module per dashboard section (registry pattern,
# design ADR-0007 extended by the two-layer rebuild). Live sections parse the
# lockstep artifact formats; digest sections load plan/digests/*.json via
# mc.digests.
