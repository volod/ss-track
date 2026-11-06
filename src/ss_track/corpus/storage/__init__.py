"""The data root on disk: where each record and frame lives, and how a write reaches it.

`layout` composes every path below the data root. `scratch` holds the one way a writer works there:
under a lock, through scratch, and published by one rename.
"""
