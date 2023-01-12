# Copyright (c) 2022 The University of Manchester
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
import neo
import numpy
from spinn_utilities.ranged.abstract_sized import AbstractSized
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spynnaker.pyNN.models.populations import Population
from spynnaker.pyNN.utilities.neo_buffer_database import NeoBufferDatabase

logger = FormatAdapter(logging.getLogger(__file__))
_SELECTIVE_RECORDED_MSG = (
    "Getting data on a whole population when selective recording was "
    "active will result in only the recorded neurons being returned "
    "in numerical order and without repeats.")


class DataPopulation(object):
    # Included here to due to circular init calls

    __slots__ = [
        "__database_file",
        "__label",
        "_indexes",
        "_size"]

    def __init__(self, database_file, label, indexes=None):
        self.__label = label
        self.__database_file = database_file
        # getting size right away also check the inputs or fails fast
        with NeoBufferDatabase(self.__database_file) as db:
            size = db.get_population_metdadata(label)[0]
        self._size = size
        if indexes is None:
            self._indexes = range(size)
        else:
            self._indexes = indexes

    @overrides(Population.write_data)
    def write_data(self, io, variables='all', gather=True, clear=False,
                   annotations=None):
        # pylint: disable=protected-access
        Population._check_params(gather, annotations)
        if clear:
            logger.warning("Ignoring clear as supported in this mode")
        if isinstance(io, str):
            io = neo.get_io(io)

        with NeoBufferDatabase(self.__database_file) as db:
            data = db.get_block(self.__label, variables, self._indexes)
        # write the neo block to the file
        io.write(data)

    @overrides(Population.describe)
    def describe(self, template=None, engine=None):
        if template is not None:
            logger.warning("Ignoring template as supported in this mode")
        if engine is not None:
            logger.warning("Ignoring engine as supported in this mode")
        with NeoBufferDatabase(self.__database_file) as db:
            _, _, description = db.get_population_metdadata(self.label)
            return description

    @overrides(Population.get_data)
    def get_data(
            self, variables='all', gather=True, clear=False, annotations=None):
        # pylint: disable=protected-access
        Population._check_params(gather, annotations)
        if clear:
            logger.warning("Ignoring clear as supported in this mode")
        with NeoBufferDatabase(self.__database_file) as db:
            return db.get_block(self.__label, variables, self._indexes,
                                annotations)

    @overrides(Population.spinnaker_get_data)
    def spinnaker_get_data(self, variable, as_matrix=False, view_indexes=None):
        if view_indexes:
            return self[view_indexes].spinnaker_get_data(variable, as_matrix)
        with NeoBufferDatabase(self.__database_file) as db:
            return db.spinnaker_get_data(
                self.__label, variable, as_matrix, self._indexes)

    @overrides(Population.get_spike_counts)
    def get_spike_counts(self, gather=True):
        # pylint: disable=protected-access
        Population._check_params(gather)
        with NeoBufferDatabase(self.__database_file) as db:
            return db.get_spike_counts(self.__label, self._indexes)

    @overrides(Population.find_units)
    def find_units(self, variable):
        with NeoBufferDatabase(self.__database_file) as db:
            (_, _, units) = db.get_recording_metadeta(self.__label, variable)
        return units

    def __len__(self):
        return self._size

    @property
    def label(self):
        return self.__label

    @property
    def local_size(self):
        return self._size

    @property
    def size(self):
        return self._size

    @overrides(Population.id_to_index)
    def id_to_index(self, id):  # @ReservedAssignment
        # pylint: disable=redefined-builtin
        # assuming not called often so not caching first id
        with NeoBufferDatabase(self.__database_file) as db:
            _, first_id, _ = db.get_population_metdadata(self.__label)
        last_id = self._size + first_id
        if not numpy.iterable(id):
            if not first_id <= id <= last_id:
                raise ValueError(
                    f"id should be in the range [{first_id},{last_id}], "
                    f"actually {id}")
            return int(id - first_id)  # assume IDs are consecutive
        return id - first_id

    @overrides(Population.index_to_id)
    def index_to_id(self, index):
        # assuming not called often so not caching first id
        with NeoBufferDatabase(self.__database_file) as db:
            _, first_id, _ = db.get_population_metdadata(self.__label)
        if not numpy.iterable(index):
            if index >= self._size:
                raise ValueError(
                    f"indexes should be in the range [0,{self._size}],"
                    f" actually {index}")
            return int(index + first_id)
        # this assumes IDs are consecutive
        return index + first_id

    def __getitem__(self, index_or_slice):
        """

        :param selector: a slice or numpy mask array.
            The mask array should either be a boolean array (ideally) of the
            same size as the parent,
            or an integer array containing cell indices,
            i.e. if `p.size == 5` then:

            ::

                PopulationView(p, array([False, False, True, False, True]))
                PopulationView(p, array([2, 4]))
                PopulationView(p, slice(2, 5, 2))

            will all create the same view.
        :type selector: None or slice or int or list(bool) or list(int) or
            ~numpy.ndarray(bool) or ~numpy.ndarray(int)
        :param index_or_slice:
        :return:
        """
        sized = AbstractSized(self._size)
        ids = sized.selector_to_ids(index_or_slice, warn=True)
        indexes = [self._indexes[index] for index in ids]
        return DataPopulation(self.__database_file, self.__label, indexes)

    @overrides(Population.mean_spike_count)
    def mean_spike_count(self, gather=True):
        Population._check_params(gather)
        counts = self.get_spike_counts()
        return sum(counts.values()) / len(counts)
