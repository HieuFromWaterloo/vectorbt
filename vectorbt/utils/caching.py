# Copyright (c) 2021 Oleg Polakow. All rights reserved.
# This code is licensed under Apache 2.0 with Commons Clause license (see LICENSE.md for details)

"""Utilities for caching."""

from vectorbt import _typing as tp
from vectorbt.utils.decorators import class_or_instancemethod


class Cacheable:
    """Class that contains cacheable properties and methods.

    Required to register `vectorbt.utils.decorators.cacheable_property` and
    `vectorbt.utils.decorators.cacheable_method`.

    See `vectorbt.ca_registry` for details on the caching procedure."""

    def __init__(self) -> None:
        from vectorbt._settings import settings
        caching_cfg = settings['caching']

        if not caching_cfg['register_lazily']:
            instance_setup = self.get_ca_setup()
            if instance_setup is not None:
                for unbound_setup in instance_setup.unbound_setups:
                    unbound_setup.cacheable.get_ca_setup(self)

    @class_or_instancemethod
    def get_ca_setup(cls_or_self) -> tp.Union['CAClassSetup', 'CAInstanceSetup']:
        """Get instance setup of type `vectorbt.ca_registry.CAInstanceSetup` if the instance method
        was called and class setup of type `vectorbt.ca_registry.CAClassSetup` otherwise."""
        from vectorbt.ca_registry import CAClassSetup, CAInstanceSetup

        if isinstance(cls_or_self, type):
            return CAClassSetup.get(cls_or_self)
        return CAInstanceSetup.get(cls_or_self)
