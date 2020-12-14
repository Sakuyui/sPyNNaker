# Copyright (c) 2017-2020The University of Manchester
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
import ctypes
from collections import namedtuple

from spinn_utilities.abstract_base import abstractproperty, abstractmethod
from spinn_utilities.overrides import overrides

from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl)
from spynnaker.pyNN.models.abstract_models import (
    AbstractReadParametersBeforeSet)
from spynnaker.pyNN.utilities.constants import SPIKE_PARTITION_ID
from spinn_front_end_common.utilities import helpful_functions


get_placement_details = \
    ProvidesProvenanceDataFromMachineImpl._get_placement_details
add_name = ProvidesProvenanceDataFromMachineImpl._add_name


class NeuronProvenance(ctypes.LittleEndianStructure):
    """ Provenance items from neuron processing
    """
    _fields_ = [
        # The timer tick at the end of simulation
        ("current_timer_tick", ctypes.c_uint32),
        # The number of misses of TDMA time slots
        ("n_tdma_misses", ctypes.c_uint32)
    ]

    N_ITEMS = len(_fields_)


# Identifiers for neuron regions
NeuronRegions = namedtuple(
    "NeuronRegions",
    ["neuron_params", "neuron_recording"])


class PopulationMachineNeurons(AbstractReadParametersBeforeSet):
    """ Mix-in for machine vertices that have neurons in them
    """

    # This MUST stay empty to allow mixing with other things with slots
    __slots__ = []

    @abstractproperty
    def _app_vertex(self):
        """ The application vertex of the machine vertex.

        :note: This is likely to be available via the MachineVertex.

        :rtype: AbstractPopulationVertex
        """

    @abstractproperty
    def _vertex_slice(self):
        """ The slice of the application vertex atoms on this machine vertex.

        :note: This is likely to be available via the MachineVertex.

        :rtype: ~pacman.model.graphs.common.Slice
        """

    @abstractproperty
    def _key(self):
        """ The key for spikes.

        :rtype: int
        """

    @abstractmethod
    def _set_key(self, key):
        """ Set the key for spikes.

        :note: This is required because this class cannot have any storage.

        :param int key: The key to be set
        """

    @abstractproperty
    def _neuron_regions(self):
        """ The region identifiers for the neuron regions

        :rtype: .NeuronRegions
        """

    def _append_neuron_provenance(
            self, provenance_items, prov_list_from_machine, offset, placement):
        """ Extract and add neuron provenance to the list of provenance items

        :param
            list(~spinn_front_end_common.utilities.utility_objs.ProvenanceDataItem)\
            provenance_items: The items already read, to append to
        :param list(int) prov_list_from_machine:
            The values read from the machine to be decoded
        :param int offset: Where in the list from the machine to start reading
        :param ~pacman.model.placements.Placement placement:
            Which vertex are we retrieving from, and where was it
        :return: The number of items read from the prov_list_from_machine
        :type: int
        """
        _, x, y, p, names = get_placement_details(placement)
        neuron_prov = NeuronProvenance(
            *prov_list_from_machine[offset:NeuronProvenance.N_ITEMS + offset])

        provenance_items.append(ProvenanceDataItem(
            add_name(names, "Last_timer_tic_the_core_ran_to"),
            neuron_prov.current_timer_tick))
        provenance_items.append(self._app_vertex.get_tdma_provenance_item(
            names, x, y, p, neuron_prov.n_tdma_misses))

        return NeuronProvenance.N_ITEMS

    def _write_neuron_data_spec(self, spec, routing_info):
        """ Write the data specification of the neuron data

        :param ~data_specification.DataSpecificationGenerator spec:
            The data specification to write to
        :param ~pacman.model.routing_info.RoutingInfo routing_info:
            The routing information to read the key from
        """
        # Get and store the key
        self._set_key(routing_info.get_first_key_from_pre_vertex(
            self, SPIKE_PARTITION_ID))

        # Write the neuron parameters
        self._write_neuron_parameters(spec)

        # Write the neuron recording region
        neuron_recorder = self._app_vertex.neuron_recorder
        spec.reserve_memory_region(
            region=self._neuron_regions.neuron_recording,
            size=neuron_recorder.get_metadata_sdram_usage_in_bytes(
                self._vertex_slice),
            label="neuron recording")
        neuron_recorder.write_neuron_recording_region(
            spec, self._neuron_regions.neuron_recording, self._vertex_slice)

    def _write_neuron_parameters(self, spec):
        """ Write the neuron parameters region

        :param ~data_specification.DataSpecificationGenerator spec:
            The data specification to write to
        """
        self._app_vertex.update_state_variables()

        # pylint: disable=too-many-arguments
        n_atoms = self._vertex_slice.n_atoms
        spec.comment("\nWriting Neuron Parameters for {} Neurons:\n".format(
            n_atoms))

        # Reserve and switch to the memory region
        params_size = self._app_vertex.get_sdram_usage_for_neuron_params(
            self.vertex_slice)
        spec.reserve_memory_region(
            region=self._neuron_regions.neuron_params, size=params_size,
            label='NeuronParams')
        spec.switch_write_focus(self._neuron_regions.neuron_params)

        # store the tdma data here for this slice.
        data = self._app_vertex.generate_tdma_data_specification_data(
            self._app_vertex.vertex_slices.index(self.vertex_slice))
        spec.write_array(data)

        # Write whether the key is to be used, and then the key, or 0 if it
        # isn't to be used
        if self._key is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)
            spec.write_value(data=self._key)

        # Write the number of neurons in the block:
        spec.write_value(data=n_atoms)

        # Write the neuron parameters
        neuron_data = self._app_vertex.neuron_impl.get_data(
            self._app_vertex.parameters, self._app_vertex.state_variables,
            self._vertex_slice)
        spec.write_array(neuron_data)

    @overrides(AbstractReadParametersBeforeSet.read_parameters_from_machine)
    def read_parameters_from_machine(
            self, transceiver, placement, vertex_slice):

        # locate SDRAM address to where the neuron parameters are stored
        neuron_region_sdram_address = \
            helpful_functions.locate_memory_region_for_placement(
                placement, self._neuron_regions.neuron_params,
                transceiver)

        # shift past the extra stuff before neuron parameters that we don't
        # need to read
        neuron_parameters_sdram_address = (
            neuron_region_sdram_address +
            self._app_vertex.tdma_sdram_size_in_bytes +
            self._app_vertex.BYTES_TILL_START_OF_GLOBAL_PARAMETERS)

        # get size of neuron params
        size_of_region = self._app_vertex.get_sdram_usage_for_neuron_params(
            vertex_slice)
        size_of_region -= (
            self._app_vertex.BYTES_TILL_START_OF_GLOBAL_PARAMETERS +
            self._app_vertex.tdma_sdram_size_in_bytes)

        # get data from the machine
        byte_array = transceiver.read_memory(
            placement.x, placement.y, neuron_parameters_sdram_address,
            size_of_region)

        # update python neuron parameters with the data
        self._app_vertex.neuron_impl.read_data(
            byte_array, 0, vertex_slice, self._app_vertex.parameters,
            self._app_vertex.state_variables)
