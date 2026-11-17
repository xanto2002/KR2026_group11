# KR2026-group11
Group project for the Knowledge Representation course (VU Amsterdam, 2026). Design of a knowledge base in OWL, reasoning experiments, and a comparison with a second formalism. Work in progress.

## Group

Antonino, Filippo, Milica, Eren (Project Group 11).

## Scenario

A bartender wants to suggest the right drinks to customers with different tastes and constraints, such as non-drinkers or vegans. The knowledge base describes drinks, their ingredients and their flavours, and a reasoner uses it to classify the drinks and find which ones fit each customer.

## Files

| File | What it is |
| :- | :- |
| `KnowledgeBase-Drink.ttl` | The OWL ontology (Turtle syntax), current version |
| `scenario_and_questions.md` | Scenario and competency questions |
| `modelling_decisions.md` | Our modelling decisions, with reasons and examples |
| `discoveries.md` | Surprises from the reasoner: what happened, why, and the fix |

## Earlier versions

Earlier versions of the ontology are not kept as files. They are marked with Git tags: for each discovery, one tag before the fix and one tag after it. To open one, choose the tag in the branch menu on GitHub (tab "Tags") and download the `.ttl` file from there.

| Tag | What it shows |
| :- | :- |
| `s1-before-mocktails-missing` | Discovery S1, before the closure axioms (file `KnowledgeBase-Drink_V1.ttl`) |
| `s1-after-closure-axioms` | Discovery S1, after the closure axioms (file `KnowledgeBase-Drink_V2_closure.ttl`) |

## How to open the ontology

1. Install Protégé Desktop 5.6.9.
2. Open `KnowledgeBase-Drink.ttl`.
3. Start the reasoner: Reasoner > HermiT > Start reasoner.
4. Ask questions in the DL Query tab, for example `Mocktail` or `VeganDrink` (tick Instances).

## Working rules

1. Commit after every meaningful step, with a clear message.
2. New modelling choices go into `modelling_decisions.md`, new reasoner surprises into `discoveries.md`.
3. Before fixing a surprising result, commit the KB and tag it (for example `s2-before-...`). After the fix, commit and tag again (`s2-after-...`).
4. Things described in the documents but not yet in the ontology are marked as **planned**.
