# Fake ss-perception

A stand-in for the pinned ss-perception tree, which the worker tests install into a throwaway
virtual environment. It holds no sibling code. It answers the worker as the real embedders do, and
reproduces on request each defect the sibling study found, so every guard of
`src/ss_track/corpus/siblings/perception_worker.py` is tested without torch or network access. A
test names the defects in `$HF_HOME/defects.json`.
