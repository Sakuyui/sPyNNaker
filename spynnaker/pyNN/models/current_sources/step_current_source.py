# Copyright (c) 2017-2021 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from spinn_utilities.overrides import overrides
from data_specification.enums import DataType
from spinn_front_end_common.utilities.constants import (
    BYTES_PER_WORD, MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.utilities.globals_variables import get_simulator
from spynnaker.pyNN.exceptions import SpynnakerException
from .abstract_current_source import AbstractCurrentSource, CurrentSourceIDs


class StepCurrentSource(AbstractCurrentSource):
    """ Current source where the amplitude changes based on a time array

    """
    __slots__ = [
        "__amplitudes",
        "__times",
        "__parameters",
        "__parameter_types"]

    def __init__(self, times=[], amplitudes=[]):
        # There's probably no need to actually store these as you can't
        # access them directly in pynn anyway
        sim = get_simulator()
        machine_ts = sim.machine_time_step
        time_convert_ms = MICRO_TO_MILLISECOND_CONVERSION / machine_ts
        self.__times = [times[i] * time_convert_ms for i in range(len(times))]
        self.__amplitudes = amplitudes

        if (len(times) != len(amplitudes)):
            msg = "len(times) is {}, but len(amplitudes) is {}".format(
                len(times), len(amplitudes))
            raise SpynnakerException(msg)

        self.__parameter_types = dict()
        self.__parameter_types['times'] = DataType.UINT32  # arrays?
        self.__parameter_types['amplitudes'] = DataType.S1615

        self.__parameters = dict()
        self.__parameters['times'] = self.__times
        self.__parameters['amplitudes'] = self.__amplitudes

    def set_parameters(self, parameters):
        """ Set the current source parameters

        :param dict(str, Any) parameters: the parameters to set
        """
        for key, value in parameters.items():
            if key not in self.__parameters.keys():
                # throw an exception
                msg = "{} is not a parameter of {}".format(key, self)
                raise SpynnakerException(msg)
            else:
                self.__parameters[key] = value

    @property
    @overrides(AbstractCurrentSource.get_parameters)
    def get_parameters(self):
        """ Get the parameters of the current source

        :rtype dict(str, Any)
        """
        return self.__parameters

    @property
    @overrides(AbstractCurrentSource.get_parameter_types)
    def get_parameter_types(self):
        """ Get the parameters of the current source

        :rtype dict(str, Any)
        """
        return self.__parameter_types

    @property
    @overrides(AbstractCurrentSource.current_source_id)
    def current_source_id(self):
        """ The ID of the current source.

        :rtype: int
        """
        return CurrentSourceIDs.STEP_CURRENT_SOURCE.value

    @overrides(AbstractCurrentSource.get_sdram_usage_in_bytes)
    def get_sdram_usage_in_bytes(self, n_neurons):
        """ The sdram usage of the current source.

        :rtype: int
        """
        return n_neurons * (((len(self.__times) + 1) * 2) + 1) * BYTES_PER_WORD
