
from equivalib import GeneratorContext


def test_first_40():
    ctx = GeneratorContext({})
    for i in range(40):
        name = ctx.generate_free_name()
        ctx.assignments[name] = i

    assert ctx.assignments \
        == {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, 'f': 5, 'g': 6,
            'h': 7, 'i': 8, 'j': 9, 'k': 10, 'l': 11, 'm': 12, 'n':
            13, 'o': 14, 'p': 15, 'q': 16, 'r': 17, 's': 18, 't': 19,
            'u': 20, 'v': 21, 'w': 22, 'x': 23, 'y': 24, 'z': 25,
            'aa': 26, 'ab': 27, 'ac': 28, 'ad': 29, 'ae': 30, 'af':
            31, 'ag': 32, 'ah': 33, 'ai': 34, 'aj': 35, 'ak': 36,
            'al': 37, 'am': 38, 'an': 39}
