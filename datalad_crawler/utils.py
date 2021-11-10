# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Various utils which were moved from datalad core or might be later moved into it

To simplify such refactoring tests should be provided here as well
"""

import inspect


def flatten(l, types=None, base_type=None):
    """Given a list, return a recursively flattened version

    Parameters
    ----------
    l:
      Iterable to flatten
    types: type or tuple of types, optional
      By default all non-list types are preserved as is, but you could specify
      other iterable types (e.g., `set`, `tuple`, `dict`) which would be flattened
      then too.  Note that no (re)ordering of associative (`set`, `dict`)
      elements is done, thus order is not guaranteed if original container
      does not provide order
    base_type: type, optional
      What should be the output type. If not specified, the type of the `l`
      is used. Note that the function supports only the base_types which support
      `+` operand, so cannot be `set` or `dict`
    """
    if base_type is None:
        base_type = type(l)
    if types is None:
        types = base_type
    return sum((flatten(i, types=types, base_type=base_type) for i in l),
               base_type()) \
            if isinstance(l, types) \
            else base_type((l,))


# moved from datalad core, made python 3 specific
def get_func_kwargs_doc(func):
    """ Provides args for a function

    Parameters
    ----------
    func:
      function from which args are being requested

    Returns
    -------
    list
      of the args that a function takes in
    """
    return inspect.getfullargspec(func)[0]