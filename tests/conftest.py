import os
import sys

# Make the in-game package importable in tests without the game engine.
_CLIENT = os.path.join(os.path.dirname(__file__), "..", "src", "res", "scripts", "client")
sys.path.insert(0, os.path.abspath(_CLIENT))
