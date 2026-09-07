#!/usr/bin/env python3
"""Freak Town CLI — Create comedy minutes in the terminal.

Run:
  freaktown                    # interactive mode
  freaktown --quick "dogs"     # quick mode: premise → minute → audio
"""

import argparse
import sys
from .terminal import main

if __name__ == "__main__":
    main()
