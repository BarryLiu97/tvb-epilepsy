import numpy as np

from tvb_epilepsy.base.constants.model_constants import X1_EQ_CR_DEF, X1_DEF
from tvb_epilepsy.base.utils.log_error_utils import raise_value_error  # warning,
from tvb_epilepsy.base.utils.data_structures_utils import formal_repr, sort_dict, ensure_list, construct_import_path
from tvb_epilepsy.base.model.statistical_models.statistical_model import StatisticalModel
from tvb_epilepsy.service.stochastic_parameter_factory import set_parameter


OBSERVATION_MODEL_EXPRESSIONS=["x1z_offset", "x1_offset", "lfp"]
OBSERVATION_MODELS=[ "seeg_logpower", "seeg_power", "lfp_power"]
# EULER_METHODS = ["backward", "midpoint", "forward"]

SIG_EQ_DEF = (X1_EQ_CR_DEF-X1_DEF)/10
SIG_INIT_DEF = SIG_EQ_DEF

class ODEStatisticalModel(StatisticalModel):

    def __init__(self, name='vep_ode', n_regions=0, active_regions=[], n_signals=0, n_times=0, dt=1.0,
                 sig_eq=SIG_EQ_DEF, sig_init=SIG_INIT_DEF, observation_model="seeg_logpower",
                 observation_expression="x1z_offset", # euler_method="forward",
                 **defaults):
        super(ODEStatisticalModel, self).__init__(name, n_regions, sig_eq, **defaults)
        self.sig_init = sig_init
        self.context_str = "from " + construct_import_path(__file__) + " import ODEStatisticalModel"
        self.create_str = "ODEStatisticalModel('" + self.name + "')"
        if np.all(np.in1d(active_regions, range(self.n_regions))):
            self.active_regions = np.unique(active_regions).tolist()
            self.n_active_regions = len(self.active_regions)
            self.n_nonactive_regions = self.n_regions - self.n_active_regions
        else:
            raise_value_error("Active regions indices:\n" + str(active_regions) +
                              "\nbeyond number of regions (" + str(self.n_regions) + ")!")
        self.n_signals = n_signals
        self.n_times = n_times
        self.dt = dt
        # if np.in1d(euler_method.lower(), EULER_METHODS):
        #     if euler_method.lower() == "midpoint":
        #         warning("Midpoint Euler method is not implemented yet! Switching to default forward one!")
        #     self.euler_method = euler_method.lower()
        # else:
        #     raise_value_error("Statistical model's euler_method " + str(euler_method) + " is not one of the valid ones: "
        #                       + str(["backward", "forward"]) + "!")
        if np.in1d(observation_expression.lower(), OBSERVATION_MODEL_EXPRESSIONS):
            self.observation_expression = observation_expression.lower()
        else:
            raise_value_error("Statistical model's observation expression " + str(observation_expression) +
                              " is not one of the valid ones: "
                              + str(OBSERVATION_MODEL_EXPRESSIONS) + "!")
        if np.in1d(observation_model.lower(), OBSERVATION_MODELS):
            self.observation_model = observation_model.lower()
        else:
            raise_value_error("Statistical model's observation expression " + str(observation_model) +
                              " is not one of the valid ones: "
                              + str(OBSERVATION_MODELS) + "!")
        self.__add_parameters(**defaults)

    def update_active_regions(self, active_regions):
        if np.all(np.in1d(active_regions, range(self.n_regions))):
            self.active_regions = np.unique(ensure_list(active_regions) + self.active_regions).tolist()
            self.n_active_regions = len(self.active_regions)
            self.n_nonactive_regions = self.n_regions - self.n_active_regions
        else:
            raise_value_error("Active regions indices:\n" + str(active_regions) +
                              "\nbeyond number of regions (" + str(self.n_regions) + ")!")

    def __repr__(self):
        form_repr = super(ODEStatisticalModel, self).__repr__()
        d = {"6. active regions": self.active_regions,
             "7. initial condition std": self.sig_init,
             "8. number of active regions": self.n_active_regions,
             "9. number of nonactive regions": self.n_nonactive_regions,
             "10. number of observation signals": self.n_signals,
             "11. number of time points": self.n_times,
             "12. time step": self.dt,
             "13. observation_expression": self.observation_expression,
             "14. observation_model": self.observation_model}
              # "13. euler_method": self.euler_method,
        return form_repr + "\n" + formal_repr(self, sort_dict(d))

    def __add_parameters(self, **defaults):
        for p in ["x1init", "zinit", "scale_signal", "offset_signal"]: # "sig_init",
            self.parameters.update({p: set_parameter(p, **defaults)})

    def plot(self, **kwargs):
        for p in self.parameters:
            p.plot(**kwargs)
