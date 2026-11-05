"""The command groups `cli` composes, and how every command reports its one JSON record."""

import argparse

type Subcommands = argparse._SubParsersAction[argparse.ArgumentParser]  # a parser's command group
