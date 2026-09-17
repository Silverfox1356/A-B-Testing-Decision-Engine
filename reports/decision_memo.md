# Decision memo: streamlined checkout flow experiment

**To**: Product and Growth leadership
**From**: Experimentation analytics
**Re**: Ship decision for the streamlined checkout flow (14-day A/B test, 140,458 users)

## Recommendation

**Ship via a phased rollout with live order-value monitoring, rather than an
immediate 100% launch.** The new checkout flow clearly converts more users and
generates more revenue per visitor. One safety check, average order value, could
not be verified either way at this sample size; a staged rollout (25% then 50%
then 100% over several weeks) keeps that upside flowing while the growing sample
settles the open question, with an automatic pause if order value degrades past
tolerance.

## Evidence

- **Data quality**: the experiment passed its assignment check -- users reached
  the two arms in the intended 50/50 proportion, so the comparison below is
  sound. We check this before reading any metric, because an uneven split
  usually means a delivery or logging fault and would invalidate everything
  that follows.
- **Checkout conversion (primary)**: up 0.32 percentage points on a 3.5% baseline,
  a roughly 9% relative improvement. This is statistically solid (p < 0.001 after
  correcting for testing multiple success metrics).
- **Revenue per visitor**: up $0.18 per user, also statistically solid.
- **Checkout error rate (guardrail)**: rose 0.14pp, within the 0.5pp tolerance we
  agreed before launch. The rise is real but is the accepted cost of the change.
- **Average order value (guardrail)**: inconclusive. The data neither clears nor
  breaches the 2% tolerance we set. This is a sample-size reality, not a red
  flag: order value is only measurable on the ~3.5% of users who buy, so
  verifying it at our standards needs roughly 9x the traffic of this test
  (about four months at current volume). The point estimate sits well inside the
  tolerance; we simply cannot yet rule out a breach.

## Projected impact if the lift holds

At our traffic of 10,000 users per day, +$0.18 revenue per user annualizes to
roughly **$660,000 per year**, from about 11,600 additional completed checkouts.
Treat this as an if-the-lift-holds extrapolation, not a guarantee: it assumes the
measured effect persists across seasons and does not decay after novelty.

## Caveats and assumptions

- The phased rollout must define its pause rule up front: if the accumulating
  order-value estimate breaches the 2% tolerance with statistical support, the
  rollout halts automatically.
- Alternatives to phasing are widening the order-value tolerance with finance's
  sign-off, or accepting the residual risk explicitly; both are business calls,
  not analytics calls.
- Results come from a single 14-day window; seasonality is not covered, and the
  test measures short-term behavior only.

## Bottom line

The upside is real and quantified. The one open question, whether basket sizes
shrink more than the 2% we can tolerate, is best answered while capturing the
upside: phase the rollout, watch order value, and stop if the data turns.
