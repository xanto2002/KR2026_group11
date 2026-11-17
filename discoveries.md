
# Discoveries

Surprises from the reasoner: what we expected, what happened, why, and how we fixed it. This is the material for the "discoveries" part of the report. Each entry points to the ontology versions before and after the fix.

## S1. "Where are the mocktails?"

**Date:** 11 November 2026

**What we expected:** `glass_of_lemon_soda` (type `Drink`, `hasIngredient lemon_soda`, and `lemon_soda` is a `CarbonatedMixer`, so non-alcoholic) should be classified as a `Mocktail`.

**Definition used:** `Mocktail` Equivalent To `Drink and (hasIngredient only NonAlcoholicIngredient)`

**What happened:** the DL Query `Mocktail` (Instances) returned no individuals.

**Why:** the **Open World Assumption**. What is not written is unknown, not false. The reasoner knows that the drink has `lemon_soda`, but nobody said that this is its only ingredient. There is a possible model where the drink also has an unknown alcoholic ingredient, so the reasoner cannot conclude that ALL its ingredients are non-alcoholic.

**Contrast with `some`:** `AlcoholicDrink` (`hasIngredient some AlcoholicIngredient`) worked at once for `gin_tonic` and `gin_lemon`, because one known alcoholic ingredient is enough, and adding more ingredients can never remove it. `only` instead needs the list of ingredients to be complete.

| | `some` (∃) | `only` (∀) |
| :- | :- | :- |
| Checks | at least one ingredient of the type | every ingredient of the type |
| Works under the OWA | yes, one known example is enough | no, it needs a closed list |

**Fix:** a **closure axiom** that says the list is complete. On `glass_of_lemon_soda`, Types: `hasIngredient only {lemon_soda}`. The property assertion `hasIngredient lemon_soda` stays: the assertion says the drink HAS lemon soda, the closure says it has NOTHING ELSE. `{lemon_soda}` is a **nominal**: the class whose only member is `lemon_soda`.

**Result after the fix:** the DL Query `Mocktail` (Instances) returns `glass_of_lemon_soda`. With the closure, every ingredient of the drink is `lemon_soda`, `lemon_soda` is a `CarbonatedMixer`, so a `NonAlcoholicIngredient`: all its ingredients are non-alcoholic, and the drink is a `Mocktail`.

**Led to:** decision **D7** (see `modelling_decisions.md`): the closure axiom is added to every drink, not only to `glass_of_lemon_soda`, because the same problem affects every definition with `only` (Mocktail now, VeganDrink when we add it).

**Versions:**
1. Before: Git tag `s1-before-mocktails-missing` (file `KnowledgeBase-Drink_V1.ttl` at that tag)
2. After: Git tag `s1-after-closure-axioms` (file `KnowledgeBase-Drink_V2_closure.ttl` at that tag, with the closure axiom)

**For the comparison with the second formalism:** Datalog uses the **Closed World Assumption**: what is not written is false. There, this problem does not exist and no closure axiom is needed.
