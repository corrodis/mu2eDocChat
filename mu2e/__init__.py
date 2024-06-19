import os

if "MU2E" in os.environ:
    MU2E = os.environ["MU2E"]+"/"
else:
    MU2E = "./"

from .core import *
from .wikiRetrival import *
print("loading the mu2e assistent")
