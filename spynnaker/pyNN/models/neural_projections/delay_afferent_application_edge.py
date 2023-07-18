# Copyright (c) 2016 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from pacman.model.graphs.application import ApplicationEdge
if TYPE_CHECKING:
    from spynnaker.pyNN.models.neuron import AbstractPopulationVertex
    from spynnaker.pyNN.models.utility_models.delays import (
        DelayExtensionVertex)


class DelayAfferentApplicationEdge(ApplicationEdge):
    __slots__ = ()

    def __init__(self, pre_vertex: AbstractPopulationVertex,
                 delay_vertex: DelayExtensionVertex,
                 label: Optional[str] = None):
        """
        :param AbstractPopulationVertex pre_vertex:
        :param DelayExtensionVertex delay_vertex:
        :param str label:
        """
        super().__init__(pre_vertex, delay_vertex, label=label)
