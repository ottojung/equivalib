
from equivalib import denv


def test_simple():
    with denv.let(x = 5):
        assert denv.x == 5


def test_hard():
    with denv.let(x = 5):
        assert denv.x == 5
        with denv.let(x = 7):
            assert denv.x == 7
            with denv.let(y = 8):
                assert denv.y == 8
                assert denv.x == 7
            assert denv.x == 7
        assert denv.x == 5
