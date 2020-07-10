from ergometer.util import Interval, pairwise, takeuntil_inclusive


def test_interval_overlaps():
    assert Interval(0, 2).overlaps(1, 3)
    assert not Interval(0, 2).overlaps(2, 4)
    assert Interval(0, 4).overlaps(1, 3)


def test_pairwise():
    assert [*pairwise([])] == []
    assert [*pairwise([11])] == []
    assert [*pairwise([11, 22])] == [(11, 22)]
    assert [*pairwise([11, 22, 33])] == [(11, 22)]
    assert [*pairwise([11, 22, 33, 44])] == [(11, 22), (33, 44)]


def test_takeuntil_inclusive():
    def is_odd(x):
        return x % 2 != 0

    assert [*takeuntil_inclusive(is_odd, [])] == []
    assert [*takeuntil_inclusive(is_odd, [10])] == [10]
    assert [*takeuntil_inclusive(is_odd, [10, 20])] == [10, 20]

    assert [*takeuntil_inclusive(is_odd, [15])] == [15]
    assert [*takeuntil_inclusive(is_odd, [15, 20])] == [15]
    assert [*takeuntil_inclusive(is_odd, [15, 25])] == [15]

    assert [*takeuntil_inclusive(is_odd, [10])] == [10]
    assert [*takeuntil_inclusive(is_odd, [10, 25])] == [10, 25]
    assert [*takeuntil_inclusive(is_odd, [10, 25, 30])] == [10, 25]
    assert [*takeuntil_inclusive(is_odd, [10, 25, 35])] == [10, 25]

    assert [*takeuntil_inclusive(is_odd, [10, 20])] == [10, 20]
    assert [*takeuntil_inclusive(is_odd, [10, 20, 35])] == [10, 20, 35]
    assert [*takeuntil_inclusive(is_odd, [10, 20, 35, 40])] == [10, 20, 35]
    assert [*takeuntil_inclusive(is_odd, [10, 20, 35, 45])] == [10, 20, 35]
