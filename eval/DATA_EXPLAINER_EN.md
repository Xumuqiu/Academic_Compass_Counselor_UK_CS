# Data explainer

The submission uses fictional student data. No real Tracy CV or other identifiable student material is included. [Detailed data history](data_explainer.md) (Chinese) records the development stages.

## Data layers

- `data/sample_cv.json`: the two-experience fictional student shown by the app's sample button.
- `data/programmes.json`: eleven locally curated programme entries with original source URLs, marked unverified. They are not a current comprehensive admissions database.
- `data/ucas_2026.json`: local three-question writing guidance with source links; not an independently validated set of university-specific preferences.
- `eval/data/offline_cases.json`: twenty earlier authored development challenges with simulated reviewer responses. These are program fixtures, not real model quality evidence.
- `eval/data/synthetic_profiles_v1/`: 26 AI-authored JSON profiles, six dev and twenty evaluation candidates; each has two experiences, a manifest, simulated answer bank, offline transcript and draft references. There are 52 experiences and 468 authored answers; the offline selector delivered 322 turns across all 26 profiles. Hidden undelivered answers cannot be used as available evidence.
- `eval/annotations/stage_gold_v1/`: separately preserved AI reference annotations, 39 specific gaps and 73 fact opportunities across all 26 profiles. These were frozen with the scoring rules before the real main run but were not independently reviewed by a human.
- `report/DEMO_SAMPLE_ANSWERS.*`: additional fictional English answers for recording the built-in sample. These are not part of the reported twenty-case experiment.

## Independence, privacy and provenance

The data author also participated in development and AI scoring. The twenty candidates had been viewed, so the independent held-out count is zero. The examples use the organisation of a CV without copying real personal evidence. Synthetic source labels do not make the data independent or representative of actual applicants.

Dataset and reference checksum manifests are included. Real runs preserve original inputs, actually delivered turns, reference snapshots and source versions. Do not regenerate or modify these before verifying the saved results. Creating a different dataset requires a new version, not overwriting this experiment.

The repository must remain runnable with these fictional fixtures. It contains no live API keys. Real uploads and answers in live mode go to the model provider; this prototype does not implement institutional consent, retention or deletion policies.
