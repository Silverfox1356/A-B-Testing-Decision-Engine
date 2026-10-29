# Decision memo: streamlined checkout flow experiment

**To**: Product and Growth leadership
**From**: Experimentation analytics
**Re**: Ship decision for the streamlined checkout flow (~98-day A/B test, 975,694 users)

## Recommendation

**Ship via a phased rollout with live order-value monitoring, rather than an
immediate 100% launch.** The new checkout flow converts significantly more users.
One safety check, average order value, could not be verified either way at this
sample size; a staged rollout (25% then 50% then 100% over several weeks) captures
the conversion gain while the growing sample settles the open question, with an
automatic pause if order value degrades past tolerance.

## Evidence

- **Checkout conversion (primary)**: up 0.11 percentage points on a 3.5% baseline,
  a roughly 3% relative improvement. This is statistically solid (one-sided
  p = 0.0016 after correcting for testing multiple success metrics).
- **Revenue per user**: up $0.05 per user, but this is **not** statistically
  significant at this sample (p = 0.14). Per-user revenue is heavy-tailed (a few
  large baskets dominate the mean), so a lift this small is not detectable even at
  ~488k users per arm. Treat the direction as encouraging, not proven.
- **Checkout error rate (guardrail)**: rose 0.07pp, within the 0.5pp tolerance we
  agreed before launch. The rise is real but is the accepted cost of the change.
- **Average order value (guardrail)**: inconclusive. The test reaches only ~70%
  power on this metric, short of our 80% bar, so it neither clears nor breaches
  the 2% tolerance we set. Confirming it at our standards needs roughly 1.8x the
  traffic (about three more months at current volume). The point estimate sits
  inside the tolerance; we simply cannot yet rule out a breach.

## Projected impact if the lift holds

At our traffic of 10,000 users per day, the significant conversion lift adds about
**4,000 additional completed checkouts per year**. The revenue-per-user movement
(+$0.05) is directionally positive but not statistically established, so we are
deliberately **not** booking a dollar figure on it yet. Any projection assumes the
measured effect persists across seasons and does not decay after novelty.

## Caveats and assumptions

- The phased rollout must define its pause rule up front: if the accumulating
  order-value estimate breaches the 2% tolerance with statistical support, the
  rollout halts automatically.
- Alternatives to phasing are widening the order-value tolerance with finance's
  sign-off, or accepting the residual risk explicitly; both are business calls,
  not analytics calls.
- Results come from a single ~98-day window; seasonality is not covered, and the
  test measures short-term behavior only.

## Bottom line

The conversion gain is real and significant. Two open questions remain: whether
basket sizes shrink more than the 2% we can tolerate, and whether the revenue lift
is real. Both are best answered while capturing the conversion upside: phase
the rollout, watch order value and revenue, and stop if the data turns.
