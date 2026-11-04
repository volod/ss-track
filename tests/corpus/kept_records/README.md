# Kept records

Real sealed records, one per format at each major it has had. A record with only its version number
changed proves nothing about a format, so every file here was written by the code of the commit in
its name. The tests read them under every later version.

Each commit was exported with `git archive`, and its own code imported one generated clip of 24
frames, built a corpus version and staged it. Only the JSON is kept, byte for byte. No clip or frame
enters the repository, and no file here is edited: a new major adds a file.

| Record | Commit | What it shows |
| --- | --- | --- |
| `source-schema-1-0238d55.json` | `0238d55` | Earliest schema 1, lacking four decoded facts |
| `source-schema-1-d6b704d.json` | `d6b704d` | Later schema 1, holding every current decoded fact |
| `source-schema-2-129a350.json` | `129a350` | First schema 2, under decode policy revision 2 |
| `corpus-schema-1-294535c.json` | `294535c` | `sequences`, with no group or split |
| `corpus-schema-2-78db68c.json` | `78db68c` | `streams`, with no `width` or `height` |
| `corpus-schema-3-d6b704d.json` | `d6b704d` | Schema 3 with no source terms in `streams[].rights` |
| `corpus-schema-3-129a350.json` | `129a350` | Schema 3 holding source terms, with no version bump |
| `bundle-schema-1-294535c.json` | `294535c` | `sequence_id` |
| `bundle-schema-2-78db68c.json` | `78db68c` | `stream_id`, with no `generated` |
| `bundle-schema-3-d6b704d.json` | `d6b704d` | The current bundle format |
| `frame-set-schema-1-fd982a1.json` | `fd982a1` | The current frame set format |
| `staged-hashes-schema-1-0bf3b9e.json` | `0bf3b9e` | The current staged-hashes format |
| `hash-comparison-schema-1-0bf3b9e.json` | `0bf3b9e` | The current comparison format |
