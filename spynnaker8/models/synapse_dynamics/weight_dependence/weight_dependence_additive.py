# Copyright (c) 2016-2023 The University of Manchester
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
from spynnaker.pyNN.models.neuron.plasticity.stdp.weight_dependence import (
    WeightDependenceAdditive as
    _BaseClass)
from spynnaker.pyNN.utilities.utility_calls import moved_in_v6


class WeightDependenceAdditive(_BaseClass):
    """
    .. deprecated:: 6.0
        Use
        :py:class:`spynnaker.pyNN.models.neuron.plasticity.stdp.weight_dependence.WeightDependenceAdditive`
        instead.
    """
    __slots__ = []

    # noinspection PyPep8Naming
    def __init__(self, w_min=0.0, w_max=1.0):
        r"""
        :param float w_min: :math:`w_\mathrm{min}`
        :param float w_max: :math:`w_\mathrm{max}`
        """
        moved_in_v6("spynnaker8.models.synapse_dynamics.weight_dependence"
                    ".WeightDependenceAdditive",
                    "spynnaker.pyNN.models.neuron.plasticity.stdp."
                    "weight_dependence.WeightDependenceAdditive")
        super(WeightDependenceAdditive, self).__init__(
            w_min=w_min, w_max=w_max)
