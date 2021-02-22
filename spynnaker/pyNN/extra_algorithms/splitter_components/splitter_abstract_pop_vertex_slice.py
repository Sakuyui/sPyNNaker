# Copyright (c) 2020-2021 The University of Manchester
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
from pacman.exceptions import PacmanConfigurationException
from pacman.model.constraints.partitioner_constraints import (
    MaxVertexAtomsConstraint, FixedVertexAtomsConstraint,
    AbstractPartitionerConstraint)
from pacman.model.graphs.machine import MachineEdge
from pacman.model.resources import (
    ResourceContainer, DTCMResource, CPUCyclesPerTickResource,
    MultiRegionSDRAM)
from pacman.model.partitioner_splitters.abstract_splitters import (
    AbstractSplitterSlice)
from pacman.utilities import utility_calls
from spynnaker.pyNN.models.neuron import (
    AbstractPopulationVertex, PopulationMachineVertex)
from spynnaker.pyNN.models.neuron.population_machine_vertex import (
    NeuronProvenance, SynapseProvenance)
from spynnaker.pyNN.models.neuron.master_pop_table import (
    MasterPopTableAsBinarySearch)
from .abstract_spynnaker_splitter_delay import AbstractSpynnakerSplitterDelay
from spynnaker.pyNN.utilities.bit_field_utilities import (
    get_estimated_sdram_for_bit_field_region,
    get_estimated_sdram_for_key_region,
    exact_sdram_for_bit_field_builder_region)


class SplitterAbstractPopulationVertexSlice(
        AbstractSplitterSlice, AbstractSpynnakerSplitterDelay):
    """ handles the splitting of the AbstractPopulationVertex via slice logic.
    """

    __slots__ = [
        "__ring_buffer_shifts",
        "__weight_scales",
        "__all_syn_block_sz",
        "__structural_sz",
        "__synapse_expander_sz",
        "__bitfield_sz",
        "__next_index"
    ]

    SPLITTER_NAME = "SplitterAbstractPopulationVertexSlice"

    INVALID_POP_ERROR_MESSAGE = (
        "The vertex {} cannot be supported by the "
        "SplitterAbstractPopulationVertexSlice as"
        " the only vertex supported by this splitter is a "
        "AbstractPopulationVertex. Please use the correct splitter for "
        "your vertex and try again.")

    def __init__(self):
        super().__init__(self.SPLITTER_NAME)
        self.__ring_buffer_shifts = None
        self.__weight_scales = None
        self.__all_syn_block_sz = dict()
        self.__structural_sz = dict()
        self.__synapse_expander_sz = None
        self.__bitfield_sz = None
        self.__next_index = 0

    @overrides(AbstractSplitterSlice.set_governed_app_vertex)
    def set_governed_app_vertex(self, app_vertex):
        super().set_governed_app_vertex(app_vertex)
        if not isinstance(app_vertex, AbstractPopulationVertex):
            raise PacmanConfigurationException(
                self.INVALID_POP_ERROR_MESSAGE.format(app_vertex))

    @overrides(AbstractSplitterSlice.get_out_going_vertices)
    def get_out_going_vertices(self, edge, outgoing_edge_partition):
        return self._get_map([MachineEdge])

    @overrides(AbstractSplitterSlice.get_in_coming_vertices)
    def get_in_coming_vertices(
            self, edge, outgoing_edge_partition, src_machine_vertex):
        return self._get_map([MachineEdge])

    @overrides(AbstractSplitterSlice.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources, label, remaining_constraints):

        if self.__ring_buffer_shifts is None:
            app_vertex = self._governed_app_vertex
            self.__ring_buffer_shifts = app_vertex.get_ring_buffer_shifts(
                app_vertex.incoming_projections)
            self.__weight_scales = app_vertex.get_weight_scales(
                self.__ring_buffer_shifts)

        index = self.__next_index
        self.__next_index += 1
        return PopulationMachineVertex(
            resources, label, remaining_constraints, self._governed_app_vertex,
            vertex_slice, index, self.__ring_buffer_shifts,
            self.__weight_scales, self.__all_syn_block_size(vertex_slice),
            self.__structural_size(vertex_slice))

    @overrides(AbstractSplitterSlice.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        """  Gets the resources of a slice of atoms from a given app vertex.

        :param ~pacman.model.graphs.common.Slice vertex_slice: the slice
        :param ~pacman.model.graphs.machine.MachineGraph graph: app graph
        :rtype: ~pacman.model.resources.ResourceContainer
        """
        # pylint: disable=arguments-differ
        variable_sdram = self.__get_variable_sdram(vertex_slice)
        constant_sdram = self.__get_constant_sdram(vertex_slice)
        sdram = MultiRegionSDRAM()
        sdram.nest(len(PopulationMachineVertex.REGIONS) + 1, variable_sdram)
        sdram.merge(constant_sdram)

        # set resources required from this object
        container = ResourceContainer(
            sdram=sdram, dtcm=self.__get_dtcm_cost(vertex_slice),
            cpu_cycles=self.__get_cpu_cost(vertex_slice))

        # return the total resources.
        return container

    def __get_variable_sdram(self, vertex_slice):
        """ returns the variable sdram from the recorder.

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            the atom slice for recording sdram
        :return: the variable sdram used by the neuron recorder
        :rtype: VariableSDRAM
        """

        return (
            self._governed_app_vertex.get_neuron_variable_sdram(vertex_slice) +
            self._governed_app_vertex.get_synapse_variable_sdram(vertex_slice))

    def __get_constant_sdram(self, vertex_slice):
        """ returns the constant sdram used by the vertex slice.

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            the atoms to get constant sdram of
        :rtype: ConstantSDRAM
        """
        n_record = (
            len(self._governed_app_vertex.neuron_recordables) +
            len(self._governed_app_vertex.synapse_recordables))
        n_provenance = NeuronProvenance.N_ITEMS + SynapseProvenance.N_ITEMS
        sdram = MultiRegionSDRAM()
        sdram.merge(self._governed_app_vertex.get_common_constant_sdram(
            n_record, n_provenance, PopulationMachineVertex.COMMON_REGIONS))
        sdram.merge(self._governed_app_vertex.get_neuron_constant_sdram(
            vertex_slice, PopulationMachineVertex.NEURON_REGIONS))
        sdram.merge(self.__get_synapse_constant_sdram(vertex_slice))
        return sdram

    def __get_synapse_constant_sdram(self, vertex_slice):

        """ Get the amount of fixed SDRAM used by synapse parts

        :param ~pacman.model.graphs.common.Slice vertex_slice:
            The slice of neurons to get the size of

        :rtype: int
        """
        sdram = MultiRegionSDRAM()
        app_vertex = self._governed_app_vertex
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.synapse_params,
            app_vertex.get_synapse_params_size())
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.synapse_dynamics,
            app_vertex.get_synapse_dynamics_size(vertex_slice))
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.structural_dynamics,
            self.__structural_size(vertex_slice))
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.synaptic_matrix,
            self.__all_syn_block_size(vertex_slice))
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.direct_matrix,
            app_vertex.all_single_syn_size)
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.pop_table,
            MasterPopTableAsBinarySearch.get_master_population_table_size(
                app_vertex.incoming_projections))
        sdram.add_cost(
            PopulationMachineVertex.SYNAPSE_REGIONS.connection_builder,
            self.__synapse_expander_size())
        sdram.merge(self.__bitfield_size())
        return sdram

    def __all_syn_block_size(self, vertex_slice):
        if vertex_slice in self.__all_syn_block_sz:
            return self.__all_syn_block_sz[vertex_slice]
        all_syn_block_sz = self._governed_app_vertex.get_synapses_size(
            vertex_slice, self._governed_app_vertex.incoming_projections)
        self.__all_syn_block_sz[vertex_slice] = all_syn_block_sz
        return all_syn_block_sz

    def __structural_size(self, vertex_slice):
        if vertex_slice in self.__structural_sz:
            return self.__structural_sz[vertex_slice]
        structural_sz = self._governed_app_vertex.get_structural_dynamics_size(
            vertex_slice, self._governed_app_vertex.incoming_projections)
        self.__structural_sz[vertex_slice] = structural_sz
        return structural_sz

    def __synapse_expander_size(self):
        if self.__synapse_expander_sz is None:
            self.__synapse_expander_sz = \
                self._governed_app_vertex.get_synapse_expander_size(
                    self._governed_app_vertex.incoming_projections)
        return self.__synapse_expander_sz

    def __bitfield_size(self):
        if self.__bitfield_sz is None:
            sdram = MultiRegionSDRAM()
            projections = self._governed_app_vertex.incoming_projections
            sdram.add_cost(
                PopulationMachineVertex.SYNAPSE_REGIONS.bitfield_filter,
                get_estimated_sdram_for_bit_field_region(projections))
            sdram.add_cost(
                PopulationMachineVertex.SYNAPSE_REGIONS.bitfield_key_map,
                get_estimated_sdram_for_key_region(projections))
            sdram.add_cost(
                PopulationMachineVertex.SYNAPSE_REGIONS.bitfield_builder,
                exact_sdram_for_bit_field_builder_region())
            self.__bitfield_sz = sdram
        return self.__bitfield_sz

    def __get_dtcm_cost(self, vertex_slice):
        """ get the dtcm cost for the slice of atoms

        :param Slice vertex_slice: atom slice for dtcm calc.
        :rtype: DTCMResource
        """
        return DTCMResource(
            self._governed_app_vertex.get_common_dtcm() +
            self._governed_app_vertex.get_neuron_dtcm(vertex_slice) +
            self._governed_app_vertex.get_synapse_dtcm(vertex_slice))

    def __get_cpu_cost(self, vertex_slice):
        """ get cpu cost for a slice of atoms

        :param Slice vertex_slice: slice of atoms
        :rtype: CPUCyclesPerTickResourcer
        """
        return CPUCyclesPerTickResource(
            self._governed_app_vertex.get_common_cpu() +
            self._governed_app_vertex.get_neuron_cpu(vertex_slice) +
            self._governed_app_vertex.get_synapse_cpu(vertex_slice))

    @overrides(AbstractSplitterSlice.check_supported_constraints)
    def check_supported_constraints(self):
        utility_calls.check_algorithm_can_support_constraints(
            constrained_vertices=[self._governed_app_vertex],
            supported_constraints=[
                MaxVertexAtomsConstraint, FixedVertexAtomsConstraint],
            abstract_constraint_type=AbstractPartitionerConstraint)

    @overrides(AbstractSplitterSlice.reset_called)
    def reset_called(self):
        super(SplitterAbstractPopulationVertexSlice, self).reset_called()
        self.__ring_buffer_shifts = None
        self.__weight_scales = None
        self.__all_syn_block_sz = dict()
        self.__structural_sz = dict()
        self.__next_index = 0
