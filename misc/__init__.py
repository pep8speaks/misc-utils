"""Stuff"""
import functools
import threaing
import builtins
import re
import operator
import typing as T


def show_table(items: dict):
    """Print the gven dict as a table where keys are headers and
    values are sequences of the items in rows"""
    lengths = [max(len(x) for x in items[k]+[k])+3 for k in items]
    print('|'.join(k.ljust(lengths[i]) for i, k in enumerate(items)))
    print('-'*(sum(lengths)+len(items)-1))
    
    for i in range(len(next(iter(items.values())))):
        print('|'.join(items[k][i].ljust(lengths[j])
                       for j, k in enumerate(items)))


def multiline_input(prompt='... ', end='\x04'):
    return '\n'.join(iter(functools.partial(input, prompt), end))



def only_classmethods(cls):
    """convert all normal methods to classmethods"""
    for k, v in cls.__dict__.items():
        if (not k.startswith('__')
                and callable(v)
                and not isinstance(v, (classmethod, staticmethod))):
            setattr(cls, k, classmethod(v))
    return cls


def threadsafe_method(name='lock'):
    """wrap the method into a with getattr(self, name):"""
    def wrapper_maker(meth):
        @functools.wraps(meth)
        def wrapper(self, *args, **kwargs):
            with getattr(self, name):
                return meth(self, *args, **kwargs)
        return wrapper
    return wrapper_maker


def threadsafe_class(name: str = 'lock', exclude: T.Container[str] =
                     ('__init__', '__new__', '__init_subclass__'),
                     check: T.Callable[[T.Any], bool] = callable,
                     wrap_init=threading.RLock):
    """wrap all class attributes passing `check` (default: `callable`) with `threadsafe_method`

    `exclude` may contain names not to wrap. Only `cls.__dict__` is checked.
    if `wrap_init` is truthly, __init__ will be wrapped to setattr(self, name, wrap_init())"""
    def modifier(cls):
        for k, v in cls.__dict__.items():
            if check(v) and k not in exclude:
                setattr(cls, k, threadsafe_method(name=name)(v))
            if wrap_init and k == '__init__':
                __init__method = v
                @functools.wraps(v)
                def wrapper(self, *args, **kwargs):
                    setattr(self, name, wrap_init())
                    return __init__method(self, *args, **kwargs)
                setattr(cls, '__init__', wrapper)
        return cls
    return modifier


class Instance:
    """Delay lookups

        This class allows for all lookup oparations on an object
        to be stored and executed at any later time

        To perform the stored oparations, use the
            Instance.lookup(<Instance object>, <real object>)
        method. DO NOT call it from the object.

        To pass the object through (built-in) functions at lookup time,
        access `__call_<function name>`. The function will be called with
        the object as sole argument. The functions are stored in the
        CALLABLES attribute, a dict. `not` is also supported.

        For the `in` as `is` lookups, call the `.__call_<is, in or contains>`
        with the sppropriate argument. using `.__call_contains`
        will swap the operands.

        To iterate, just iterate. This will yield a single Instance
        object whose lookup will yield an iterable over the different items.
        NOTE: This also applies when creating e.g. a list, therefore always
        continue with the first item:
            instance_obj = list(instance_obj)[0]
            instance_obj = [somefunc(x) for x in instance_obj][0]
        """
    CALLABLES = {k: getattr(builtins, k) for k in
                 'len repr str bytes int float bool complex'.split()}
    CALLABLES.update({
        'not': operator.not_,
        'is': operator.is_,
        'in': lambda a, b: operator.contains(b, a),
        'contains': operator.contains,
    })

    iter_flag = False

    def _dunder_lookup(__name__=None):
        def wrapper(self, *args, **kwargs):
            super().__getattribute__('stored_lookups').append(
                (__name__, args, kwargs))
            return self
        wrapper.__name__ = __name__
        return wrapper

    for _dunder_name in ('lt le eq ne gt ge trunc getitem setitem reversed '
                         + 'add sub mul matmul truediv floordiv mod divmod '
                         + 'lshift rshift and xor radd rsub rmul rfloordiv '
                         + 'or pow rmatmul rtruediv rmod rdivmod rpow rand '
                         + 'rlshift rrshift rxor ror iadd isub ior imatmul '
                         + 'imul itruediv ifloordiv imod ipow ilshift iand '
                         + 'irshift ixor ior neg pos abs invert round ciel '
                         + 'call floor setattr iter').split():
        _dunder_name = '__{}__'.format(_dunder_name)
        locals()[_dunder_name] = _dunder_lookup(_dunder_name)
    del _dunder_lookup, _dunder_name

    def lookup(self, inst, _index=0):
        result = inst
        for i, (lkup, a1, a2) in enumerate(super().__getattribute__(
                'stored_lookups')[_index:], _index):
            if lkup == '**call**':
                result = Instance.CALLABLES[a1](result, *a2)
            elif lkup == '__next__':
                return (Instance.lookup(self, r, i + 1) for r in result)
            else:
                result = getattr(result, lkup)(*a1, **a2)
        return result

    def __next__(self):
        flag = super().__getattribute__('iter_flag')
        super().__setattr__('iter_flag', not flag)
        if flag:
            raise StopIteration
        else:
            super().__getattribute__('stored_lookups').append(
                ('__next__', (), {}))
            return self

    def __init__(self):
        super().__setattr__('stored_lookups', [])

    def __getattribute__(self, name):
        stored_lookups = super().__getattribute__('stored_lookups')
        match = re.match(
            '^__call_({})$'.format('|'.join(Instance.CALLABLES)),
            name
        )
        if match:
            name = match.group(1)
            if name in ['in', 'is']:
                return functools.partial(Instance._call_with_arg,
                               self,
                               _name=name,
                               _op=stored_lookups.append)
            stored_lookups.append(('**call**', name, ()))
        else:
            stored_lookups.append(('__getattribute__', (name,), {}))
        return self

    def _call_with_arg(self, arg, _op, _name):
        _op(('**call**', _name, (arg,)))
        return self


class Tree:
    @classmethod
    def new(cls, value):
        return type('<DerivedTreeNode: {}>'.format(type(value)),
                    (Tree, type(value)), {})(value)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, type(
            '<DerivedTreeNode: {}>'.format(type(value)), (Tree, type(value)), {})(value))
