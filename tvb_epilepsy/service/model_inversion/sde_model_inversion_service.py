import time
import numpy as np
from tvb_epilepsy.base.constants.model_constants import model_noise_intensity_dict
from tvb_epilepsy.base.constants.model_inversion_constants import SIG_DEF
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger
from tvb_epilepsy.base.model.statistical_models.sde_statistical_model import SDEStatisticalModel
from tvb_epilepsy.service.stochastic_parameter_factory import set_parameter_defaults
from tvb_epilepsy.service.epileptor_model_factory import AVAILABLE_DYNAMICAL_MODELS_NAMES, EPILEPTOR_MODEL_NVARS
from tvb_epilepsy.service.model_inversion.ode_model_inversion_service import ODEModelInversionService

LOG = initialize_logger(__name__)


class SDEModelInversionService(ODEModelInversionService):

    def __init__(self, model_configuration, hypothesis=None, head=None, dynamical_model=None, model_name=None,
                 logger=LOG, **kwargs):
        super(SDEModelInversionService, self).__init__(model_configuration, hypothesis, head, dynamical_model,
                                                       model_name, logger, **kwargs)
        self.set_default_parameters(**kwargs)

    def get_default_sig(self, **kwargs):
        if kwargs.get("sig", None):
            return kwargs.pop("sig")
        elif np.in1d(self.dynamical_model, AVAILABLE_DYNAMICAL_MODELS_NAMES):
                if EPILEPTOR_MODEL_NVARS[self.dynamical_model] == 2:
                    return model_noise_intensity_dict[self.dynamical_model][1]
                elif EPILEPTOR_MODEL_NVARS[self.dynamical_model] > 2:
                    return model_noise_intensity_dict[self.dynamical_model][2]
        else:
            return SIG_DEF

    def set_default_parameters(self, **kwargs):
        sig = self.get_default_sig(**kwargs)
        # Generative model:
        # Integration:
        # self.default_parameters.update(set_parameter_defaults("x1_dWt", "normal", (),  # name, pdf, shape
        #                                                       -10.0*sig, 10.0*sig,     # min, max
        #                                                       pdf_params={"mu": 0.0, "sigma": sig}))
        self.default_parameters.update(set_parameter_defaults("z_dWt", "normal", (),  # name, pdf, shape
                                                              pdf_params={"mu": 0.0, "sigma": sig}))
        sig_std = sig / kwargs.get("sig_scale_ratio", 3)
        self.default_parameters.update(set_parameter_defaults("sig", "gamma", (),  # name, pdf, shape
                                                              0.1*sig, 10.0*sig,  # min, max
                                                              pdf_params={"mean": sig/sig_std, "skew": 0.0},
                                                              **kwargs))

    def generate_statistical_model(self, model_name="vep_sde", **kwargs):
        tic = time.time()
        self.logger.info("Generating model...")
        active_regions = kwargs.pop("active_regions", [])
        self.default_parameters.update(kwargs)
        model = SDEStatisticalModel(model_name, self.n_regions, active_regions, self.n_signals, self.n_times, self.dt,
                                    self.get_default_sig_eq(**kwargs), self.get_default_sig_init(**kwargs),
                                    **self.default_parameters)
        self.model_generation_time = time.time() - tic
        self.logger.info(str(self.model_generation_time) + ' sec required for model generation')
        return model

    def generate_model_data(self, statistical_model, signals, gain_matrix=None):
        return super(SDEModelInversionService, self).generate_model_data(statistical_model, signals, gain_matrix)
