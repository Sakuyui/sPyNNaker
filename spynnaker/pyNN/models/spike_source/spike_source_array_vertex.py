# Copyright (c) 2017-2019 The University of Manchester
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

import logging
import numpy
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_front_end_common.utility_models import ReverseIpTagMultiCastSource
from spinn_front_end_common.abstract_models import AbstractChangableAfterRun
from spynnaker.pyNN.data import SpynnakerDataView
from spynnaker.pyNN.models.common import EIEIOSpikeRecorder
from spynnaker.pyNN.utilities import constants
from spynnaker.pyNN.models.abstract_models import (
    PopulationApplicationVertex, RecordingType, ParameterHolder)
from spynnaker.pyNN.utilities.ranged import SpynnakerRangedList

logger = FormatAdapter(logging.getLogger(__name__))


def _as_numpy_ticks(times, time_step):
    return numpy.ceil(
        numpy.floor(numpy.array(times) * 1000.0) / time_step).astype("int64")


def _send_buffer_times(spike_times, time_step):
    # Convert to ticks
    if len(spike_times) and hasattr(spike_times[0], "__len__"):
        data = []
        for times in spike_times:
            data.append(_as_numpy_ticks(times, time_step))
        return data
    else:
        return _as_numpy_ticks(spike_times, time_step)


class SpikeSourceArrayVertex(
        ReverseIpTagMultiCastSource, PopulationApplicationVertex,
        AbstractChangableAfterRun):
    """ Model for play back of spikes
    """

    SPIKE_RECORDING_REGION_ID = 0

    def __init__(
            self, n_neurons, spike_times, constraints, label,
            max_atoms_per_core, model, splitter):
        # pylint: disable=too-many-arguments
        self.__model_name = "SpikeSourceArray"
        self.__model = model

        if spike_times is None:
            spike_times = []
        use_list_as_value = (
            not len(spike_times) or not hasattr(spike_times[0], '__iter__'))
        self._spike_times = SpynnakerRangedList(
            n_neurons, spike_times, use_list_as_value=use_list_as_value)

        time_step = SpynnakerDataView.get_simulation_time_step_us()

        super().__init__(
            n_keys=n_neurons, label=label, constraints=constraints,
            max_atoms_per_core=max_atoms_per_core,
            send_buffer_times=_send_buffer_times(spike_times, time_step),
            send_buffer_partition_id=constants.SPIKE_PARTITION_ID,
            splitter=splitter)

        # handle recording
        self.__spike_recorder = EIEIOSpikeRecorder()

        # used for reset and rerun
        self.__requires_mapping = True

    @property
    @overrides(AbstractChangableAfterRun.requires_mapping)
    def requires_mapping(self):
        return self.__requires_mapping

    @overrides(AbstractChangableAfterRun.mark_no_changes)
    def mark_no_changes(self):
        self.__requires_mapping = False

    def _to_early_spikes_single_list(self, spike_times):
        """
        Checks if there is one or more spike_times before the current time

        Logs a warning for the first oen found

        :param iterable(int spike_times:
        """
        current_time = SpynnakerDataView.get_current_run_time_ms()
        for i in range(len(spike_times)):
            if spike_times[i] < current_time:
                logger.warning(
                    "SpikeSourceArray {} has spike_times that are lower than "
                    "the current time {} For example {} - "
                    "these will be ignored.".format(
                        self, current_time, float(spike_times[i])))
                return

    def _check_spikes_double_list(self, spike_times):
        """
        Checks if there is one or more spike_times before the current time

        Logs a warning for the first oen found

        :param iterable(iterable(int) spike_times:
        """
        current_time = SpynnakerDataView.get_current_run_time_ms()
        for neuron_id in range(0, self.n_atoms):
            id_times = spike_times[neuron_id]
            for i in range(len(id_times)):
                if id_times[i] < current_time:
                    logger.warning(
                       "SpikeSourceArray {} has spike_times that are lower "
                       "than the current time {} For example {} - "
                       "these will be ignored.".format(
                            self, current_time, float(id_times[i])))
                    return

    def __set_spike_buffer_times(self, spike_times):
        """ Set the spike source array's buffer spike times

        """
        time_step = SpynnakerDataView.get_simulation_time_step_us()
        # warn the user if they are asking for a spike time out of range
        if spike_times:  # in case of empty list do not check
            if hasattr(spike_times[0], '__iter__'):
                self._check_spikes_double_list(spike_times)
            else:
                self._to_early_spikes_single_list(spike_times)
        self.send_buffer_times = _send_buffer_times(spike_times, time_step)

    def __read_parameter(self, name, selector):
        # This can only be spike times
        return self._spike_times.get_values(selector)

    @overrides(PopulationApplicationVertex.get_parameter_values)
    def get_parameter_values(self, names, selector=None):
        self._check_parameters(names, {"spike_times"})
        return ParameterHolder(names, self.__read_parameter, selector)

    @overrides(PopulationApplicationVertex.set_parameter_values)
    def set_parameter_values(self, name, value, selector=None):
        self._check_parameters(name, {"spike_times"})
        self.__set_spike_buffer_times(value)
        use_list_as_value = (
            not len(value) or not hasattr(value[0], '__iter__'))
        self._spike_times.set_value_by_selector(
            selector, value, use_list_as_value)

    @overrides(PopulationApplicationVertex.get_parameters)
    def get_parameters(self):
        return ["spike_times"]

    @overrides(PopulationApplicationVertex.get_units)
    def get_units(self, name):
        if name == "spikes":
            return ""
        if name == "spike_times":
            return "ms"
        raise KeyError(f"Units for {name} unknown")

    @overrides(PopulationApplicationVertex.get_recordable_variables)
    def get_recordable_variables(self):
        return ["spikes"]

    @overrides(PopulationApplicationVertex.can_record)
    def can_record(self, name):
        return name == "spikes"

    @overrides(PopulationApplicationVertex.set_recording)
    def set_recording(self, name, sampling_interval=None, indices=None):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        if sampling_interval is not None:
            logger.warning("Sampling interval currently not supported for "
                           "SpikeSourceArray so being ignored")
        if indices is not None:
            logger.warning("Indices currently not supported for "
                           "SpikeSourceArray so being ignored")
        self.enable_recording(True)

    @overrides(PopulationApplicationVertex.set_not_recording)
    def set_not_recording(self, name, indices=None):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        if indices is not None:
            logger.warning("Indices currently not supported for "
                           "SpikeSourceArray so being ignored")
        self.enable_recording(False)

    @overrides(PopulationApplicationVertex.get_recorded_data)
    def get_recorded_data(self, name):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        return self.__spike_recorder.get_spikes(
            self.label, 0, self,
            lambda vertex:
                vertex.virtual_key
                if vertex.virtual_key is not None
                else 0)

    @overrides(PopulationApplicationVertex.get_recording_sampling_interval)
    def get_recording_sampling_interval(self, name):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        return SpynnakerDataView.get_simulation_time_step_us()

    @overrides(PopulationApplicationVertex.get_recording_indices)
    def get_recording_indices(self, name):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        return range(self.n_atoms)

    @overrides(PopulationApplicationVertex.get_recording_type)
    def get_recording_type(self, name):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        return RecordingType.BIT_FIELD

    @overrides(PopulationApplicationVertex.clear_recording_data)
    def clear_recording_data(self, name):
        if name != "spikes":
            raise KeyError(f"Cannot record {name}")
        buffer_manager = SpynnakerDataView.get_buffer_manager()
        for machine_vertex in self.machine_vertices:
            placement = SpynnakerDataView.get_placement_of_vertex(
                machine_vertex)
            buffer_manager.clear_recorded_data(
                placement.x, placement.y, placement.p,
                SpikeSourceArrayVertex.SPIKE_RECORDING_REGION_ID)

    def describe(self):
        """ Returns a human-readable description of the cell or synapse type.

        The output may be customised by specifying a different template\
        together with an associated template engine\
        (see :py:mod:`pyNN.descriptions`).

        If template is None, then a dictionary containing the template\
        context will be returned.
        """

        parameters = dict()
        for parameter_name in self.__model.default_parameters:
            parameters[parameter_name] = self.get_value(parameter_name)

        context = {
            "name": self.__model_name,
            "default_parameters": self.__model.default_parameters,
            "default_initial_values": self.__model.default_parameters,
            "parameters": parameters,
        }
        return context
