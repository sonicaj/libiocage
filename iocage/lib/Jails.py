# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""iocage module of jail collections."""
import libzfs
import typing

import iocage.lib.Jail
import iocage.lib.Filter
import iocage.lib.Resource
import iocage.lib.helpers


class JailsGenerator(iocage.lib.Resource.ListableResource):
    """Asynchronous representation of a collection of jails."""

    _class_jail = iocage.lib.Jail.JailGenerator
    states = iocage.lib.JailState.JailStates()

    # Keys that are stored on the Jail object, not the configuration
    JAIL_KEYS = [
        "jid",
        "name",
        "running",
        "ip4.addr",
        "ip6.addr"
    ]

    def __init__(
        self,
        filters: typing.Optional[iocage.lib.Filter.Terms]=None,
        host: typing.Optional['iocage.lib.Host.HostGenerator']=None,
        logger: typing.Optional['iocage.lib.Logger.Logger']=None,
        zfs: typing.Optional['iocage.lib.ZFS.ZFS']=None
    ) -> None:

        self.logger = iocage.lib.helpers.init_logger(self, logger)
        self.zfs = iocage.lib.helpers.init_zfs(self, zfs)
        self.host = iocage.lib.helpers.init_host(self, host)

        iocage.lib.Resource.ListableResource.__init__(
            self,
            dataset=self.host.datasets.jails,
            filters=filters
        )

    def _create_resource_instance(
        self,
        dataset: libzfs.ZFSDataset,
        *class_args,  # noqa: T484
        **class_kwargs  # noqa: T484
    ) -> iocage.lib.Jail.JailGenerator:

        class_kwargs["data"] = {
            "id": dataset.name.split("/").pop()
        }
        class_kwargs["dataset"] = dataset
        class_kwargs["logger"] = self.logger
        class_kwargs["host"] = self.host
        class_kwargs["zfs"] = self.zfs
        jail = self._class_jail(*class_args, **class_kwargs)

        if jail.identifier in self.states:
            self.logger.spam(
                f"Injecting pre-loaded state to '{jail.humanreadable_name}'"
            )
            jail.jail_state = self.states[jail.identifier]

        return jail

    def __iter__(
        self
    ) -> typing.Generator['iocage.lib.Resource.Resource', None, None]:
        """Iterate over all jails matching the filter criteria."""
        self.states.query()

        for jail in iocage.lib.Resource.ListableResource.__iter__(self):

            if jail.identifier in self.states:
                jail.state = self.states[jail.identifier]
            else:
                jail.state = iocage.lib.JailState.JailState(
                    jail.identifier, {}
                )

            yield jail


class Jails(JailsGenerator):
    """Synchronous wrapper ofs JailsGenerator."""

    _class_jail = iocage.lib.Jail.Jail
