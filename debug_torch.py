import sys
import os
print(f"Python Executable: {sys.executable}")
print(f"Python Path: {sys.path}")
try:
    import torch
    print(f"Torch Version: {torch.__version__}")
    print(f"Torch Path: {torch.__file__}")
except ImportError as e:
    print(f"ImportError: {e}")
