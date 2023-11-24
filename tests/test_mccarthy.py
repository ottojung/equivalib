
from equivalib.mccarthy import mccarthy

def test_mc_carthy():
    for n in range(-100, 100):
        assert mccarthy(n) == 91
