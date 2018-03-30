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
"""iocage filters for ListableResource."""
import re
import typing

import iocage.lib.errors
import iocage.lib.helpers
import iocage.lib.Resource
import iocage.lib.ResourceSelector

_ResourceSelector = iocage.lib.ResourceSelector.ResourceSelector
_TermValuesType = typing.Union[str, typing.List[str], _ResourceSelector]


def match_filter(value: str, filter_string: str) -> bool:
    """Return True when the value matches the filter string."""
    escaped_characters = [".", "$", "^", "(", ")", "?"]
    for character in escaped_characters:
        filter_string = filter_string.replace(character, f"\\{character}")
    filter_string = filter_string.replace("*", ".*")
    filter_string = filter_string.replace("+", ".+")
    pattern = f"^{filter_string}$"
    match = re.match(pattern, value)
    return match is not None


class Term(list):
    """A single filter term."""

    glob_characters = ["*", "+"]

    def __init__(
        self,
        key: str,
        values: _TermValuesType=[]
    ) -> None:
        self.key = key

        if isinstance(values, str):
            data = self._split_filter_values(values)
        elif isinstance(values, list):
            data = values
        elif isinstance(values, _ResourceSelector):
            data = [values]

        list.__init__(self, data)

    @property
    def short(self) -> bool:
        """Return True if the short name of a UUID be used."""
        return (self.key == "name") is True

    def matches_resource(
        self,
        resource: 'iocage.lib.Resource.Resource'
    ) -> bool:
        """Return True if the term matches the resource."""
        value = resource.get(self.key)
        return self.matches(value, self.short)

    def matches(self, value: typing.Any, short: bool=False) -> bool:
        """
        Return True if the value matches the term.

        Args:

            value:
                The value that is matched against the filter term

            short:
                When value has a length of 8 characters, this argument allows
                to match a jail's shortname as well. This is required for
                selecting jails with UUIDs by the first part of the name
        """
        # match any item of a list
        if (value is not None) and isinstance(value, list):
            # `short` not required here
            return any(map(self.matches, value))

        input_value = iocage.lib.helpers.to_string(value)

        for filter_value in self:

            if isinstance(filter_value, str):
                if self._match_filter(input_value, filter_value, short):
                    return True
            elif isinstance(filter_value, _ResourceSelector):
                if self._match_filter(input_value, filter_value.name, short):
                    return True
            elif isinstance(filter_value, list):
                results = list(map(
                    lambda x: self._match_filter(input_value, x, short),
                    filter_value
                ))
                if any(results):
                    return True

        return False

    def _match_filter(
        self,
        value: str,
        filter_string: str,
        short: bool=False
    ) -> bool:
        if match_filter(value, filter_string) is True:
            return True

        if short is False:
            return False

        # match against humanreadable names as well
        has_humanreadble_length = (len(filter_string) == 8)
        has_no_globs = not self._filter_string_has_globs(filter_string)
        if (has_humanreadble_length and has_no_globs) is True:
            shortname = iocage.lib.helpers.to_humanreadable_name(
                input_value
            )
            if shortname == filter_string:
                return True

        return False

    def _filter_string_has_globs(self, filter_string: str) -> bool:
        for glob in self.glob_characters:
            if glob in filter_string:
                return True
        return False

    def _split_filter_values(self, user_input: str) -> typing.List[str]:
        values: typing.List[str] = []
        escaped_comma_blocks = map(
            lambda block: block.split(","),
            user_input.split("\\,")
        )
        for block in escaped_comma_blocks:
            n = len(values)
            if n > 0:
                index = n - 1
                values[index] += f",{block[0]}"
            else:
                values.append(block[0])
            if len(block) > 1:
                values += block[1:]
        return values

    def _validate_name_filter_string(self, filter_string: str) -> bool:

        globs = self.glob_characters

        # Allow glob only filters
        if (len(filter_string) == 1) and (filter_string in globs):
            return True

        # replace all glob charaters in user input
        filter_string_without_globs = ""
        for i, char in enumerate(filter_string):
            if char not in globs:
                filter_string_without_globs += char

        return iocage.lib.helpers.validate_name(
            filter_string_without_globs
        ) is True


class Terms(list):
    """
    A group of filter terms.

    Each item in this group must match for a resource to pass the filter.
    This can be interpreted as logical AND
    """

    def __init__(
            self,
            terms: typing.Optional[
                typing.Iterable[typing.Union[Term, str]]
            ]=None) -> None:

        data: typing.List[typing.Union[Term, str]] = []

        if terms is not None:

            for term in terms:
                if isinstance(term, str):
                    data += self._parse_term(term)
                elif isinstance(term, Term):
                    data.append(term)

        list.__init__(self, data)

    def match_resource(
        self,
        resource: 'iocage.lib.Resource.Resource'
    ) -> bool:
        """Return True if all Terms match the resource."""
        for term in self:
            if term.matches_resource(resource) is False:
                return False
        return True

    def match_key(self, key: str, value: str) -> bool:
        """
        Check if a value matches for a given key.

        Returns True if the given value matches all terms for the specified key
        Returns Fals if one of the terms does not match
        """
        for term in self:

            if term.key != key:
                continue

            if (key == "name"):
                short = True

            if term.matches(value, short) is False:
                return False

        return True

    def match_source(self, source_name: str) -> bool:
        """Check if the source name matches the filter terms."""
        for term in self:
            if term.key != "name":
                continue

            # All name terms have been transformed to ResourceSelector
            resource_selector = term[0]
            if resource_selector.source_name is None:
                return True
            return resource_selector.source_name == source_name

        # no name term or none at all
        return True

    def _parse_term(self, user_input: str) -> typing.List[Term]:

        terms = []

        try:
            prop, value = user_input.split("=", maxsplit=1)
        except ValueError:
            prop = "name"
            value = iocage.lib.ResourceSelector.ResourceSelector(user_input)

        terms.append(Term(prop, value))

        return terms
