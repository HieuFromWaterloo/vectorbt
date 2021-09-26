# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Functions for combining arrays.

Combine functions combine two or more NumPy arrays using a custom function. The emphasis here is
done upon stacking the results into one NumPy array - since vectorbt is all about brute-forcing
large spaces of hyperparameters, concatenating the results of each hyperparameter combination into
a single DataFrame is important. All functions are available in both Python and Numba-compiled form."""

import numpy as np
from tqdm.auto import tqdm

from vectorbt import _typing as tp
from vectorbt.nb_registry import register_jit
from vectorbt.utils.parallel import run_ntimes_using_ray
from vectorbt.base import reshape_fns


def apply_and_concat_none(n: int,
                          apply_func: tp.Callable, *args,
                          show_progress: bool = False,
                          tqdm_kwargs: tp.KwargsLike = None,
                          **kwargs) -> None:
    """For each value `i` from 0 to `n`, apply `apply_func` with arguments `*args` and `**kwargs`,
    and output nothing. Meant for in-place outputs.

    `apply_func` must accept arguments `i`, `*args` and `**kwargs`."""
    if tqdm_kwargs is None:
        tqdm_kwargs = {}
    for i in tqdm(range(n), disable=not show_progress, **tqdm_kwargs):
        apply_func(i, *args, **kwargs)


@register_jit
def apply_and_concat_none_nb(n: int, apply_func_nb: tp.Callable, *args) -> None:
    """A Numba-compiled version of `apply_and_concat_none`.

    !!! note
        * `apply_func_nb` must be Numba-compiled
        * `*args` must be Numba-compatible
        * No support for `**kwargs`
    """
    for i in range(n):
        apply_func_nb(i, *args)


def apply_and_concat_one(n: int,
                         apply_func: tp.Callable, *args,
                         show_progress: bool = False,
                         tqdm_kwargs: tp.KwargsLike = None,
                         **kwargs) -> tp.Array2d:
    """For each value `i` from 0 to `n`, apply `apply_func` with arguments `*args` and `**kwargs`,
    and concat the results along axis 1.

    The result of `apply_func` must be a single 1-dim or 2-dim array.

    `apply_func` must accept arguments `i`, `*args` and `**kwargs`."""
    if tqdm_kwargs is None:
        tqdm_kwargs = {}
    outputs = []
    for i in tqdm(range(n), disable=not show_progress, **tqdm_kwargs):
        outputs.append(reshape_fns.to_2d(apply_func(i, *args, **kwargs)))
    return np.column_stack(outputs)


@register_jit
def to_2d_one_nb(a: tp.Array) -> tp.Array2d:
    """Expand the dimensions of array `a` along axis 1.

    !!! note
        * `a` must be strictly homogeneous"""
    if a.ndim > 1:
        return a
    return np.expand_dims(a, axis=1)


@register_jit
def apply_and_concat_one_nb(n: int, apply_func_nb: tp.Callable, *args) -> tp.Array2d:
    """A Numba-compiled version of `apply_and_concat_one`.

    !!! note
        * `apply_func_nb` must be Numba-compiled
        * `*args` must be Numba-compatible
        * No support for `**kwargs`
    """
    output_0 = to_2d_one_nb(apply_func_nb(0, *args))
    output = np.empty((output_0.shape[0], n * output_0.shape[1]), dtype=output_0.dtype)
    for i in range(n):
        if i == 0:
            outputs_i = output_0
        else:
            outputs_i = to_2d_one_nb(apply_func_nb(i, *args))
        output[:, i * outputs_i.shape[1]:(i + 1) * outputs_i.shape[1]] = outputs_i
    return output


def apply_and_concat_multiple(n: int,
                              apply_func: tp.Callable, *args,
                              show_progress: bool = False,
                              tqdm_kwargs: tp.KwargsLike = None,
                              **kwargs) -> tp.List[tp.Array2d]:
    """Identical to `apply_and_concat_one`, except that the result of `apply_func` must be
    multiple 1-dim or 2-dim arrays. Each of these arrays at `i` will be concatenated with the
    array at the same position at `i+1`."""
    if tqdm_kwargs is None:
        tqdm_kwargs = {}
    outputs = []
    for i in tqdm(range(n), disable=not show_progress, **tqdm_kwargs):
        outputs.append(tuple(map(reshape_fns.to_2d, apply_func(i, *args, **kwargs))))
    return list(map(np.column_stack, list(zip(*outputs))))


@register_jit
def to_2d_multiple_nb(a: tp.Iterable[tp.Array]) -> tp.List[tp.Array2d]:
    """Expand the dimensions of each array in `a` along axis 1.

    !!! note
        * `a` must be strictly homogeneous
    """
    lst = list()
    for _a in a:
        lst.append(to_2d_one_nb(_a))
    return lst


@register_jit
def apply_and_concat_multiple_nb(n: int, apply_func_nb: tp.Callable, *args) -> tp.List[tp.Array2d]:
    """A Numba-compiled version of `apply_and_concat_multiple`.

    !!! note
        * Output of `apply_func_nb` must be strictly homogeneous
        * `apply_func_nb` must be Numba-compiled
        * `*args` must be Numba-compatible
        * No support for `**kwargs`
    """
    outputs = list()
    outputs_0 = to_2d_multiple_nb(apply_func_nb(0, *args))
    for j in range(len(outputs_0)):
        outputs.append(np.empty((outputs_0[j].shape[0], n * outputs_0[j].shape[1]), dtype=outputs_0[j].dtype))
    for i in range(n):
        if i == 0:
            outputs_i = outputs_0
        else:
            outputs_i = to_2d_multiple_nb(apply_func_nb(i, *args))
        for j in range(len(outputs_i)):
            outputs[j][:, i * outputs_i[j].shape[1]:(i + 1) * outputs_i[j].shape[1]] = outputs_i[j]
    return outputs


def select_and_combine(i, obj, others, combine_func, *args, **kwargs):  # no type annotations!
    """Combine `obj` and an element from `others` at `i` using `combine_func`."""
    return combine_func(obj, others[i], *args, **kwargs)


def combine_and_concat(obj: tp.Any,
                       others: tp.Sequence,
                       combine_func: tp.Callable,
                       *args, **kwargs) -> tp.Array2d:
    """Use `apply_and_concat_one` to combine `obj` with each element from `others` using `combine_func`."""
    return apply_and_concat_one(len(others), select_and_combine, obj, others, combine_func, *args, **kwargs)


@register_jit
def select_and_combine_nb(i, obj, others, combine_func_nb, *args):  # no type annotations!
    """A Numba-compiled version of `select_and_combine`.

    !!! note
        * `combine_func_nb` must be Numba-compiled
        * `obj`, `others` and `*args` must be Numba-compatible
        * `others` must be strictly homogeneous
        * No support for `**kwargs`
    """
    return combine_func_nb(obj, others[i], *args)


@register_jit
def combine_and_concat_nb(obj: tp.Any, others: tp.Sequence, combine_func_nb: tp.Callable, *args) -> tp.Array2d:
    """A Numba-compiled version of `combine_and_concat`."""
    return apply_and_concat_one_nb(len(others), select_and_combine_nb, obj, others, combine_func_nb, *args)


def combine_multiple(objs: tp.Sequence, combine_func: tp.Callable, *args, **kwargs) -> tp.AnyArray:
    """Combine `objs` pairwise into a single object."""
    result = objs[0]
    for i in range(1, len(objs)):
        result = combine_func(result, objs[i], *args, **kwargs)
    return result


@register_jit
def combine_multiple_nb(objs: tp.Sequence, combine_func_nb: tp.Callable, *args) -> tp.Array:
    """A Numba-compiled version of `combine_multiple`.

    !!! note
        * `combine_func_nb` must be Numba-compiled
        * `objs` and `*args` must be Numba-compatible
        * `objs` must be strictly homogeneous
        * No support for `**kwargs`
    """
    result = objs[0]
    for i in range(1, len(objs)):
        result = combine_func_nb(result, objs[i], *args)
    return result


def apply_and_concat_one_ray(*args, **kwargs) -> tp.Array2d:
    """Distributed version of `apply_and_concat_one`."""
    results = run_ntimes_using_ray(*args, **kwargs)
    return np.column_stack(list(map(reshape_fns.to_2d, results)))


def apply_and_concat_multiple_ray(*args, **kwargs) -> tp.List[tp.Array2d]:
    """Distributed version of `apply_and_concat_multiple`."""
    results = run_ntimes_using_ray(*args, **kwargs)
    return list(map(np.column_stack, list(zip(*results))))


def combine_and_concat_ray(obj: tp.Any,
                           others: tp.Sequence,
                           combine_func: tp.Callable,
                           *args, **kwargs) -> tp.Array2d:
    """Distributed version of `combine_and_concat`."""
    return apply_and_concat_one_ray(len(others), select_and_combine, obj, others, combine_func, *args, **kwargs)
