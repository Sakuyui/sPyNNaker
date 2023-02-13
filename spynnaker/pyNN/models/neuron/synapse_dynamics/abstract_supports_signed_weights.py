# Copyright (c) 2021-2023 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


class AbstractSupportsSignedWeights(object, metaclass=AbstractBase):
    """ A synapse dynamics object that supports signed weights
    """

    @abstractmethod
    def get_positive_synapse_index(self, incoming_projection):
        """ Get the synapse type that positive weights will arrive at

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: int
        """

    @abstractmethod
    def get_negative_synapse_index(self, incoming_projection):
        """ Get the synapse type that negative weights will arrive at

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: int
        """

    @abstractmethod
    def get_maximum_positive_weight(self, incoming_projection):
        """ Get the maximum likely positive weight.
            Note this must be a value >= 0.

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: float
        """

    @abstractmethod
    def get_minimum_negative_weight(self, incoming_projection):
        """ Get the minimum likely negative weight.
            Note this must be a value <= 0.

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: int
        """

    @abstractmethod
    def get_mean_positive_weight(self, incoming_projection):
        """ Get the mean of the positive weights.
            Note this must be a value >= 0.

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: float
        """

    @abstractmethod
    def get_mean_negative_weight(self, incoming_projection):
        """ Get the mean of the negative weights.
            Note this must be a value <= 0.

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: float
        """

    @abstractmethod
    def get_variance_positive_weight(self, incoming_projection):
        """ Get the variance of the positive weights.
            Note this must be a value >= 0.

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: float
        """

    @abstractmethod
    def get_variance_negative_weight(self, incoming_projection):
        """ Get the variance of the negative weights.
            Note this must be a value <= 0.

        :param ~spynnaker.pyNN.models.projection.Projection\
            incoming_projection: The projection targeted
        :rtype: float
        """
