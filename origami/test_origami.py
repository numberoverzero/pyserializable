from origami import (
    fold,
    unfold,
    pattern,
    Crafter,
    OrigamiException
)

import collections
import bitstring
import unittest
import pytest
import uuid


def init(*attrs):
    def fn(self, *args):
        for attr, arg in zip(attrs, args):
            setattr(self, attr, arg)
    return fn


def equals(*attrs):
    def eq(self, other):
        try:
            eq_ = lambda at: getattr(self, at) == getattr(other, at)
            return all(map(eq_, attrs))
        except AttributeError:
            return False
    return eq


def count_creases(fold, unfold):
    counter = collections.defaultdict(int)

    def fold_(value):
        counter['fold'] += 1
        return fold(value)

    def unfold_(value):
        counter['unfold'] += 1
        return unfold(value)
    return counter, {'fold': fold_, 'unfold': unfold_}


unique_id = lambda: str(uuid.uuid4())


class CrafterTests(unittest.TestCase):
    def setUp(self):
        self.id = unique_id()
        self.crafter = Crafter(self.id)

    def testGlobalCrafter(self):
        assert Crafter().name == 'global'
        assert Crafter() is Crafter('global')

    def testRepr(self):
        expected = "Crafter('{}')".format(self.id)
        assert repr(self.crafter) == expected

    def testLearnPattern(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}

        self.crafter.learn_pattern(cls, unfold_func, folds, creases)
        assert cls in self.crafter.patterns

    def testLearnPatternEmptyClass(self):
        cls = None
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}

        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testLearnSamePatternTwice(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}

        self.crafter.learn_pattern(cls, unfold_func, folds, creases)
        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testLearnPatternInvalidFolds(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:NotANumber'
        creases = {}

        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testFoldPattern(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)

        foo = Foo()
        foo.a = 127
        data = bitstring.pack('uint:8', foo.a)
        assert self.crafter.fold(foo) == data

    def testFoldUnknownPattern(self):
        class Foo(object):
            pass
        foo = Foo()
        with pytest.raises(OrigamiException):
            self.crafter.fold(foo)

    def testFoldMissingAttribute(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)

        with pytest.raises(OrigamiException):
            self.crafter.fold(Foo())

    def testFoldInvalidDataType(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)
        foo = Foo()
        foo.a = 'NotANumber'
        with pytest.raises(OrigamiException):
            self.crafter.fold(foo)

    def testFoldOutOfRangeValue(self):
        class Foo(object):
            pass
        cls = Foo
        unfold_func = lambda: None
        folds = 'a=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)
        foo = Foo()
        foo.a = 1 << 20
        with pytest.raises(OrigamiException):
            self.crafter.fold(foo)

    def testUnfoldPattern(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            instance = instance or Foo()
            instance.a = kw['a']
            return instance
        folds = 'a=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)

        value = 127
        data = bitstring.pack('uint:8', value)
        foo = self.crafter.unfold(data, Foo)
        assert foo.a == value

    def testUnfoldUnknownPattern(self):
        class Foo(object):
            pass
        with pytest.raises(OrigamiException):
            self.crafter.unfold(None, Foo)

    def testUnfoldMissingData(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            instance = instance or Foo()
            instance.a = kw['a']
            instance.b = kw['b']
            return instance
        folds = 'a=uint:8, b=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)

        value = 127
        data = bitstring.pack('uint:8', value)
        with pytest.raises(OrigamiException):
            self.crafter.unfold(data, Foo)

    def testUnfoldInvalidDataType(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            instance = instance or Foo()
            instance.a = kw['a']
            instance.b = kw['b']
            return instance
        folds = 'a=uint:8, b=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)

        a, b = 120, 1023
        data = bitstring.pack('uint:8, uint:10', a, b)
        foo = self.crafter.unfold(data, Foo)
        assert foo.a == a
        assert foo.b != b

    def testUnfoldConcatenatedValues(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            instance = instance or Foo()
            instance.a = kw['a']
            instance.b = kw['b']
            return instance
        folds = 'a=uint:8, b=uint:8'
        creases = {}
        self.crafter.learn_pattern(cls, unfold_func, folds, creases)

        a, b = 120, 254
        other_a, other_b = 121, 255
        data = bitstring.pack('uint:8, uint:8', a, b)
        data += bitstring.pack('uint:8, uint:8', other_a, other_b)

        foo = self.crafter.unfold(data, Foo)
        other_foo = self.crafter.unfold(data, Foo)

        assert foo.a == a
        assert foo.b == b
        assert other_foo.a == other_a
        assert other_foo.b == other_b

    def testFoldsUnknownCrafter(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            return instance

        folds = {"unknown crafter": 'a=uint:8, b=uint:1'}
        creases = {}
        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testCreaseWithoutCustomFmt(self):
        counter, my_int_creases = count_creases(fold=int, unfold=str)

        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            return instance

        creases = {
            'custom_crease': {
                'fold': int,
                'unfold': int
            }
        }

        folds = {self.id: 'a=custom_crease'}
        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testCreaseMissingFold(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            return instance

        folds = {self.id: 'a=uint:8'}
        creases = {
            "uint:8": {
                "unfold": int
            }
        }
        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testCreaseMissingUnfold(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            return instance

        folds = {self.id: 'a=uint:8'}
        creases = {
            "uint:8": {
                "fold": int
            }
        }
        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)

    def testInvalidNameFmt(self):
        class Foo(object):
            pass
        cls = Foo

        def unfold_func(name, instance, **kw):
            return instance

        folds = {self.id: 'a=my_crease'}
        creases = {
            "my_crease": {
                "fmt": "invalid",
                "fold": int,
                "unfold": int
            }
        }
        with pytest.raises(OrigamiException):
            self.crafter.learn_pattern(cls, unfold_func, folds, creases)


class PatternTests(unittest.TestCase):
    def setUp(self):
        self.id = unique_id()
        self.other_id = unique_id()
        self.crafter = Crafter(self.id)

    def testPattern(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8'

        assert hasattr(Foo, 'unfold')
        assert Foo in self.crafter.patterns

    def testPatternWithSlots(self):
        @pattern(crafter=self.id)
        class Foo(object):
            __slots__ = ['a']
            folds = 'a=uint:8'

            def __init__(self, a=10):
                self.a = a
            __eq__ = equals('a')

        foo = Foo(120)
        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, Foo, crafter=self.id)

        assert foo == other_foo

    def testPatternInvalidInit(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8'

            def __init__(self, a):
                self.a = a

        foo = Foo(10)
        data = fold(foo, crafter=self.id)
        with pytest.raises(OrigamiException):
            unfold(data, Foo, crafter=self.id)

    def testPatternNoFolds(self):
        with pytest.raises(OrigamiException):
            @pattern(crafter=self.id)
            class Foo(object):
                pass

    def testPatternGlobalCrafter(self):
        @pattern
        class Foo(object):
            folds = 'a=uint:8'
            pass

        assert hasattr(Foo, 'unfold')
        assert Foo in Crafter('global').patterns

    def testGeneratedUnfoldMethod(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:8'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo(127, 128)
        kwargs = {'a': 127, 'b': 128}
        other_foo = Foo.unfold(self.id, None, **kwargs)

        assert foo == other_foo

    def testGeneratedUnfoldReturnsInstance(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:8'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        kwargs = {'a': 127, 'b': 128}
        foo = Foo()
        other_foo = Foo.unfold(self.id, foo, **kwargs)

        assert foo is other_foo

    def testMultiCrafterUnfoldWorksForBoth(self):
        @pattern(crafter=self.id)
        @pattern(crafter=self.other_id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:8'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        kwargs = {'a': 127, 'b': 128}
        foo = Foo()
        other_foo = Foo()

        foo = Foo.unfold(self.id, foo, **kwargs)
        other_foo = Foo.unfold(self.other_id, foo, **kwargs)

        assert foo == other_foo

    def testPatternUnfoldMissingAttr(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:8'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        kwargs = {'a': 127}
        foo = Foo()

        with pytest.raises(OrigamiException):
            foo = Foo.unfold(self.id, foo, **kwargs)

    def testLearnedPattern(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8'
            __init__ = init('a')
            __eq__ = equals('a')

        @pattern(crafter=self.id)
        class Bar(object):
            folds = 'a=Foo'
            __init__ = init('a')
            __eq__ = equals('a')

        foo = Foo(256)
        bar = Bar(foo)

        kwargs = {'a': foo}
        bar = Bar()
        other_bar = Bar.unfold(self.id, bar, **kwargs)
        assert bar == other_bar


class FoldUnfoldTests(unittest.TestCase):
    def setUp(self):
        self.id = unique_id()
        self.other_id = unique_id()
        self.crafter = Crafter(self.id)

    def testSingleCrafter(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo(129, 1)

        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, Foo, crafter=self.id)

        assert foo == other_foo

    def testUnfoldByString(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo(129, 1)

        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, "Foo", crafter=self.id)

        assert foo == other_foo

    def testUnfoldIntoInstance(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo(129, 1)
        other_foo = Foo()

        data = fold(foo, crafter=self.id)
        third_foo = unfold(data, other_foo, crafter=self.id)

        assert foo == third_foo
        assert other_foo is third_foo

    def testNameCrease(self):
        counter, a_creases = count_creases(fold=int, unfold=str)

        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            creases = {'a': a_creases}
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo('129', 1)

        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, Foo, crafter=self.id)

        assert foo == other_foo
        assert counter['fold'] == counter['unfold'] == 1

    def testFoldLearnedPattern(self):
        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8'
            __init__ = init('a')
            __eq__ = equals('a')

        @pattern(crafter=self.id)
        class Bar(object):
            folds = 'a=Foo'
            __init__ = init('a')
            __eq__ = equals('a')

        foo = Foo(129)
        bar = Bar(foo)

        data = fold(bar, crafter=self.id)
        other_bar = unfold(data, Bar, crafter=self.id)

        assert bar == other_bar

    def testFormatCrease(self):
        counter, uint8_creases = count_creases(fold=int, unfold=str)

        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            creases = {'uint:8': uint8_creases}
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo('129', 1)

        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, Foo, crafter=self.id)

        assert foo == other_foo
        assert counter['fold'] == counter['unfold'] == 1

    def testFormatCreaseWithCustomFmt(self):
        counter, my_int_creases = count_creases(fold=int, unfold=str)
        my_int_creases['fmt'] = 'uint:8'

        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=my_int, b=uint:1'
            creases = {'my_int': my_int_creases}
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo('129', 1)

        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, Foo, crafter=self.id)

        assert foo == other_foo
        assert counter['fold'] == counter['unfold'] == 1

    def testNameCreaseHasPriority(self):
        name_counter, name_creases = count_creases(fold=int, unfold=str)
        fmt_counter, fmt_creases = count_creases(fold=int, unfold=str)

        @pattern(crafter=self.id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            creases = {'a': name_creases, 'uint:8': fmt_creases}
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        foo = Foo('129', 1)

        data = fold(foo, crafter=self.id)
        other_foo = unfold(data, Foo, crafter=self.id)

        assert foo == other_foo
        assert name_counter['fold'] == name_counter['unfold'] == 1
        assert fmt_counter['fold'] == fmt_counter['unfold'] == 0

    def testMultipleCraftersSameFolds(self):
        @pattern(crafter=self.id)
        @pattern(crafter=self.other_id)
        class Foo(object):
            folds = 'a=uint:8, b=uint:1'
            __init__ = init('a', 'b')
            __eq__ = equals('a', 'b')

        original_foo = Foo(129, 1)

        data = fold(original_foo, crafter=self.id)
        other_data = fold(original_foo, crafter=self.other_id)

        foo = unfold(data, Foo, crafter=self.id)
        other_foo = unfold(other_data, Foo, crafter=self.other_id)

        assert original_foo == foo
        assert foo == other_foo

    def testMultipleCraftersDifferentFolds(self):
        @pattern(crafter=self.id)
        @pattern(crafter=self.other_id)
        class Foo(object):
            folds = {
                self.id: 'a=uint:8, b=uint:1',
                self.other_id: 'b=uint:1, c=uint:7'
            }
            __init__ = init(*list('abc'))
            __eq__ = equals(*list('abc'))

        original_foo = Foo(129, 1, 100)

        data = fold(original_foo, crafter=self.id)
        other_data = fold(original_foo, crafter=self.other_id)

        foo = unfold(data, Foo, crafter=self.id)
        other_foo = unfold(other_data, Foo, crafter=self.other_id)

        assert foo.a == original_foo.a
        assert foo.b == original_foo.b

        assert other_foo.b == original_foo.b
        assert other_foo.c == original_foo.c

    def testMultipleCraftersUseSameCreases(self):
        counter, b_creases = count_creases(fold=int, unfold=str)

        @pattern(crafter=self.other_id)
        @pattern(crafter=self.id)
        class Foo(object):
            folds = {
                self.id: 'a=uint:8, b=uint:4',
                self.other_id: 'b=uint:4, c=uint:7'
            }
            creases = {'b': b_creases}
            __init__ = init(*list('abc'))
            __eq__ = equals(*list('abc'))

        original_foo = Foo(129, '12', 100)

        data = fold(original_foo, crafter=self.id)
        other_data = fold(original_foo, crafter=self.other_id)

        foo = unfold(data, Foo, crafter=self.id)
        other_foo = unfold(other_data, Foo, crafter=self.other_id)

        assert foo.a == original_foo.a
        assert foo.b == original_foo.b

        assert other_foo.b == original_foo.b
        assert other_foo.c == original_foo.c

        assert counter['fold'] == counter['unfold'] == 2
