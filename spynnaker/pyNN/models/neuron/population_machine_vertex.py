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

from enum import IntEnum
from spinn_utilities.overrides import overrides
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.machine import MachineVertex
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl)
from spinn_front_end_common.interface.buffer_management.buffer_models import (
    AbstractReceiveBuffersToHost)
from spinn_front_end_common.utilities.helpful_functions import (
    locate_memory_region_for_placement)
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractSupportsBitFieldGeneration,
    AbstractSupportsBitFieldRoutingCompression,
    AbstractGeneratesDataSpecification, AbstractRewritesDataSpecification)
from spinn_front_end_common.interface.profiling import (
    AbstractHasProfileData, profile_utils)
from spinn_front_end_common.interface.profiling.profile_utils import (
    get_profiling_data)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities import (
    constants as common_constants, helpful_functions)
from spinn_front_end_common.interface.simulation import simulation_utilities
from spynnaker.pyNN.models.neuron.synapse_dynamics import (
    AbstractSynapseDynamicsStructural)
from spynnaker.pyNN.utilities import constants, bit_field_utilities
from spynnaker.pyNN.models.abstract_models import (
    AbstractSynapseExpandable, AbstractReadParametersBeforeSet)
from spynnaker.pyNN.utilities.constants import POPULATION_BASED_REGIONS
from spynnaker.pyNN.models.current_sources import CurrentSourceIDs
from spynnaker.pyNN.utilities.utility_calls import convert_to


class PopulationMachineVertex(
        MachineVertex, AbstractReceiveBuffersToHost,
        AbstractHasAssociatedBinary, ProvidesProvenanceDataFromMachineImpl,
        AbstractHasProfileData, AbstractSupportsBitFieldGeneration,
        AbstractSupportsBitFieldRoutingCompression,
        AbstractGeneratesDataSpecification, AbstractSynapseExpandable,
        AbstractRewritesDataSpecification, AbstractReadParametersBeforeSet):

    __slots__ = [
        "__binary_file_name",
        "__recorded_region_ids",
        "__resources",
        "__on_chip_generatable_offset",
        "__on_chip_generatable_size",
        "__drop_late_spikes",
        "__change_requires_neuron_parameters_reload"]

    class EXTRA_PROVENANCE_DATA_ENTRIES(IntEnum):
        """ Entries for the provenance data generated by standard neuron \
            models.
        """
        #: The number of pre-synaptic events
        PRE_SYNAPTIC_EVENT_COUNT = 0
        #: The number of times the synapse arithmetic saturated
        SATURATION_COUNT = 1
        #: The number of times there was a buffer overflow
        BUFFER_OVERFLOW_COUNT = 2
        #: The current timer tick
        CURRENT_TIMER_TIC = 3
        #: The number of times the plastic synapses saturated during weight
        #: calculation
        PLASTIC_SYNAPTIC_WEIGHT_SATURATION_COUNT = 4
        GHOST_POP_TABLE_SEARCHES = 5
        FAILED_TO_READ_BIT_FIELDS = 6
        DMA_COMPLETES = 7
        SPIKE_PROGRESSING_COUNT = 8
        INVALID_MASTER_POP_HITS = 9
        BIT_FIELD_FILTERED_COUNT = 10
        N_REWIRES = 11
        #: The number of packets that were dropped as they arrived too late
        #: to be processed
        N_LATE_SPIKES = 12
        #: The max filled size of the input buffer
        INPUT_BUFFER_FILLED_SIZE = 13
        #: The number of TDMA misses
        TDMA_MISSES = 14
        # the maxmimum number of background tasks queued
        MAX_BACKGROUND_QUEUED = 15
        # the number of times the background queue overloaded
        N_BACKGROUND_OVERLOADS = 16

    _PROFILE_TAG_LABELS = {
        0: "TIMER",
        1: "DMA_READ",
        2: "INCOMING_SPIKE",
        3: "PROCESS_FIXED_SYNAPSES",
        4: "PROCESS_PLASTIC_SYNAPSES"}

    # x words needed for a bitfield covering 256 atoms
    _WORDS_TO_COVER_256_ATOMS = 8

    # provenance data items
    SATURATION_COUNT_NAME = "Times_synaptic_weights_have_saturated"
    INPUT_BUFFER_FULL_NAME = "Times_the_input_buffer_lost_packets"
    TOTAL_PRE_SYNAPTIC_EVENT_NAME = "Total_pre_synaptic_events"
    LAST_TIMER_TICK_NAME = "Last_timer_tic_the_core_ran_to"
    N_RE_WIRES_NAME = "Number_of_rewires"
    SATURATED_PLASTIC_WEIGHTS_NAME = (
        "Times_plastic_synaptic_weights_have_saturated")
    _N_LATE_SPIKES_NAME = "Number_of_late_spikes"
    _MAX_FILLED_SIZE_OF_INPUT_BUFFER_NAME = "Max_filled_size_input_buffer"
    _BACKGROUND_OVERLOADS_NAME = "Times_the_background_queue_overloaded"
    _BACKGROUND_MAX_QUEUED_NAME = "Max_backgrounds_queued"
    BIT_FIELD_FILTERED_PACKETS = (
        "How many packets were filtered by the bitfield filterer.")
    INVALID_MASTER_POP_HITS = "Invalid Master Pop hits"
    SPIKES_PROCESSED = "how many spikes were processed"
    DMA_COMPLETE = "DMA's that were completed"
    BIT_FIELDS_NOT_READ = "N bit fields not able to be read into DTCM"
    GHOST_SEARCHES = "Number of failed pop table searches"
    PLASTIC_WEIGHT_SATURATION = "Times_plastic_synaptic_weights_have_saturated"
    LAST_TIMER_TICK = "Last_timer_tic_the_core_ran_to"
    TOTAL_PRE_SYNAPTIC_EVENTS = "Total_pre_synaptic_events"
    LOST_INPUT_BUFFER_PACKETS = "Times_the_input_buffer_lost_packets"

    N_ADDITIONAL_PROVENANCE_DATA_ITEMS = len(EXTRA_PROVENANCE_DATA_ENTRIES)

    def __init__(
            self, resources_required, recorded_region_ids, label, constraints,
            app_vertex, vertex_slice, drop_late_spikes, binary_file_name):
        """
        :param ~pacman.model.resources.ResourceContainer resources_required:
        :param iterable(int) recorded_region_ids:
        :param str label:
        :param bool drop_late_spikes: control flag for dropping packets.
        :param list(~pacman.model.constraints.AbstractConstraint) constraints:
        :param AbstractPopulationVertex app_vertex:
            The associated application vertex
        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of the population that this implements
        :param str binary_file_name: binary name to be run for this verte
        """
        super().__init__(label, constraints, app_vertex, vertex_slice)
        self.__binary_file_name = binary_file_name
        self.__recorded_region_ids = recorded_region_ids
        self.__resources = resources_required
        self.__drop_late_spikes = drop_late_spikes
        self.__on_chip_generatable_offset = None
        self.__on_chip_generatable_size = None
        self.__change_requires_neuron_parameters_reload = False

    def set_on_chip_generatable_area(self, offset, size):
        self.__on_chip_generatable_offset = offset
        self.__on_chip_generatable_size = size

    @overrides(AbstractSupportsBitFieldGeneration.bit_field_base_address)
    def bit_field_base_address(self, transceiver, placement):
        return locate_memory_region_for_placement(
            placement=placement, transceiver=transceiver,
            region=POPULATION_BASED_REGIONS.BIT_FIELD_FILTER.value)

    @overrides(AbstractSupportsBitFieldRoutingCompression.
               key_to_atom_map_region_base_address)
    def key_to_atom_map_region_base_address(self, transceiver, placement):
        return locate_memory_region_for_placement(
            placement=placement, transceiver=transceiver,
            region=POPULATION_BASED_REGIONS.BIT_FIELD_KEY_MAP.value)

    @overrides(AbstractSupportsBitFieldGeneration.bit_field_builder_region)
    def bit_field_builder_region(self, transceiver, placement):
        return locate_memory_region_for_placement(
            placement=placement, transceiver=transceiver,
            region=POPULATION_BASED_REGIONS.BIT_FIELD_BUILDER.value)

    @overrides(AbstractSupportsBitFieldRoutingCompression.
               regeneratable_sdram_blocks_and_sizes)
    def regeneratable_sdram_blocks_and_sizes(self, transceiver, placement):
        synaptic_matrix_base_address = locate_memory_region_for_placement(
            placement=placement, transceiver=transceiver,
            region=POPULATION_BASED_REGIONS.SYNAPTIC_MATRIX.value)
        return [(
            self.__on_chip_generatable_offset + synaptic_matrix_base_address,
            self.__on_chip_generatable_size)]

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self.__resources

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return POPULATION_BASED_REGIONS.PROVENANCE_DATA.value

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return len(self.EXTRA_PROVENANCE_DATA_ENTRIES)

    @overrides(ProvidesProvenanceDataFromMachineImpl.
               get_provenance_data_from_machine)
    def get_provenance_data_from_machine(self, transceiver, placement):
        provenance_data = self._read_provenance_data(transceiver, placement)
        label, names = self._get_provenance_placement_description(placement)

        # This is why we have to override the superclass public method
        tic_overruns = 0
        for item in self.parse_system_provenance_items(
                label, names, provenance_data):
            yield item
            if item.names[-1] == self._TIMER_TICK_OVERRUN:
                # GOTCHA!
                tic_overruns = item.value

        # translate into provenance data items
        yield from self.__parse_prov_items(
            label, names, self._get_extra_provenance_words(provenance_data),
            tic_overruns)

    def __parse_prov_items(self, label, names, provenance_data, tic_overruns):
        # Would be parse_extra_provenance_items except for extra argument
        """
        :param str label:
        :param list(str) names:
        :param list(int) provenance_data:
        :param int tic_overruns:
        :rtype: iterable(ProvenanceDataItem)
        """
        (n_pre_synaptic_events, n_saturations, n_buffer_overflows,
         last_timer_tick, n_plastic_saturations, n_ghost_searches,
         n_bitfield_fails, dma_completes, spike_processing_count,
         invalid_master_pop_hits, n_packets_filtered, n_rewires,
         n_late_packets, input_buffer_max, tdma_misses, max_bg_queued,
         n_bg_overloads) = provenance_data

        # translate into provenance data items
        yield ProvenanceDataItem(
            names + [self.SATURATION_COUNT_NAME],
            n_saturations, (n_saturations > 0),
            f"The weights from the synapses for {label} saturated "
            f"{n_saturations} times. If this causes issues you can increase "
            "the spikes_per_second and / or ring_buffer_sigma values located "
            "within the .spynnaker.cfg file.")
        yield ProvenanceDataItem(
            names + [self.INPUT_BUFFER_FULL_NAME],
            n_buffer_overflows, (n_buffer_overflows > 0),
            f"The input buffer for {label} lost packets on "
            f"{n_buffer_overflows} occasions. This is often a sign that the "
            "system is running too quickly for the number of neurons per "
            "core.  Please increase the timer_tic or time_scale_factor or "
            "decrease the number of neurons per core.")
        yield ProvenanceDataItem(
            names + [self.TOTAL_PRE_SYNAPTIC_EVENT_NAME],
            n_pre_synaptic_events)
        yield ProvenanceDataItem(
            names + [self.LAST_TIMER_TICK_NAME], last_timer_tick)
        yield ProvenanceDataItem(
            names + [self.SATURATED_PLASTIC_WEIGHTS_NAME],
            n_plastic_saturations, (n_plastic_saturations > 0),
            f"The weights from the plastic synapses for {label} saturated "
            f"{n_plastic_saturations} times. If this causes issue increase "
            "the spikes_per_second and / or ring_buffer_sigma values located "
            "within the .spynnaker.cfg file.")
        yield ProvenanceDataItem(
            names + [self.N_RE_WIRES_NAME], n_rewires)
        yield ProvenanceDataItem(
            names + [self.GHOST_SEARCHES], n_ghost_searches,
            (n_ghost_searches > 0),
            f"The number of failed population table searches for {label} was "
            f"{n_ghost_searches}. If this number is large relative to the "
            "predicted incoming spike rate, try increasing source and target "
            "neurons per core")
        yield ProvenanceDataItem(
            names + [self.BIT_FIELDS_NOT_READ],
            n_bitfield_fails, False,
            f"On {label}, the filter for stopping redundant DMAs couldn't be "
            f"fully filled in; it failed to read {n_bitfield_fails} entries, "
            "which means it required a max of "
            f"{n_bitfield_fails * self._WORDS_TO_COVER_256_ATOMS} "
            "extra bytes of DTCM (assuming cores have at most 255 neurons). "
            "Try reducing neurons per core, or size of buffers, or neuron "
            "params per neuron, etc.")
        yield ProvenanceDataItem(
            names + [self.DMA_COMPLETE], dma_completes)
        yield ProvenanceDataItem(
            names + [self.SPIKES_PROCESSED],
            spike_processing_count)
        yield ProvenanceDataItem(
            names + [self.INVALID_MASTER_POP_HITS],
            invalid_master_pop_hits, (invalid_master_pop_hits > 0),
            f"On {label}, there were {invalid_master_pop_hits} keys received "
            "that had no master pop entry for them. This is an error, which "
            "most likely stems from bad routing.")
        yield ProvenanceDataItem(
            names + [self.BIT_FIELD_FILTERED_PACKETS],
            n_packets_filtered, (n_packets_filtered > 0 and (
                n_buffer_overflows > 0 or tic_overruns > 0)),
            f"On {label}, there were {n_packets_filtered} packets received "
            "that were filtered by the bit-field filterer on the core. These "
            "packets were having to be stored and processed on core, which "
            "means the core may not be running as efficiently as it should. "
            "Please adjust the network or the mapping so that these packets "
            "are filtered in the router to improve performance.")

        late_message = (
            f"On {label}, {n_late_packets} packets were dropped from the "
            "input buffer, because they arrived too late to be processed in "
            "a given time step. Try increasing the time_scale_factor located "
            "within the .spynnaker.cfg file or in the pynn.setup() method."
            if self.__drop_late_spikes else
            f"On {label}, {n_late_packets} packets arrived too late to be "
            "processed in a given time step. Try increasing the "
            "time_scale_factor located within the .spynnaker.cfg file or in "
            "the pynn.setup() method.")
        yield ProvenanceDataItem(
            names + [self._N_LATE_SPIKES_NAME],
            n_late_packets, (n_late_packets > 0), late_message)

        yield ProvenanceDataItem(
            names + [self._MAX_FILLED_SIZE_OF_INPUT_BUFFER_NAME],
            input_buffer_max, report=False)

        yield self._app_vertex.get_tdma_provenance_item(
            names, label, tdma_misses)

        yield ProvenanceDataItem(
            names + [self._BACKGROUND_MAX_QUEUED_NAME],
            max_bg_queued, (max_bg_queued > 1),
            f"On {label}, a maximum of {max_bg_queued} background tasks were "
            "queued, which can indicate a core overloading. Try increasing "
            "the time_scale_factor located within the .spynnaker.cfg file or "
            "in the pynn.setup() method.")
        yield ProvenanceDataItem(
            names + [self._BACKGROUND_OVERLOADS_NAME],
            n_bg_overloads, (n_bg_overloads > 0),
            f"On {label}, the background queue overloaded {n_bg_overloads} "
            "times, which can indicate a core overloading. Try increasing "
            "the time_scale_factor located within the .spynnaker.cfg file or "
            "in the pynn.setup() method.")

    @overrides(AbstractReceiveBuffersToHost.get_recorded_region_ids)
    def get_recorded_region_ids(self):
        return self.__recorded_region_ids

    @overrides(AbstractReceiveBuffersToHost.get_recording_region_base_address)
    def get_recording_region_base_address(self, txrx, placement):
        return locate_memory_region_for_placement(
            placement, POPULATION_BASED_REGIONS.NEURON_RECORDING.value, txrx)

    @overrides(AbstractHasProfileData.get_profile_data)
    def get_profile_data(self, transceiver, placement):
        return get_profiling_data(
            POPULATION_BASED_REGIONS.PROFILING.value,
            self._PROFILE_TAG_LABELS, transceiver, placement)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self.__binary_file_name

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "application_graph": "MemoryApplicationGraph",
        "machine_graph": "MemoryMachineGraph",
        "routing_info": "MemoryRoutingInfos",
        "data_n_time_steps": "DataNTimeSteps",
        "n_key_map": "MemoryMachinePartitionNKeysMap"
    })
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor",
            "application_graph", "machine_graph", "routing_info",
            "data_n_time_steps", "n_key_map"
        })
    def generate_data_specification(
            self, spec, placement, machine_time_step, time_scale_factor,
            application_graph, machine_graph, routing_info, data_n_time_steps,
            n_key_map):
        """
        :param machine_time_step: (injected)
        :param time_scale_factor: (injected)
        :param application_graph: (injected)
        :param machine_graph: (injected)
        :param routing_info: (injected)
        :param data_n_time_steps: (injected)
        :param n_key_map: (injected)
        """
        # pylint: disable=too-many-arguments, arguments-differ

        spec.comment("\n*** Spec for block of {} neurons ***\n".format(
            self._app_vertex.neuron_impl.model_name))

        # Reserve memory regions
        self._reserve_memory_regions(spec, machine_graph, n_key_map)

        # Declare random number generators and distributions:
        # TODO add random distribution stuff
        # self.write_random_distribution_declarations(spec)

        # Get the key
        key = routing_info.get_first_key_from_pre_vertex(
            self, constants.SPIKE_PARTITION_ID)

        # Write the setup region
        spec.switch_write_focus(POPULATION_BASED_REGIONS.SYSTEM.value)
        spec.write_array(simulation_utilities.get_simulation_header_array(
            self.__binary_file_name, machine_time_step, time_scale_factor))

        # Write the neuron recording region
        self._app_vertex.neuron_recorder.write_neuron_recording_region(
            spec, POPULATION_BASED_REGIONS.NEURON_RECORDING.value,
            self.vertex_slice, data_n_time_steps)

        # Write the neuron parameters
        self._write_neuron_parameters(
            spec, key, POPULATION_BASED_REGIONS.NEURON_PARAMS.value)

        # Write the current source parameters
        if self._app_vertex.current_source is not None:
            self._write_current_source_parameters(
                spec, key,
                POPULATION_BASED_REGIONS.CURRENT_SOURCE_PARAMS.value)

        # write profile data
        profile_utils.write_profile_region_data(
            spec, POPULATION_BASED_REGIONS.PROFILING.value,
            self._app_vertex.n_profile_samples)

        # Get the weight_scale value from the appropriate location
        weight_scale = self._app_vertex.neuron_impl.get_global_weight_scale()

        # allow the synaptic matrix to write its data spec-able data
        self._app_vertex.synapse_manager.write_data_spec(
            spec, self._app_vertex, self.vertex_slice, self, machine_graph,
            application_graph, routing_info, weight_scale, machine_time_step)
        self.set_on_chip_generatable_area(
            self._app_vertex.synapse_manager.host_written_matrix_size(
                self.vertex_slice),
            self._app_vertex.synapse_manager.on_chip_written_matrix_size(
                self.vertex_slice))

        # write up the bitfield builder data
        bit_field_utilities.write_bitfield_init_data(
            spec, self, machine_graph, routing_info,
            n_key_map, POPULATION_BASED_REGIONS.BIT_FIELD_BUILDER.value,
            POPULATION_BASED_REGIONS.POPULATION_TABLE.value,
            POPULATION_BASED_REGIONS.SYNAPTIC_MATRIX.value,
            POPULATION_BASED_REGIONS.DIRECT_MATRIX.value,
            POPULATION_BASED_REGIONS.BIT_FIELD_FILTER.value,
            POPULATION_BASED_REGIONS.BIT_FIELD_KEY_MAP.value,
            POPULATION_BASED_REGIONS.STRUCTURAL_DYNAMICS.value,
            isinstance(
                self._app_vertex.synapse_manager.synapse_dynamics,
                AbstractSynapseDynamicsStructural))

        # End the writing of this specification:
        spec.end_specification()

    @inject_items({"routing_info": "MemoryRoutingInfos"})
    @overrides(
        AbstractRewritesDataSpecification.regenerate_data_specification,
        additional_arguments={"routing_info"})
    def regenerate_data_specification(self, spec, placement, routing_info):
        # pylint: disable=too-many-arguments, arguments-differ

        # reserve the neuron parameters data region
        self._reserve_neuron_params_data_region(spec)

        # write the neuron params into the new DSG region
        self._write_neuron_parameters(
            key=routing_info.get_first_key_from_pre_vertex(
                self, constants.SPIKE_PARTITION_ID),
            spec=spec,
            region_id=constants.POPULATION_BASED_REGIONS.NEURON_PARAMS.value)

        # close spec
        spec.end_specification()

    @overrides(AbstractRewritesDataSpecification.reload_required)
    def reload_required(self):
        return self.__change_requires_neuron_parameters_reload

    @overrides(AbstractRewritesDataSpecification.set_reload_required)
    def set_reload_required(self, new_value):
        self.__change_requires_neuron_parameters_reload = new_value

    def _reserve_memory_regions(self, spec, machine_graph, n_key_map):
        """ Reserve the DSG data regions.

        :param ~.DataSpecificationGenerator spec:
            the spec to write the DSG region to
        :param ~.MachineGraph machine_graph: machine graph
        :param n_key_map: n key map
        :return: None
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=POPULATION_BASED_REGIONS.SYSTEM.value,
            size=common_constants.SIMULATION_N_BYTES,
            label='System')

        self._reserve_neuron_params_data_region(spec)

        self._reserve_current_source_params_data_region(spec)

        spec.reserve_memory_region(
            region=POPULATION_BASED_REGIONS.NEURON_RECORDING.value,
            size=self._app_vertex.neuron_recorder.get_exact_static_sdram_usage(
                self.vertex_slice),
            label="neuron recording")

        profile_utils.reserve_profile_region(
            spec, POPULATION_BASED_REGIONS.PROFILING.value,
            self._app_vertex.n_profile_samples)

        # reserve bit field region
        bit_field_utilities.reserve_bit_field_regions(
            spec, machine_graph, n_key_map, self,
            POPULATION_BASED_REGIONS.BIT_FIELD_BUILDER.value,
            POPULATION_BASED_REGIONS.BIT_FIELD_FILTER.value,
            POPULATION_BASED_REGIONS.BIT_FIELD_KEY_MAP.value)

        self.reserve_provenance_data_region(spec)

    @staticmethod
    def neuron_region_sdram_address(placement, transceiver):
        return helpful_functions.locate_memory_region_for_placement(
                placement, POPULATION_BASED_REGIONS.NEURON_PARAMS.value,
                transceiver)

    def _reserve_neuron_params_data_region(self, spec):
        """ Reserve the neuron parameter data region.

        :param ~data_specification.DataSpecificationGenerator spec:
            the spec to write the DSG region to
        :return: None
        """
        params_size = self._app_vertex.get_sdram_usage_for_neuron_params(
            self.vertex_slice)
        spec.reserve_memory_region(
            region=POPULATION_BASED_REGIONS.NEURON_PARAMS.value,
            size=params_size, label='NeuronParams')

    def _reserve_current_source_params_data_region(self, spec):
        """ Reserve the current_source parameter data region.

        :param ~data_specification.DataSpecificationGenerator spec:
            the spec to write the DSG region to
        :return: None
        """
        params_size = self._app_vertex.\
            get_sdram_usage_for_current_source_params(self.vertex_slice)
        if params_size:
            spec.reserve_memory_region(
                region=POPULATION_BASED_REGIONS.CURRENT_SOURCE_PARAMS.value,
                size=params_size, label='CurrentSourceParams')

    def _write_neuron_parameters(self, spec, key, region_id):

        self._app_vertex.set_has_run()

        # pylint: disable=too-many-arguments
        n_atoms = self.vertex_slice.n_atoms
        spec.comment("\nWriting Neuron Parameters for {} Neurons:\n".format(
            n_atoms))

        # Set the focus to the memory region:
        spec.switch_write_focus(region_id)

        # store the tdma data here for this slice.
        data = self._app_vertex.generate_tdma_data_specification_data(
            self._app_vertex.vertex_slices.index(self.vertex_slice))
        spec.write_array(data)

        # Write whether the key is to be used, and then the key, or 0 if it
        # isn't to be used
        if key is None:
            spec.write_value(data=0)
            spec.write_value(data=0)
        else:
            spec.write_value(data=1)
            spec.write_value(data=key)

        # Write the number of neurons in the block:
        spec.write_value(data=n_atoms)

        # Write the number of synapse types
        spec.write_value(
            data=self._app_vertex.neuron_impl.get_n_synapse_types())

        # Write the size of the incoming spike buffer
        spec.write_value(data=self._app_vertex.incoming_spike_buffer_size)

        # Write the neuron parameters
        neuron_data = self._app_vertex.neuron_impl.get_data(
            self._app_vertex.parameters, self._app_vertex.state_variables,
            self.vertex_slice)
        spec.write_array(neuron_data)

    def _write_current_source_parameters(self, spec, key, region_id):
        # pylint: disable=too-many-arguments
        n_atoms = self.vertex_slice.n_atoms
        spec.comment(
            "\nWriting Current Source Parameters for {} Neurons:\n".format(
                n_atoms))

        # Set the focus to the memory region:
        spec.switch_write_focus(region_id)

        # Now write the hash associated with the
        current_source = self.app_vertex.current_source

        # Generally speaking the parameters are single-valued dicts
        cs_id = current_source.current_source_id
        spec.write_value(cs_id)
        cs_data_types = current_source.get_parameter_types
        for key, value in current_source.get_parameters.items():
            # StepCurrentSource and ACSource are currently handled with arrays
            if ((cs_id == CurrentSourceIDs.STEP_CURRENT_SOURCE.value) or (
                    cs_id == CurrentSourceIDs.AC_SOURCE.value)):
                n_params = len(current_source.get_parameters[key])
                spec.write_value(n_params)
                for n in range(n_params):
                    value_convert = convert_to(
                        value[n], cs_data_types[key]).view("uint32")
                    spec.write_value(data=value_convert)
            # DCSource and NoisyCurrentSource just have single-valued params
            else:
                if hasattr(value, "__getitem__"):
                    for n in range(len(value)):
                        value_convert = convert_to(
                            value[n], cs_data_types[key]).view("uint32")
                        spec.write_value(data=value_convert)
                else:
                    value_convert = convert_to(
                        value, cs_data_types[key]).view("uint32")
                    spec.write_value(data=value_convert)

    @overrides(AbstractSynapseExpandable.gen_on_machine)
    def gen_on_machine(self):
        return self.app_vertex.synapse_manager.gen_on_machine(
            self.vertex_slice)

    @overrides(AbstractSynapseExpandable.read_generated_connection_holders)
    def read_generated_connection_holders(self, transceiver, placement):
        self._app_vertex.synapse_manager.read_generated_connection_holders(
            transceiver, placement)

    @overrides(AbstractReadParametersBeforeSet.read_parameters_from_machine)
    def read_parameters_from_machine(
            self, transceiver, placement, vertex_slice):

        # locate SDRAM address to where the neuron parameters are stored
        neuron_region_sdram_address = self.neuron_region_sdram_address(
            placement, transceiver)

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
