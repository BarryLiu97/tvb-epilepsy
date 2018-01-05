
import numpy as np

from tvb_epilepsy.base.constants.module_constants import MAX_SINGLE_VALUE
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger
from tvb_epilepsy.base.utils.data_structures_utils import construct_import_path
from tvb_epilepsy.base.model.parameter import Parameter
from tvb_epilepsy.service.sampling.sampling_service import SamplingService


logger = initialize_logger(__name__)


class DeterministicSamplingService(SamplingService):

    def __init__(self, n_samples=10, grid_mode=True):
        super(DeterministicSamplingService, self).__init__(n_samples)
        self.sampling_module = "numpy.linspace"
        self.sampler = np.linspace
        self.grid_mode = grid_mode
        self.shape = (1, self.n_samples)
        self.context_str = "from " + construct_import_path(__file__) + " import " + self.__class__.__name__
        self.create_str = self.__class__.__name__ + "()"

    def sample(self, parameter=(), **kwargs):
        if isinstance(parameter, Parameter):
            parameter_shape = parameter.shape
            low = parameter.low
            high = parameter.high
        else:
            parameter_shape = kwargs.pop("shape", (1,))
            low = kwargs.pop("low", -MAX_SINGLE_VALUE)
            high = kwargs.pop("high", MAX_SINGLE_VALUE)
        low, high = self.check_for_infinite_bounds(low, high)
        low, high, n_outputs, parameter_shape = self.check_size(low, high, parameter_shape)
        self.adjust_shape(parameter_shape)
        samples = []
        for (lo, hi) in zip(low.flatten(), high.flatten()):
            samples.append(self.sampler(lo, hi, self.n_samples))
        if self.grid_mode:
            samples_grids = np.meshgrid(*(samples), sparse=False, indexing="ij")
            samples = []
            for sb in samples_grids:
                samples.append(sb.flatten())
            samples = np.array(samples)
            self.shape = samples.shape
            self.n_samples = self.shape[1]
        else:
            samples = np.array(samples)
        transpose_shape = tuple([self.n_samples] + list(self.shape)[0:-1])
        samples = np.reshape(samples, transpose_shape).T
        self.shape = samples.shape
        return samples



