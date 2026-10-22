#!/usr/bin/env python3
"""FUNNIER CLI — Create comedy minutes in the terminal.

Run:
  funnier                    # interactive mode
  funnier --quick "dogs"     # quick mode: premise → minute → audio
"""

import argparse
import sys
from .terminal import main

if __name__ == "__main__":
    main()
