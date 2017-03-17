from pacman.executor.injection_decorator import inject_items
from spynnaker.pyNN.models.abstract_models.abstract_contains_units import \
    AbstractContainsUnits
from spynnaker.pyNN.models.neural_properties.neural_parameter \
    import NeuronParameter
from spynnaker.pyNN.models.neuron.neuron_models.abstract_neuron_model \
    import AbstractNeuronModel
from spynnaker.pyNN.utilities import utility_calls

from data_specification.enums.data_type import DataType


class NeuronModelIzh(AbstractNeuronModel, AbstractContainsUnits):

    def __init__(self, n_neurons, a, b, c, d, v_init, u_init, i_offset):
        AbstractNeuronModel.__init__(self)
        AbstractContainsUnits.__init__(
            self, {'a': "ms", 'b': "ms", 'c': "mV", 'd': "mV/ms",
                   'v_init': "mV", 'u_init': "mV/ms", 'i_offset': "nA"})
        self._n_neurons = n_neurons
        self._a = utility_calls.convert_param_to_numpy(a, n_neurons)
        self._b = utility_calls.convert_param_to_numpy(b, n_neurons)
        self._c = utility_calls.convert_param_to_numpy(c, n_neurons)
        self._d = utility_calls.convert_param_to_numpy(d, n_neurons)
        self._v_init = utility_calls.convert_param_to_numpy(v_init, n_neurons)
        self._u_init = utility_calls.convert_param_to_numpy(u_init, n_neurons)
        self._i_offset = utility_calls.convert_param_to_numpy(
            i_offset, n_neurons)

    @property
    def a(self):
        return self._a

    @a.setter
    def a(self, a):
        self._a = utility_calls.convert_param_to_numpy(a, self._n_neurons)

    @property
    def b(self):
        return self._b

    @b.setter
    def b(self, b):
        self._b = utility_calls.convert_param_to_numpy(b, self._n_neurons)

    @property
    def c(self):
        return self._c

    @c.setter
    def c(self, c):
        self._c = utility_calls.convert_param_to_numpy(c, self._n_neurons)

    @property
    def d(self):
        return self._d

    @d.setter
    def d(self, d):
        self._d = utility_calls.convert_param_to_numpy(d, self._n_neurons)

    @property
    def v_init(self):
        return self._v_init

    @v_init.setter
    def v_init(self, v_init):
        self._v_init = utility_calls.convert_param_to_numpy(
            v_init, self._n_neurons)

    @property
    def u_init(self):
        return self._u_init

    @u_init.setter
    def u_init(self, u_init):
        self._u_init = utility_calls.convert_param_to_numpy(
            u_init, self._n_neurons)

    @property
    def i_offset(self):
        return self._i_offset

    @i_offset.setter
    def i_offset(self, new_value):
        self._i_offset = new_value

    def initialize_v(self, v_init):
        self._v_init = utility_calls.convert_param_to_numpy(
            v_init, self._n_neurons)

    def initialize_u(self, u_init):
        self._u_init = utility_calls.convert_param_to_numpy(
            u_init, self._n_neurons)

    def get_n_neural_parameters(self):
        return 8

    @inject_items({"machine_time_step": "MachineTimeStep"})
    def get_neural_parameters(self, machine_time_step):
        return [

            # REAL A
            NeuronParameter(self._a, DataType.S1615),

            # REAL B
            NeuronParameter(self._b, DataType.S1615),

            # REAL C
            NeuronParameter(self._c, DataType.S1615),

            # REAL D
            NeuronParameter(self._d, DataType.S1615),

            # REAL V
            NeuronParameter(self._v_init, DataType.S1615),

            # REAL U
            NeuronParameter(self._u_init, DataType.S1615),

            # offset current [nA]
            # REAL I_offset;
            NeuronParameter(self._i_offset, DataType.S1615),

            # current timestep - simple correction for threshold
            # REAL this_h;
            NeuronParameter(machine_time_step / 1000.0, DataType.S1615)
        ]

    def get_n_global_parameters(self):
        return 1

    @inject_items({"machine_time_step": "MachineTimeStep"})
    def get_global_parameters(self, machine_time_step):
        return [
            NeuronParameter(machine_time_step / 1000.0, DataType.S1615)
        ]

    def get_n_cpu_cycles_per_neuron(self):

        # A bit of a guess
        return 150
