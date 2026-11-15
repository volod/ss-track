"""Versioned event packages shared by Python modules and later C++ modules.

The frozen descriptor of each package lives under ``contracts/event/``. Parsing a
JSON Lines event is ``contract.events``. Mapping a staged ``FrameRef`` is
``contract.frame_ref``. This package does not import ``ss_track.corpus`` at import
time.
"""
