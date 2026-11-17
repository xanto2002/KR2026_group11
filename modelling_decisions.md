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

**Example:** Long Island has `hasIngredient vodka`, `hasIngredient white_rum`, `hasIngredient gin`, ... and vodka is an `AlcoholicIngredient`, so the reasoner concludes that Long Island is an `AlcoholicDrink`.

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

**Why we keep the classes:** disjoint classes make the individuals different. OWL has no **unique name assumption**: without more information, `gin` and `vodka` could be two names for the same object. But `gin` is a `Gin`, `vodka` is a `Vodka`, and the two classes are disjoint, so the reasoner knows they are two different objects. This way `StrongDrink` (at least 2 spirits) works for a drink like the Vesper (gin, vodka, Lillet) without an extra Different Individuals axiom for the spirits.

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
