
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

**Led to:** decision **D7** (see `modelling_decisions.md`): the closure axiom is added to every drink, not only to `glass_of_lemon_soda`, because the same problem affects every definition with `only` (Mocktail, VeganDrink).

**Versions:**
1. Before: Git tag `s1-before-mocktails-missing` (file `KnowledgeBase-Drink_V1.ttl` at that tag)
2. After: Git tag `s1-after-closure-axioms` (file `KnowledgeBase-Drink_V2_closure.ttl` at that tag, with the closure axiom)

**For the comparison with the second formalism:** Datalog uses the **Closed World Assumption**: what is not written is false. There, this problem does not exist and no closure axiom is needed.

## Ideas to test (not yet observed)

These are problems we expect, but the reasoner has not shown them yet. An idea becomes a real discovery (S2, S3, ...) only if we build the model the simple way first and the problem really appears.

### 1. "Likes gin, gets lemon juice?"

**The idea:** when a customer likes an ingredient, the property chain `likesIngredient o hasFlavour` lets the reasoner conclude that the customer likes ALL the flavours of that ingredient. Gin has juniper, citrus and herbal flavours, so a customer who likes gin would also "like" citrus, and the reasoner might suggest drinks that share only this secondary flavour (for example something with lemon juice).

**How to test it:** after building flavours and preferences, give a customer `likesIngredient gin` and check which drinks the reasoner suggests.

**Possible fix: `hasSignatureFlavour`**. A second property, next to `hasFlavour`, that links an ingredient only to its MOST TYPICAL flavour, the one that makes it recognisable:
1. `gin hasFlavour juniper`, `gin hasFlavour citrus`, `gin hasFlavour herbal` (all its flavours)
2. `gin hasSignatureFlavour juniper` (only the typical one)

Preferences then follow the signature flavour: liking gin means liking juniper, not citrus. A zero gin (also juniper) still matches, a lemon juice no longer does. We could make `hasSignatureFlavour` a sub property of `hasFlavour`, so every signature flavour is automatically also a normal flavour. The fix works only if the preference chain changes too: it must become `likesIngredient o hasSignatureFlavour`. If the chain still uses `hasFlavour`, the customer still "likes" citrus and nothing is fixed.

### 2. "Does adding soda water make a cocktail plain?"

**Date:** 17 November 2026

**Status:** a worked logical example and a proposed reasoner test, not an observed reasoner result. The flavour propagation chain is still planned (D10), so there are no before/after ontology tags for this experiment yet.

**The assumption to test:** the candidate label `plain` for soda water, cream and egg white describes a neutral ingredient. With unrestricted flavour propagation, that label would also transfer to any cocktail containing one of them.

**Test setup:** create a test drink with `campari`, `lemon_juice` and `soda_water`. Campari supplies `bitter` and `herbal`; lemon juice supplies `sour` and `citrus`. Temporarily give soda water `hasFlavour plain` in a separate test ontology, then add the chain `hasIngredient o hasFlavour ⊑ hasFlavour`. Compare the inferred flavours with and without soda water.

**Expected result:** without soda water, the drink inherits `bitter`, `herbal`, `sour` and `citrus`. Adding soda water with the candidate label makes the reasoner infer `hasFlavour plain` as well, while retaining all the other labels. The chain transfers every recorded label; it does not assess the overall taste or dilution.

**Why this matters:** "contains a neutral ingredient" does not mean "the whole drink tastes plain". In this example, interpreting the inherited label as the overall taste would be misleading.

**Decision:** we decided to **exclude `plain`** because it does not make sense as a flavour of a drink under this model. The current CSVs already reflect this choice: `plain` is absent from `flavours.csv`, and soda water, cream and egg white have no recorded flavour labels in `ingredients.csv`. Once the chain is implemented, they will contribute no recorded flavour labels, while the drink still inherits the flavours of its other ingredients. Empty cells do not assert that these ingredients have no possible flavours under the Open World Assumption.

**Follow-up check:** when D10 is implemented, run the test in a separate ontology with the temporary `plain` assignment, then repeat without that assignment and check that `hasFlavour plain` is no longer inferred. The choice and its limits are documented in D9 and D10 of `modelling_decisions.md`.
