# Modelling decisions

A modelling decision is a choice where the logic allows more than one valid model. For each one we write the options, what we chose, why, and an example. These go into the report as **modelling assumptions**.

## D1. The four top classes are disjoint

**Date:** 11 November 2026

**Question:** can something be, for example, both a Drink and a Person?

**Choice:** no. `Drink`, `Ingredient`, `Flavour` and `Person` are pairwise **disjoint**.

**In DL:** `Drink ⊓ Person ⊑ ⊥` (and the same for the other 5 pairs)

**Why:**
1. Because of the **Open World Assumption**, the reasoner treats anything we have not forbidden as possible. Without this axiom, something could be a drink and a person at the same time.
2. With it, the reasoner catches our mistakes: if an individual ends up in two of these classes, the ontology becomes **inconsistent**.

**Example:** an individual `test` with types `Drink` and `Ingredient` makes the ontology inconsistent.

## D2. A simple drink is a drink with one ingredient

**Date:** 11 November 2026

**Question:** lemon soda can be drunk on its own (a drink) and used in a gin lemon (an ingredient). How do we model it?

**Options:**

| Option | Idea | Problem |
| :- | :- | :- |
| A | Two individuals: the ingredient and the drink | One more individual for each simple drink |
| B | One individual that is both Drink and Ingredient | We must drop the disjointness of Drink and Ingredient; the drink has no ingredients, so it behaves differently in the questions about ingredients |

**Choice:** Option A.

**Example:**
1. `lemon_soda`: type `Ingredient` (the liquid in the bottle)
2. `glass_of_lemon_soda`: type `Drink`, with `hasIngredient lemon_soda`

**Why:**
1. We keep the disjointness of Drink and Ingredient (D1).
2. Every drink works the same way: a drink always has ingredients.
3. When we add flavours (planned), a property chain `hasIngredient o hasFlavour` will give `glass_of_lemon_soda` the flavours of `lemon_soda` automatically.
4. Being an ingredient is a **role**: something a thing does in relation to a drink, not what the thing is.

## D3. Drink categories are inferred from the ingredients

**Date:** 11 November 2026

**Question:** do we write by hand that a drink (for example Long Island) is alcoholic, or do we let the reasoner find it?

**Choice:** we write by hand only facts about **ingredients** (gin is an `AlcoholicIngredient`, tonic water is a `NonAlcoholicIngredient`). Drink categories such as `AlcoholicDrink` or `Mocktail` are never asserted: the reasoner **infers** them.

**In OWL:**
1. Ingredient types are **primitive classes**: we assert their members, with `SubClass Of` (necessary conditions only).
2. Drink types are **defined classes**: the reasoner classifies the drinks, with `Equivalent To` (necessary and sufficient conditions). Example: `AlcoholicDrink` Equivalent To `Drink and (hasIngredient some AlcoholicIngredient)`.

**Example (Long Island is planned, not yet in the KB):** Long Island has `hasIngredient vodka`, `hasIngredient white_rum`, `hasIngredient gin`, ... and vodka is an `AlcoholicIngredient`, so the reasoner concludes that Long Island is an `AlcoholicDrink`.

**Why:**
1. One source of truth: "alcoholic or not" is stored only on the ingredient, so drink and ingredient can never disagree.
2. New drinks are classified automatically.
3. The reasoner can make discoveries we did not expect, for example a "virgin" drink that turns out to be alcoholic because of one ingredient.

## D4. "Alcoholic" is a yes/no property

**Date:** 11 November 2026

**Question:** does the amount of alcohol matter?

**Choice:** no. An ingredient is either alcoholic or not, and one alcoholic ingredient is enough to make a drink alcoholic. We ignore quantities and alcohol percentages.

**Example:** a drink with a few drops of angostura bitters is an `AlcoholicDrink`, exactly like a Long Island.

**Why:** it keeps the model simple, and quantities are hard to reason about in OWL. This is a simplification of the real world, and we state it as a limit of the model.

## D5. One generic individual per ingredient type, no brands

**Date:** 11 November 2026

**Question:** do we model brands (Bombay, Tanqueray, ...)? And if not, do we still need a class like `Gin`?

**Choice:**
1. No brands: none of our competency questions needs them. The competency questions decide what goes into the KB.
2. Each ingredient type stays a **class** (`Gin`, `Vodka`, ...) and gets **one generic individual** used in the recipes (`gin` of type `Gin`, `vodka` of type `Vodka`).

**Example:**
1. `gin`: type `Gin`
2. `vodka`: type `Vodka`
3. `Gin` and `Vodka` are disjoint (sibling classes under `Spirit`)

**Why we keep the classes:** disjoint classes make the individuals different. OWL has no **unique name assumption**: without more information, `gin` and `vodka` could be two names for the same object. But `gin` is a `Gin`, `vodka` is a `Vodka`, and the two classes are disjoint, so the reasoner knows they are two different objects. This way `StrongDrink` (planned: at least 2 spirits) will work for a drink like the Vesper (gin, vodka, Lillet) without an extra Different Individuals axiom for the spirits.

## D6. Whole ingredient classes are plant-based

**Date:** 11 November 2026

**Question:** to answer "Which drinks are vegan?", the reasoner must know which ingredients are not animal products. Do we mark each ingredient one by one, or whole classes?

**Choice:**
1. When ALL members of a class are plant-based, we say it once for the class: `Spirit`, `FortifiedWine`, `Bitters`, `CarbonatedMixer`, `Juice`, `Herb` and `NonAlcoholicSpirit` are subclasses of `PlantBased`.
2. `Liqueur` and `Sweetener` are not, because they have members of both kinds (Baileys contains cream; honey is an animal product). Their individuals get `PlantBased` or `AnimalProduct` one by one.

**In DL:** `Spirit ⊑ PlantBased`, and `PlantBased ⊓ AnimalProduct ⊑ ⊥`

**Example:** `gin` is a `Gin`, and `Gin ⊑ Spirit ⊑ PlantBased`, so the reasoner concludes that `gin` is plant-based and therefore NOT an `AnimalProduct`. We never write this on `gin` itself.

**Why:**
1. An axiom on a class is inherited by all its members: we write it once, and it holds for every ingredient we add later.
2. Under the **Open World Assumption**, "not an animal product" must be derivable. The positive fact (PlantBased) plus the disjointness gives the negative one.

**Simplification (limit of the model):** in reality, some wines and spirits are clarified with animal products (for example gelatine or egg white). We ignore this and treat these classes as fully plant-based.

## D7. Every drink gets a closure axiom

**Date:** 11 November 2026

**Origin:** decided after discovery **S1** ("Where are the mocktails?", see `discoveries.md`). In V1, `glass_of_lemon_soda` was not classified as a `Mocktail` because of the **Open World Assumption**. We fixed it with a closure axiom, and then realised that the same problem would happen again with every definition that uses `only`.

**Question:** do we add a closure axiom only where we saw the problem, or to every drink?

**Choice:** every drink gets a **closure axiom** that lists ALL its ingredients, next to its property assertions.

**In OWL:** for each drink, the property assertions say what it HAS, and one extra type says it has NOTHING ELSE:
1. Property assertions: `hasIngredient gin`, `hasIngredient tonic_water`
2. Type (closure): `hasIngredient only {gin, tonic_water}`

**Example:**
1. `gin_tonic`: `hasIngredient only {gin, tonic_water}`
2. `gin_lemon`: `hasIngredient only {gin, lemon_soda}`
3. `glass_of_lemon_soda`: `hasIngredient only {lemon_soda}`

**Why:**
1. Every definition with `only` needs to know that the list of ingredients is complete: `Mocktail` (all ingredients non-alcoholic) and `VeganDrink` (no animal ingredient) both depend on it.
2. Definitions with `some` (such as `AlcoholicDrink`) do not need it, but the closure does not break them: it only adds information, so the drinks that were alcoholic stay alcoholic.
3. Applying the rule to all drinks keeps the KB uniform: every drink is described in the same way.

**Cost:** each ingredient is written twice (assertion and closure). With 20 to 30 drinks this is repetitive, so it is a good candidate for Cellfie or a script.

## D8. `hasIngredient` has a domain, `hasFlavour` will not

**Date:** 11 November 2026

**Question:** do we give a domain and a range to our properties?

**Options:**

| Option | Idea | Problem |
| :- | :- | :- |
| A | No domain and no range | The reasoner cannot catch a property used on the wrong kind of thing |
| B | Domain and range on every property | A domain that is too narrow gives wrong types to individuals |
| C | Decide for each property | We must think about every property |

**Choice:** Option C.
1. `hasIngredient`: domain `Drink`, range `Ingredient`.
2. `hasFlavour` (planned): range `Flavour`, no domain.

**In DL:** `∃hasIngredient.⊤ ⊑ Drink` and `⊤ ⊑ ∀hasIngredient.Ingredient`

**Example:** if someone writes `gin hasIngredient juniper` by mistake, the reasoner concludes that `gin` is a `Drink`. But `gin` is also an `Ingredient`, and the two classes are disjoint (D1), so the ontology becomes inconsistent and we see the mistake.

**Why:**
1. A domain is not a check: it is an inference rule. It does not forbid anything, it adds a type to whatever uses the property.
2. For `hasIngredient` this is what we want: only drinks have ingredients (D2), and together with D1 a wrong use becomes a visible inconsistency.
3. For `hasFlavour` a domain of `Drink` would be wrong: ingredients have flavours too (`gin hasFlavour juniper`), so every ingredient with a flavour would become a `Drink` and break the KB.

## D9. Flavours are qualitative, overlapping labels

**Date:** 17 November 2026

**Question:** are flavours exclusive categories, and what does a flavour label describe?

**Choice:** `sweet`, `sour`, `bitter`, `citrus`, `fruity` and `herbal` are **individuals of `Flavour`**, as recorded in `flavours.csv`. An ingredient can have several `hasFlavour` assertions. These labels can occur together: `hasFlavour` is not functional, and having one flavour does not exclude another.

**Example:** `lemon_juice` has both `sour` and `citrus`. If tonic water is assigned both `bitter` and `sweet`, both labels apply together. In the current `ingredients.csv`, `tonic_water` is assigned only `bitter`; the two-label tonic-water example is illustrative.

**Simplification (limit of the model):** flavour descriptions are manually assigned qualitative labels. We do not represent intensity, quantities, dominant flavours, or changes caused by mixing ingredients. The labels describe our simplified model rather than a complete sensory profile.

**Why we exclude `plain`:** the candidate label meant "contains a neutral ingredient" when propagated to a drink, but could easily be read as "the whole drink tastes plain". Those are different claims. A cocktail containing cream, egg white or soda water can still have strong flavours. We decided to exclude `plain` because it does not make sense as a drink flavour under unrestricted propagation (D10), and we do not need a separate neutral-ingredient label for our questions.

**Current data:** `plain` is absent from `flavours.csv`, and cream, egg white and soda water have empty `hasFlavour` cells in `ingredients.csv`. An empty cell means **no flavour label is recorded**; under the Open World Assumption, it does not prove that the ingredient has no flavours.

**Related experiment:** "Does adding soda water make a cocktail plain?" in `discoveries.md` records the proposed test and the reason for this decision.

## D10. Drinks inherit every recorded flavour of their ingredients

**Date:** 17 November 2026

**Question:** which ingredient flavours should a drink inherit, and how do we classify drinks by flavour?

**Choice:** every recorded flavour of every ingredient transfers to the drink, using the property chain introduced in D2:

```text
hasIngredient o hasFlavour ⊑ hasFlavour
```

If a drink has an ingredient and that ingredient has a flavour, the drink has that flavour. This is a property-chain inference supported by [OWL 2 object subproperty axioms](https://www.w3.org/TR/owl2-syntax/#Object_Subproperties).

**Example:** a drink containing `lemon_juice` inherits both `sour` and `citrus`. A drink containing `tonic_water` inherits `bitter` from the current CSV. If `sweet` is also recorded for tonic water, the same chain makes the drink inherit both `bitter` and `sweet`.

**Flavour classes (Manchester syntax):**

```text
SweetDrink EquivalentTo Drink and (hasFlavour value sweet)

BitterDrink EquivalentTo Drink and (hasFlavour value bitter)

HerbalDrink EquivalentTo Drink and (hasFlavour value herbal)
```

Here, `value sweet` refers to the **flavour individual** `sweet` in `flavours.csv`. It means that the drink has a `hasFlavour` link to that individual; it does not refer to a class named `sweet`. See [OWL 2 individual value restrictions](https://www.w3.org/TR/owl2-syntax/#Individual_Value_Restriction).

**Overlapping classes:** these drink classes are not disjoint. The same drink can be a `SweetDrink`, a `BitterDrink` and a `HerbalDrink` if its ingredients supply all three labels.

**Simplification (limit of the model):** even a small contribution from one ingredient is sufficient. The reasoner does not calculate the dominant taste, dilution, or whether one flavour masks another. Excluding `plain` (D9) avoids treating the presence of a neutral ingredient as a flavour of the whole drink.

**Status:** the property chain and flavour-based drink classes are **planned**; they are not yet present in `KnowledgeBase-Drink.ttl`. The CSVs provide the ingredient flavour assignments for their implementation.
