# 05 — Interview question bank

~95 questions, grouped by type, with model answers. Rehearse **out loud**.
Target 60–90 seconds per answer unless marked otherwise.

Legend: 🟢 basic · 🟡 intermediate · 🔴 hard / likely to separate candidates

---

## Section 1 — Opening and framing

**🟢 Q1. Tell me about this project.**
> I built an experimentation decision engine — an A/B testing pipeline that goes
> past "p < 0.05, ship it." It does three things production platforms do that
> most tutorials skip. First, it designs for power: before running anything it
> computes how much traffic a given minimum detectable effect actually needs.
> Second, it uses CUPED — pre-experiment data — to cut metric variance, so the
> same traffic buys a shorter experiment. Third, it turns results into a
> SHIP / DO NOT SHIP / INVESTIGATE verdict that treats success metrics and
> guardrail metrics with deliberately different statistical risk postures.
> I validated the whole thing against simulation where I control the truth, then
> ran it unchanged on a real 64,000-user email experiment.

**🟢 Q2. Why did you build it?**
> Most A/B writeups stop at a t-test. When I read how Microsoft's ExP, Spotify
> and Netflix actually operate, the hard parts are elsewhere: sizing before you
> run, squeezing more out of fixed traffic, and deciding under risk when metrics
> disagree. I wanted to implement those three things end to end rather than
> demonstrate a p-value again.

**🟡 Q3. What is the single most interesting thing you learned?**
> That guardrail power is brutally expensive and almost nobody budgets for it.
> My primary conversion test needed 70,000 users per arm. The average-order-value
> guardrail, at the same 2% tolerance, needed roughly 900,000 — about 13 times
> more — because AOV only exists for the 3.5% of users who buy and order values
> are heavy-tailed. At the primary-powered sample size that guardrail had 20%
> power, meaning it was essentially decorative. Most teams never compute this and
> so ship behind guardrails that could never have caught anything.

**🟡 Q4. What would you do differently?**
> The two biggest gaps I've since closed. I had no sample ratio mismatch check —
> the standard first gate in any real platform — so I added one, and it returns
> a separate INVALID verdict that withholds every metric. And I'd demonstrated
> 39% variance reduction from CUPED and then run the verdicts on raw metrics, so
> I wired CUPED into the engine. What's still open: sequential testing, because
> fixed-horizon analysis is only valid if nobody peeks and everyone peeks; and
> CUPAC, which would materially help the real-data case.

**🔴 Q4b. Wiring CUPED in must have been simple. Was it?**
> The wiring was ten lines. What wasn't simple was discovering I couldn't apply
> it to the average-order-value guardrail. CUPED's unbiasedness rests on the
> arms having equal covariate means, which randomization guarantees on the
> randomized population — and AOV is measured on converters only, which is a
> post-treatment subgroup. I simulated it with a true AOV effect of exactly
> zero: the raw estimator came back at +$0.07, well within noise, and the CUPED
> one at **+$0.70** — twelve Monte Carlo standard errors from zero, against a
> $1.18 margin. And it biased toward *passing*, which is the worst direction for
> a safety check. So the engine now raises a ValueError if you try to combine a
> covariate with a row filter. It's the same failure mode as the original AOV
> incident, which was a slightly unsettling thing to rediscover from the other
> direction.

**🟡 Q5. Explain it to a VP of Product in 30 seconds.**
> Before we run a test, it tells you how long it needs to run to give a
> trustworthy answer. While it runs, it uses customers' past behaviour to cancel
> out noise, so you get that answer sooner. And when it's done, it doesn't just
> say "the number went up" — it checks that nothing important got worse, and
> tells you plainly whether to ship, not ship, or investigate before deciding.

---

## Section 2 — Power analysis

**🟢 Q6. What is statistical power?**
> The probability of detecting an effect of a given size, given it is real.
> 1 − β. 80% power means that if the true effect is exactly the MDE, four out of
> five identically-run experiments would come back significant — and one would
> miss it.

**🟢 Q7. What are the inputs to a power calculation?**
> Baseline rate, minimum detectable effect, α, and target power. Fix any three
> and the fourth determines the sample size.

**🔴 Q8. Derive the two-proportion sample size formula.** *(whiteboard, 5 min)*
> Under H₀ the rates are equal, so the null standard error is
> √(2p̄(1−p̄)/n) and we reject when the observed difference exceeds
> z_{1−α/2} times that. Under H₁ the estimator is normal around the true Δ with
> unpooled SE √((p₁(1−p₁)+p₂(1−p₂))/n). Power is the probability of landing in
> the rejection region, which is Φ((Δ − z_{1−α/2}·SE₀)/SE₁). Set that equal to
> z_{1−β}, so Δ = z_{1−α/2}·SE₀ + z_{1−β}·SE₁. Both SEs carry a 1/√n, so factor
> it out, square both sides, and n is the squared sum of those two terms divided
> by Δ².
>
> Key point: the two square roots are different on purpose — the critical value
> is computed under the null with pooled variance, the estimator's distribution
> is under the alternative with unpooled variance.

**🟡 Q9. I halve the MDE. What happens to sample size?**
> It quadruples. n is inversely proportional to Δ², and Δ is proportional to the
> MDE. Detecting small effects is the single most expensive thing in
> experimentation.

**🟡 Q10. Estimate a sample size in your head.**
> Use n ≈ 16·p(1−p)/Δ². It comes from (1.96 + 0.84)² ≈ 7.84 ≈ 8, doubled for two
> arms. For 3.5% baseline and +8% relative: Δ = 0.0028, so
> 16 × 0.035 × 0.965 / 0.0028² ≈ 69,000. The exact formula gives 70,229.

**🟡 Q11. Why is your baseline rate so important?**
> Because for a fixed *relative* lift, Δ = p × MDE, so n grows roughly as 1/p.
> Halving the baseline rate roughly doubles the traffic you need. Rare events
> are expensive, which is exactly why variance reduction matters for them.

**🔴 Q12. Your design uses two-sided α but your decision uses a one-sided test.
Isn't that inconsistent?**
> It is, and it's conservative in a safe direction. Two-sided sizing demands more
> users than one-sided sizing would, so my achieved one-sided power is above the
> 80% target rather than below it. The clean version would be one-sided
> throughout. I'd rather be over-powered than have to explain why I was
> under-powered.

**🟡 Q13. What if you can't get the sample size you need?**
> Four levers, all with costs. Widen the MDE — you only detect bigger effects.
> Raise α — more false positives. Lower power — more missed effects. Or reduce
> variance, which is the only lever that doesn't cost you error rate, and that's
> CUPED. Failing all four, you either accept an underpowered test and *say so*,
> or you don't run it. What you must not do is run it and interpret a null result
> as evidence of no effect.

**🟡 Q14. Why did your single simulated experiment give +8.92% when the truth
was +8%?**
> Sampling variation. The 95% CI was [+0.119pp, +0.514pp] around a true 0.28pp,
> so the truth sits comfortably inside. That's exactly why notebook 01's takeaway
> section notes that a single run is one draw and that at 80% power, one in five
> identical experiments would miss this real effect entirely.

---

## Section 3 — CUPED

**🟢 Q15. What is CUPED?**
> Controlled-experiment Using Pre-Experiment Data. You take the outcome metric
> and subtract off the part predictable from a pre-experiment covariate:
> Y_cuped = Y − θ(X − X̄), with θ = Cov(Y,X)/Var(X). Because X was measured
> before randomization, treatment can't have affected it, so the effect estimate
> stays unbiased while variance drops by a factor of 1 − ρ².

**🔴 Q16. Derive θ.**
> Var(Y − θX) = Var(Y) − 2θCov(Y,X) + θ²Var(X). That's a quadratic in θ opening
> upward. Differentiate: −2Cov + 2θVar(X) = 0, so θ* = Cov(Y,X)/Var(X). Which is
> just the OLS slope of Y on X.

**🔴 Q17. Derive the variance reduction.**
> Substitute θ* back: Var(Y) − Cov²/Var(X) = Var(Y)(1 − Cov²/(Var(Y)Var(X))),
> and that fraction is ρ². So Var(Y_cuped) = Var(Y)(1 − ρ²).

**🔴 Q18. Why doesn't CUPED bias the treatment effect?**
> Write out the difference in adjusted means: the global centring constant X̄
> cancels exactly, leaving (Ȳ_T − Ȳ_C) − θ(X̄_T − X̄_C). Under randomization,
> E[X̄_T] = E[X̄_C], so the correction term has expectation zero and the
> estimator is unbiased. Intuitively: X was measured before we flipped the coin,
> so subtracting it can't remove a treatment effect — only shared noise.

**🟡 Q19. Why pooled θ instead of per-arm?**
> Under randomization X has the same distribution in both arms, so a pooled θ is
> a treatment-independent constant and the unbiasedness argument holds exactly.
> A per-arm θ is a function of that arm's outcomes, which reintroduces a small
> bias and adds noise for nothing. Pooling also halves the estimation error in θ.
> My API enforces it — `cuped_adjust` takes no group argument.

**🟡 Q20. Why centre X?**
> Purely for interpretability. Y − θX reduces variance just as well but shifts
> the metric off its scale, so you'd report an "adjusted revenue" of −$12.
> Centring preserves the mean exactly, so adjusted values stay in dollars. I have
> a unit test asserting mean preservation.

**🔴 Q21. Why 39% on revenue but only 6% on conversion?** *(the key CUPED
question — give both answers)*
> Surface answer: ρ(revenue, pre-period spend) is 0.625, so ρ² is 39%.
> ρ(converted, pre-period sessions) is only 0.251, so ρ² is 6%. Spending habits
> persist; a rare binary event doesn't.
>
> Deeper answer, from the law of total variance: for a binary outcome,
> Var(Y) = E[p(X)(1−p(X))] + Var(p(X)). The first term is irreducible Bernoulli
> noise; only the second is explainable. At p ≈ 3.5%, the Bernoulli term is about
> 0.0338 and dominates completely. So the ceiling on ρ² is low as a *mathematical
> property of rare binary outcomes*, not a failure of my covariate. No amount of
> covariate engineering fixes it — the right move is a more sensitive metric.

**🟡 Q22. Your CI narrowed 22% but variance dropped 39%. Why don't those match?**
> Variance and sample size scale with (1 − ρ²); standard error and CI width scale
> with its square root. √0.61 = 0.78, so the CI narrows by about 22%. Mixing
> those two up is a common slip.

**🔴 Q23. On real data CUPED gave you 0.04%. Was it a waste?**
> It was the most informative result in the project. ρ(two-week spend, prior-year
> history) was 0.0195 — two reasons. Spend is zero for about 99% of users in a
> two-week window, so you hit the same rare-event ceiling. And a year-long
> aggregate is a coarse predictor of a two-week outcome. Same method, same math;
> the covariate quality decides everything. The fix isn't a different technique,
> it's better data — a recent, same-cadence pre-period panel — or CUPAC, where
> you predict the outcome from all pre-experiment features and use the prediction
> as the covariate.

**🟡 Q24. What is CUPAC?**
> CUPED with a model instead of a single covariate — DoorDash's version. Train a
> predictor of the outcome from all pre-experiment features and use its
> prediction as X. CUPED with univariate θ is the special case. The only
> discipline required is that the model is fit on pre-experiment or control-only
> data so it stays treatment-independent.

**🟡 Q25. Could you use a post-experiment covariate?**
> No, and this is the one rule you must never break. A post-treatment variable
> can be affected by the treatment, so adjusting for it removes part of the
> effect you're trying to measure and biases the estimate. It's the same failure
> as conditioning on a post-treatment variable in causal inference — which I
> actually hit in a different form; see the AOV selection-bias story.

**🟡 Q26. What if the covariate is uncorrelated with the outcome?**
> θ ≈ 0 and the adjustment is a no-op — no gain, but no harm either. I have a
> unit test for exactly that. The only real cost is the tiny extra variance from
> estimating θ, which is negligible at these sample sizes.

**🟡 Q27. Does CUPED work for binary outcomes?**
> Yes. It's a linear adjustment with no distributional assumption on Y. The
> adjusted metric isn't 0/1 anymore, but we only ever use its mean and variance,
> and the CLT covers that. The gain is just small for rare outcomes, per Q21.

---

## Section 4 — Testing and decisions

**🟢 Q28. What's the difference between a success metric and a guardrail?**
> A success metric must *improve* for us to ship — it's the reason the change
> exists. A guardrail must *not degrade past a tolerance* — it's the thing we're
> worried the change might break. Different questions, and crucially different
> error costs, so they get different statistical treatment.

**🔴 Q29. Why one-sided tests for success metrics?**
> The decision is binary — ship or don't. "No effect" and "harm" lead to the same
> action, so they belong in the same null hypothesis. A two-sided test spends
> half its α detecting a direction I'd never act on differently. The fair
> criticism is that one-sided tests get abused to manufacture significance; the
> defence is that my direction is fixed by the decision rule and written into the
> MetricSpec before any data exists.

**🔴 Q30. Why non-inferiority instead of just checking p > 0.05?**
> Because absence of evidence isn't evidence of absence. "p = 0.4, so no harm" is
> a failure to detect, and it rewards underpowered experiments — run a tiny test
> and every guardrail passes. Non-inferiority makes harm the *null* and requires
> evidence to reject it, so the burden of proof sits on the side of safety. A
> small sample then gives you "inconclusive" rather than a false all-clear.

**🟡 Q31. Explain non-inferiority to a non-statistician.**
> We agreed beforehand how much order value we'd tolerate losing — 2%. The test
> asks: even in the worst case this data is compatible with, are we still inside
> that 2%? If yes, we've *proven* it's safe enough. If the whole plausible range
> is worse than 2%, we've proven it's not. And if the data spans both, we
> honestly don't know yet.

**🔴 Q32. Where does the margin come from?**
> The business, before the experiment. It's a statement about what degradation is
> worth the upside. In a real company finance or leadership sets it; an analyst
> choosing it after seeing the data is exactly the thing that makes the test
> meaningless. I said so explicitly in notebook 04 where I set a 10% margin on
> the Hillstrom spend guardrail.

**🔴 Q33. Why don't you apply BH correction to the guardrails?** *(the single
most likely follow-up on this project)*
> Because correction makes it harder to reject a null, and for a guardrail the
> null is "there is harm." So correcting makes it *harder to establish safety* —
> and worse, it creates a perverse incentive where an analyst who wants to ship
> is rewarded for adding more guardrails, since each one loosens the others.
>
> Structurally: correction exists to control Type I inflation. Guardrails fear
> Type II. Suppressing the error you don't fear at the cost of the one you do is
> backwards. So guardrails run uncorrected at full α, and their Type II risk is
> disclosed as power, with a floor that triggers INVESTIGATE instead of a silent
> pass. That framing is from Kohavi's book and Spotify's published guardrail
> framework.

**🟡 Q34. Why BH and not Bonferroni?**
> Success metrics are a discovery family — a few false leads are recoverable, so
> FDR is the right error rate: "at most 5% of the wins I declare are spurious."
> Bonferroni controls family-wise error, which is what you want when one false
> positive is catastrophic, and it loses power fast as m grows.

**🔴 Q35. Walk me through the BH procedure.**
> Sort the m p-values ascending. Find the largest k with p₍ₖ₎ ≤ (k/m)·q. Reject
> ranks 1 through k — all of them, including any whose own p-value exceeds its
> own threshold. That step-up property is what people get wrong. My unit test
> makes it concrete: p = [0.03, 0.04] at q = 0.05 has thresholds 0.025 and 0.05.
> 0.03 fails its own threshold, but 0.04 passes its own, and that rescues both.

**🔴 Q36. You only have two success metrics. Does BH actually do anything?**
> Honestly, no. At m = 2 the thresholds are 0.025 and 0.05, and in every scenario
> both p-values are far below either, so the correction changes no verdict. The
> value is that the structure is correct and scales — add eight secondary metrics
> and it starts doing real work. I'd rather say that than claim it mattered.

**🟡 Q37. Explain the verdicts.**
> Four of them. INVALID: the assignment split doesn't match what was intended,
> so the arms aren't comparable and no metric is reported at all. SHIP: the
> primary improved after BH correction and every guardrail established
> non-inferiority with adequate power. DO NOT SHIP: either the primary failed, or
> harm beyond a margin is statistically established. INVESTIGATE: the primary
> improved but at least one guardrail is inconclusive — usually because it was
> underpowered.

**🔴 Q37b. Why is INVALID separate from DO NOT SHIP?**
> Because they're claims about different things. DO NOT SHIP is a claim about
> the feature — we ran a valid experiment and learned the feature isn't good
> enough. INVALID is a claim about the experiment — we learned nothing, because
> the data can't support any claim at all. If I collapsed them, a stakeholder
> would hear "the feature failed" when the truth is "the pipeline failed," and
> they'd kill a feature that might be fine.

**🔴 Q38. What's the precedence order and why?**
> Harm first, then primary failure, then inconclusive, then ship. Established
> harm vetoes a ship *even when the primary improved* — that's the whole reason
> guardrails exist. My DO-NOT-SHIP scenario is exactly that case: conversion up
> and significant, revenue up, but AOV harm beyond the margin. Verdict: no ship.

**🔴 Q39. Your error-rate guardrail shows a statistically significant increase
and still passes. Explain.**
> Because the margin exists precisely because the business declared degradation
> below it acceptable. The true increase is 0.1pp against a 0.5pp tolerance. At
> 1.8 million users that's overwhelmingly significant and completely irrelevant.
> Blocking on significance rather than materiality would mean more traffic makes
> you *less* able to ship, which is absurd. The report labels it "significant but
> within-margin degradation (accepted cost)" so nothing is hidden.

**🔴 Q40. Your engine says INVESTIGATE when the guardrail actually passed. Isn't
that overconservative?** *(give both sides)*
> There's a real argument on both sides. Against my choice: the confidence bound
> already contains all the evidence — if it clears the margin, non-inferiority is
> established at level α, full stop, and gating on power arguably double-counts.
>
> For my choice: at 13% power, even a perfectly harmless treatment would come
> back inconclusive 87% of the time. So the pass reflects an unusually large
> observed effect, not an adequately sized design — the margin was never
> realistically testable at that n. And critically, I *flag* rather than *block*:
> the verdict is INVESTIGATE, not DO NOT SHIP. That's the proportionate response
> to a design concern as opposed to an evidence concern.

**🔴 Q41. Isn't reporting power post-hoc a known statistical sin?**
> The discredited thing is *observed power* — power computed at the observed
> effect size, which is a deterministic monotone function of the p-value and
> therefore carries zero information. This is different: I compute power at a
> fixed hypothetical alternative, zero true harm. That's a property of the
> design — margin, sample size, metric variance — not of the result. Change the
> observed effect and it barely moves; change the margin or n and it moves a lot.
>
> The fair caveat, which I'll give you before you ask: I plug in the realized SE
> rather than a pre-experiment variance estimate, so it's not purely a priori.
> The rigorous version computes it at design time from historical variance.

**🟡 Q42. What are ni_passed, inferior, and harm_detected?**
> Three different questions. `ni_passed`: the worst-case bound is inside the
> margin, so safety is established. `inferior`: even the bound nearest zero is
> outside the margin, so harm beyond tolerance is established — that's the ship
> blocker. `harm_detected`: the CI excludes zero on the harmful side, so there's
> *some* real harm, possibly trivial — informational only. The gap between
> ni_passed and inferior is INVESTIGATE.

**🟡 Q43. What does α = 0.05 actually mean here?**
> That if there were truly no improvement, 5% of experiments would still declare
> one. It's a convention from Fisher, not a law. The right value is a business
> decision about the relative cost of shipping something useless versus missing
> something good.

---

## Section 5 — The selection bias story

**🔴 Q44. Tell me about a hard bug you fixed.** *(your best answer — 90 seconds)*
> Midway through the project my SHIP demo wouldn't pass. I'd set the true
> order-value effect to exactly zero, and treatment AOV kept landing about 2%
> below control — across every seed. That silently consumed my entire 2%
> non-inferiority margin.
>
> The cause was my data generator. I had a single latent "user quality" factor
> driving both conversion propensity and order value. When treatment lifted
> conversion by 8%, the extra converters were marginal users — lower on that
> quality factor — and under a single factor, lower quality meant smaller
> baskets. So treatment's average order value fell with no causal effect on
> order value at all.
>
> That's selection bias from conditioning on a post-treatment variable: AOV is
> revenue *given converted*, and converted is affected by treatment, so
> conditioning on it destroys the comparability randomization bought. It's
> collider-stratification bias; the closely related classic is Lord's paradox.
>
> The fix was two independent latents — a frequency/monetary decomposition.
> One drives conversion and pre-period activity, the other drives basket size.
> Now a conversion lift shifts composition on frequency, not on basket value, so
> AOV is unbiased by construction. I re-ran every Phase 1 and Phase 2 gate
> afterwards and they all passed.
>
> And the lesson carried forward: guardrails belong on all-user metrics wherever
> possible. When I moved to real data, I deliberately used spend per *all* users
> rather than spend per converter, because its denominator is the set of
> randomized users and treatment can't move it.

**🔴 Q45. Why is AOV a dangerous guardrail metric in general?**
> Because its denominator is post-treatment. Any metric of the form "X per
> converter" conditions on conversion, which treatment affects. If the treatment
> changes *who* converts, the two converter pools aren't comparable, and you
> measure composition shift rather than a treatment effect. The safe version is
> revenue per *randomized user*, where the denominator is fixed by randomization.

**🟡 Q46. When would you still use a per-converter metric?**
> As a diagnostic, never as a ship gate — and always alongside the all-user
> version. If all-user revenue is up while AOV is down, the composition story is
> usually the explanation, and that's useful to know. You just can't treat it as
> a causal estimate.

---

## Section 6 — Validation and testing

**🟡 Q47. How do you know your code is correct?**
> Two tiers. Thirteen unit tests check function-level properties — θ recovers a
> known slope, BH matches hand-worked examples, my power formula agrees with
> statsmodels within 1%, the generator is reproducible. Then simulation gates
> check distributional properties over thousands of runs — that the design really
> has 80% power, that A/A really gives 5% false positives, that CUPED is really
> unbiased, that BH really controls FDR.

**🔴 Q48. Why both? Isn't one enough?**
> They test different kinds of claim. You can't unit-test "this design has 80%
> power" — it's a statement about repeated sampling, so you have to measure it
> over many simulated experiments. And you don't want to burn minutes of Monte
> Carlo to find out you wrote `norm.ppf(1-power)` instead of `norm.ppf(power)`.
> Fast deterministic tests for the inner loop, slow distributional gates for
> phase transitions.

**🔴 Q49. What's an A/A test and why does it matter?**
> Running the experiment with no true effect. If your pipeline is correct, it
> should declare significance about α of the time — 5%. If it's higher, something
> is broken: a variance mis-estimate, a peeking problem, a randomization bug. It's
> the cheapest possible check on a whole analysis stack. I run it in gate G1b and
> again with CUPED applied in G2c, to confirm CUPED doesn't inflate the false
> positive rate.

**🔴 Q50. Your G2a gate sounds subtle. Explain it.** *(a genuinely
distinguishing answer)*
> The naive check is to compare in-sample variance before and after adjustment.
> That's useless — when θ is estimated in-sample, the variance ratio equals
> 1 − r² as an *algebraic identity*. It's true no matter what the data is, so it
> proves nothing about the method.
>
> The non-tautological check is at the estimator level: run 1,000 independent
> simulations, compute the treatment effect each time with and without CUPED, and
> compare the variance of those two collections of estimates. That's a real
> statement about the sampling distribution.
>
> I also had to justify the sim count. A variance ratio from 200 sims has a
> Monte-Carlo standard error around 0.05, so my 0.10 tolerance would only be 2
> SEs and would false-alarm roughly one run in twenty. At 1,000 sims it's about
> 4 SEs. I still print the 200-sim value for reference.

**🟡 Q51. How do you avoid flaky statistical tests?**
> Three techniques, all used in my suite. Assert on algebraic identities rather
> than statistical outcomes wherever possible — I check the variance ratio to
> 1e-9 because it's an identity. Compare a sample against *itself* so the
> estimate is exactly zero and the p-value is exactly 0.5. And where you need a
> real effect, make it large — five standard errors — so the assertion is
> effectively deterministic rather than a coin flip.

**🟡 Q52. How did you pick your gate tolerances?**
> In Monte-Carlo standard error units, not arbitrary numbers. G2b's unbiasedness
> tolerance is literally `4 * std / sqrt(n_sims)`. A hardcoded tolerance either
> flakes or hides real bias depending on how lucky you got.

**🟡 Q53. Your G3c scenario gate uses fixed seeds. Isn't that fragile?**
> It's a regression test, not a statistical claim, and I say so in the docstring.
> The underlying rates — power, α, FDR — are what G3a, G1a and G3b validate over
> thousands of runs. G3c just pins that the three canonical scenarios still
> produce their intended verdicts, so a refactor can't silently change the
> decision logic.

---

## Section 7 — Code and architecture

**🟡 Q54. Walk me through the architecture.**
> Five layers, all dependencies pointing down. Config at the bottom as the single
> source of truth. A data layer with the simulator. A statistical core of pure
> functions — power, CUPED, the tests — none of which know anything about the
> business scenario. Above that one orchestrator, the decision engine, which is
> the only place statistics, business rules and metric definitions meet. Then
> three presentation surfaces: notebooks, a Streamlit dashboard, and a
> stakeholder memo. Plus verification cutting across everything.

**🔴 Q55. What's the best design decision in the codebase?**
> Making metrics declarative data rather than code. A MetricSpec declares how a
> metric is measured and judged — its kind, column, direction, margin, margin
> type. The engine walks the list and dispatches. The payoff was that I ran the
> whole engine on a completely different real-world dataset by writing three
> MetricSpec objects, with zero changes to engine code. If I'd written a function
> per metric, every new experiment would have meant editing the engine.

**🟡 Q56. Why dataclasses for results?**
> NonInferiorityResult carries eight fields including three booleans with
> genuinely different meanings. As a tuple that's unreadable — `r[5]`, which
> flag? As a dict it's untyped and typo-prone. Dataclasses give named, typed,
> IDE-completable fields and make the report renderer self-documenting.

**🟡 Q57. Why does `evaluate_experiment` return data instead of printing?**
> So the same computation can be rendered two ways — markdown in the notebooks,
> widgets in the dashboard. If verdict logic lived in a renderer, my notebook and
> my dashboard could disagree about the same experiment.

**🟡 Q58. Why relative margins against the control mean, not the pooled mean?**
> Because the pooled mean contains treatment's effect, so a relative margin
> anchored on it would move with the very thing being tested — the tolerance
> would shrink exactly when treatment did harm. Control is the pre-agreed,
> unaffected reference.

**🟡 Q59. Why does the engine raise if there isn't exactly one primary metric?**
> Zero primaries means there's no defined ship criterion; two means an ambiguous
> one. Real platforms enforce a single primary metric as a discipline, and I
> wanted that as a precondition rather than a convention someone can quietly
> violate.

**🟢 Q60. Why `math.ceil` on the sample size?**
> You can't recruit a fraction of a user, and rounding up keeps achieved power at
> or above target rather than just below. My unit test asserts power lands in
> [0.80, 0.81), which pins both the direction and the magnitude of the effect.

**🟡 Q61. What's the weakest thing in your codebase?**
> `sys.path.insert` at the top of the notebooks and dashboard instead of proper
> packaging. It's fragile, invisible to tooling, and breaks under some runners.
> The right fix is a pyproject.toml and `pip install -e .`. It's a pragmatic
> shortcut for a notebook-centric repo, and I wouldn't ship it in a library.

**🟡 Q62. Why did you write formulas by hand instead of using statsmodels?**
> Because the point of the project is demonstrating I understand them — a library
> call demonstrates I can read documentation. And it let me use statsmodels as an
> independent oracle instead: I cross-check against it in a unit test and a
> validation gate. That's stronger than either alone, because statsmodels uses a
> different parameterization — the arcsine-transformed Cohen's h — so agreement
> to within 1% is real confirmation rather than a tautology. In production I'd
> use the library.

**🟡 Q63. Your `test` field on MetricSpec says "proportion" or "mean" but both
take the same code path. Why does it exist?**
> It's reporting metadata. For a 0/1 column, a proportion test *is* a
> difference-in-means test — the mean is the rate and the variance is p(1−p). So
> the label tells the reader what kind of metric it is without changing the math.
> I'll admit it looks like a dispatch key and isn't; that's a fair readability
> criticism.

---

## Section 8 — Real data

**🟡 Q64. Describe the real dataset.**
> The MineThatData email dataset from Kevin Hillstrom, 2008: 64,000 customers
> randomized into men's email, women's email, or no email, with two weeks of
> follow-up on visit, conversion and spend. Each customer also carries `history`,
> their actual dollar spend in the prior year, which I used as the CUPED
> covariate.

**🟡 Q65. Why did you drop the men's email arm?**
> My engine models a single treatment-versus-control contrast. Three arms would
> need their own multiplicity treatment across arms as well as across metrics,
> and it would have muddied the demonstration without adding anything. I called
> it out as an explicit design decision in the notebook rather than quietly
> filtering.

**🔴 Q66. Your real-data verdict was INVESTIGATE even though everything looked
good. Explain.**
> Both success metrics improved decisively — conversion +0.31pp on a 0.57% base,
> visits +4.5pp, both BH-significant. And the spend guardrail actually *cleared*
> its margin: the email raised spend, and even the worst-case bound sat above
> the −$0.065 tolerance. But the guardrail's power was 13%. At about 21,000 users
> per arm, with spend zero for 99% of users and a control standard deviation of
> $11.6 against a $0.65 mean, a $0.065 margin was never realistically testable.
> The pass was driven by a large positive effect, not by an adequate design.
> That's the engine telling me the guardrail *design* was broken, which is an
> honest and very common real-world outcome.

**🟡 Q67. How much code did you change to run on real data?**
> None in the engine. I wrote three MetricSpec objects and added a `group`
> column. That was the test of whether the abstraction was right.

**🟡 Q68. What would you request from a real company to do this better?**
> Per-user pre-period panels — spend, visits and orders in the four to eight
> weeks immediately before the experiment. `history` covers a whole year, and a
> recent same-cadence window would correlate far better with a two-week outcome.
> Richer covariates for CUPAC: recency, frequency, channel and category affinity.
> And a margin set by the business before launch, with the guardrail's power
> reviewed at design time — so an underpowered guardrail gets caught before the
> experiment runs, not after.

---

## Section 9 — Broader A/B testing knowledge

These go beyond your code. Interviewers use the project as a springboard.

**🟡 Q69. What is a sample ratio mismatch and why does it matter?**
> When the observed split differs significantly from the intended one. You test
> it with a chi-square goodness of fit on the two arm counts, one degree of
> freedom. It matters because it means assignment, logging, bot filtering or the
> analysis join is broken — and the users who went missing are almost never a
> random subset, so the arms are confounded and every metric in the experiment
> is meaningless. It's the standard first gate in any real platform, and it's
> the first thing my engine runs.

**🔴 Q69b. Your α is 0.05 everywhere but your SRM gate uses 0.0005. Justify
that.** *(the most likely follow-up on the SRM work)*
> Because the SRM check runs on *every* experiment, not once per decision. At
> 0.05 I'd throw away one perfectly healthy experiment in twenty, and each false
> alarm costs an engineering investigation that finds nothing — which is exactly
> how a check gets ignored and then deleted. Meanwhile a genuine SRM is orders
> of magnitude more extreme: my 49/51 demo lands at p = 6e-14. So the strict
> threshold costs essentially no detection power while nearly eliminating false
> alarms. My validation gate measures both halves — 0.00035 false-alarm rate
> over 20,000 fair-coin simulations, and 100% detection of a 49/51 bug.
>
> The general principle is that a screening test which runs constantly should
> get its threshold from its false-alarm budget, not from convention.

**🔴 Q69c. Why report no metrics at all on an SRM? Isn't that hiding data?**
> It's refusing to supply something that can only be misused. If I print the
> metrics next to "by the way, assignment is broken," somebody will quote the
> metrics in a deck and the caveat will fall off. There is exactly one correct
> response to an SRM — fix the pipeline and re-run — so the engine declines to
> give anyone an alternative. The raw data is obviously still there; what's
> withheld is the *analysis*, which is genuinely invalid.

**🟡 Q70. What's the peeking problem?**
> Checking results repeatedly and stopping when you see significance. Each look
> is another chance to cross the threshold, so the real false-positive rate is
> far above α — with frequent monitoring it can reach 20–30%. Fixed-horizon
> analysis is only valid if you look once, at the end.

**🟡 Q71. How do you fix peeking?**
> Group-sequential boundaries like O'Brien-Fleming, which spend α across planned
> interim looks. Or always-valid inference — mSPRT, confidence sequences — which
> gives you a p-value valid at every moment, at the cost of some power. Both are
> in my "what I'd add next" list.

**🟡 Q72. What's a novelty effect?**
> Users react to a change because it's new, not because it's better, and the
> effect decays. You detect it by plotting the effect over time or comparing new
> versus returning users. It's why short experiments can overstate lifts, and why
> a holdback group is useful.

**🟡 Q73. What's Simpson's paradox in an A/B context?**
> An aggregate effect reverses within every segment — usually caused by unequal
> segment mixes between arms, which itself is usually a sign of a randomization
> or ramp problem. It's another reason to check SRM and segment balance before
> trusting an aggregate.

**🟡 Q74. What's network interference?**
> When one user's treatment affects another's outcome — social features,
> marketplaces, two-sided platforms. It violates SUTVA, so the independence
> assumption behind every standard error in my project breaks. The fix is
> cluster randomization, or switchback designs in marketplaces.

**🟡 Q75. How would you handle ratio metrics like clicks per session?**
> The unit of analysis differs from the unit of randomization, so you can't treat
> sessions as independent. Either aggregate to the user level, or use the delta
> method to get a correct variance for the ratio, with clustering by user.

**🟡 Q76. What's a holdout / holdback?**
> A slice of users kept on control long after the ship, to measure long-term and
> cumulative effects — decay, learning, and the combined impact of many shipped
> changes that individually looked positive.

**🟡 Q77. How do you pick a primary metric?**
> It should be sensitive enough to move in a reasonable experiment, aligned with
> long-term value rather than just short-term clicks, hard to game, and agreed
> before the experiment. The hard part is that long-term value metrics are
> usually insensitive and sensitive metrics are usually gameable — that's the
> classic OEC problem.

**🟡 Q78. What's an OEC?**
> Overall Evaluation Criterion — a single metric, sometimes a weighted
> combination, that captures what the business actually wants. The point of
> committing to one is to prevent metric-shopping after the fact.

**🟡 Q79. Your experiment is significant but the effect is tiny. Ship it?**
> Depends entirely on cost. Statistical significance says the effect is real;
> it says nothing about whether it's worth the engineering, maintenance and
> complexity cost. This is exactly why my guardrails have margins — a declared
> materiality threshold — and arguably my success metrics should have them too.
> That's on my list of weaknesses.

**🟡 Q80. How long should an experiment run, minimum?**
> At least one full business cycle, usually a week, and typically two — so you
> capture weekday/weekend composition and don't measure a Tuesday-shaped
> population. Even if you hit your sample size in three days, you stop at the
> week boundary. My 14-day figure comes from sample size, but the weekly-cycle
> argument would set a floor independently.

---

## Section 10 — Curveballs and pressure questions

**🔴 Q81. This is all simulated. Why should I believe any of it?**
> You shouldn't believe the *findings* — they're about a fictional checkout flow.
> You should evaluate the *method*, and simulation is the only way to validate a
> method, because it's the only setting where you know the true answer and can
> check that the machinery recovers it at the advertised rate. Then I ran the
> same engine unchanged on real data, where the results were noticeably less
> flattering — 0.04% CUPED gain instead of 39%, and an INVESTIGATE verdict
> instead of a clean SHIP. If I were optimizing for a good-looking result, those
> wouldn't be in the repo.

**🔴 Q82. What's the most likely way this engine gives a wrong answer in
production?**
> Two ways, in order. First, a data quality failure it can't see — an SRM, a
> logging bug, a broken assignment. The engine assumes the arms are comparable
> and has no check for it. Second, peeking: someone runs it daily and acts on the
> first green result, which inflates the false positive rate far past 5%. Both
> are data-and-process failures, not statistical ones, which is exactly why
> they're dangerous — the math keeps looking correct.

**🔴 Q83. A stakeholder says your INVESTIGATE verdict is unhelpful and they need
a yes or no. What do you say?**
> That INVESTIGATE *is* an answer — it says the evidence doesn't yet support
> either claim, and pretending otherwise would mean making up confidence I don't
> have. Then I'd give them the actionable version, which is what my memo does:
> phase the rollout to 25%, then 50%, then 100%, keep capturing the upside, and
> define an automatic pause rule up front if order value breaches tolerance. The
> answer to "we don't know yet" is usually "here's how we find out while not
> losing money," not "no."

**🔴 Q84. If you had to delete half this project, what would go?**
> The dashboard and the plotting module. They're presentation, and the
> intellectual content is in the statistical core, the decision engine and the
> validation suite. I'd keep the notebooks because they're the narrative and the
> reproducible record — and I'd keep the memo, because translating a verdict into
> a business recommendation is the part most analysts skip.

**🔴 Q85. What's the weakest claim in your README?**
> The $660k annualized revenue projection. It's +$0.18 per user times 10,000
> users a day times 365, and it assumes the measured effect persists across
> seasons and doesn't decay after novelty. The memo labels it as an
> if-the-lift-holds extrapolation, which is the right caveat, but it's still the
> number a stakeholder would quote back at me in six months.

**🔴 Q86. Someone tells you CUPED is just a fancy name for regression
adjustment. Are they right?**
> Substantially, yes. With a single covariate it's algebraically equivalent to
> including that covariate in a regression of the outcome on treatment. The
> distinctive contributions are the framing — insist the covariate is
> pre-experiment, so it's guaranteed treatment-independent rather than
> hopefully-so — and the operational packaging for online platforms. I'd rather
> agree with the substance than defend a branding claim.

**🔴 Q87. Your power floor is 80%. Why not 90%?**
> Convention, and it's a business choice I inherited rather than derived. 80%
> means accepting a 20% chance of missing a real effect. The principled version
> sets it from the relative costs of the two errors — if shipping harm is
> catastrophic, you want a much higher guardrail power floor, and you'd have to
> pay for it in traffic. My AOV finding is exactly what that payment looks like:
> going from 20% to 80% power on that guardrail costs about nine times the users.

**🔴 Q88. Is there anything in this project you'd now say was a mistake?**
> Two, both since fixed. I built CUPED, proved it works, and then ran the
> verdicts on raw metrics — demonstrating a capability and not using it is
> exactly the gap between a portfolio piece and a working system. And I had no
> SRM check, which meant the engine would confidently analyse an experiment
> whose randomization was broken. What's still open is sequential testing, and
> I'd rather name that than pretend the project is finished.

**🔴 Q88b. Adding CUPED made one of your p-values worse. Doesn't that mean it
hurt?** *(a great question to be ready for)*
> No — and it's my favourite result in the project. On that seed, treatment
> happened to draw users with $1.70 more pre-experiment spend, about 1.4
> standard errors of chance imbalance. θ times that imbalance is $0.073, and the
> revenue estimate duly fell from +$0.182 to +$0.113. So CUPED removed a chance
> imbalance that was *inflating* the raw estimate — the raw number was partly
> luck. That's the second thing CUPED does alongside variance reduction: it
> corrects covariate imbalance. The standard error genuinely fell by 22%; the
> point estimate just happened to fall further on this particular draw. Over 400
> simulations the CUPED and raw estimators agree to within 0.06 Monte Carlo
> standard errors, which is the unbiasedness check that matters.

**🔴 Q89. What don't you know about experimentation that you wish you did?**
> Practically, running at scale: the infrastructure side — assignment services,
> metric pipelines, how you keep a metric definition stable for a year. And on
> the statistics side, I've only read about sequential methods, I haven't
> implemented mSPRT or group-sequential boundaries, and I know that's the next
> layer between what I built and what a production platform does.

**🟡 Q90. How long did this take and what took longest?**
> The statistical core is small — CUPED is 51 lines. What took the time was
> validation and the debugging that came out of it: building the simulation gates,
> and then the selection-bias investigation, which meant redesigning the data
> generator and re-running every earlier gate to confirm nothing regressed.

---

## Section 11 — Rapid fire (know these in one sentence)

| Q | A |
|---|---|
| Sample size per arm? | 70,229 (140,458 total, 14 days at 10k/day) |
| Baseline / MDE? | 3.5% conversion, +8% relative (Δ = 0.28pp) |
| CUPED formula? | Y − θ(X − X̄), θ = Cov(Y,X)/Var(X) |
| CUPED variance? | Var(Y)(1 − ρ²) |
| CUPED on revenue? | ρ = 0.625 → 39% variance reduction, 22% CI narrowing |
| CUPED on conversion? | ρ = 0.251 → 6.3% |
| CUPED on real data? | ρ = 0.0195 → 0.038% |
| Guardrail power formula? | Φ(m/SE − z_{1−α}) |
| AOV guardrail power at 70k/arm? | 20% |
| Users needed for 80% AOV power? | ~650k/arm (~9×); project uses 900k for ~91% |
| BH rule? | Largest k with p₍ₖ₎ ≤ (k/m)q, reject 1..k |
| Why no BH on guardrails? | Correction fights Type I; guardrails fear Type II |
| Verdict precedence? | harm → primary fail → inconclusive → ship |
| Real dataset? | Hillstrom MineThatData, 64k customers, 2008 |
| Real-data verdict? | INVESTIGATE (guardrail power 13%) |
| Halve the MDE? | 4× the sample size |
| Rule of thumb? | n ≈ 16p(1−p)/Δ² |
| Number of unit tests? | 26, all passing, ~3 seconds |
| SRM test? | Chi-square goodness of fit, 1 df, gated at p < 0.0005 |
| Why 0.0005? | Runs on every experiment; 0.05 would discard 1 healthy test in 20 |
| SRM gate G3d? | 0.00035 false-alarm rate, 100% detection of 49/51 |
| Verdicts? | INVALID, SHIP, DO NOT SHIP, INVESTIGATE |
| CUPED in the engine? | Both success metrics, covariate `pre_exp_spend` |
| Why no CUPED on AOV? | Converters-only is post-treatment: +$0.70 bias vs a $1.18 margin |
| Biggest remaining gap? | No sequential testing (peeking) |
