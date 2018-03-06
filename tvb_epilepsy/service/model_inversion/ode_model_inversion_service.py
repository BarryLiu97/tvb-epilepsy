import time
import numpy as np
from scipy.stats import zscore
from tvb_epilepsy.base.constants.model_inversion_constants import X1EQ_MIN, X1EQ_MAX, X1INIT_MIN, X1INIT_MAX, \
    DT_DEF, ZINIT_MIN, ZINIT_MAX, MC_SCALE, SIG_INIT_DEF, WIN_LEN_RATIO, LOW_FREQ, HIGH_FREQ, BIPOLAR, LOG_FLAG
from tvb_epilepsy.base.utils.data_structures_utils import isequal_string, ensure_list, sort_dict, assert_arrays, \
    extract_dict_stringkeys
from tvb_epilepsy.base.computations.math_utils import select_greater_values_array_inds
from tvb_epilepsy.base.model.vep.sensors import Sensors
from tvb_epilepsy.base.model.statistical_models.ode_statistical_model import ODEStatisticalModel
from tvb_epilepsy.service.head_service import HeadService
from tvb_epilepsy.service.signal_processor import decimate_signals, cut_signals_tails
from tvb_epilepsy.service.stochastic_parameter_builder import set_parameter_defaults
from tvb_epilepsy.service.model_inversion.model_inversion_service import ModelInversionService
from tvb_epilepsy.base.epileptor_models import *
from tvb_epilepsy.top.scripts.fitting_data_scripts import prepare_seeg_observable, prepare_signal_observable


class ODEModelInversionService(ModelInversionService):

    def __init__(self, model_configuration, hypothesis=None, head=None, dynamical_model=None, **kwargs):
        super(ODEModelInversionService, self).__init__(model_configuration, hypothesis, head, dynamical_model, **kwargs)
        self.time = None
        self.dt = kwargs.get("dt", DT_DEF)
        self.n_times = 0
        self.n_signals = self.number_of_regions
        self.data_type = "lfp"
        self.signals_inds = range(self.n_signals)
        self._set_default_parameters(**kwargs)

    # def set_time(self, time=None):
    #     if time is not None:
    #         time = np.array(time)
    #         try:
    #             if time.size == 1:
    #                 self.dt = time
    #                 return np.arange(self.dt * (self.n_times - 1))
    #             elif time.size == self.n_times:
    #                 self.dt = np.mean(np.diff(time))
    #                 return time
    #             else:
    #                 raise_value_error("Input time is neither a scalar nor a vector of length equal " +
    #                                   "to target_data.shape[0]!" + "\ntime = " + str(time))
    #         except:
    #             raise_value_error(
    #                 "Input time is neither a scalar nor a vector of length equal to target_data.shape[0]!" +
    #                 "\ntime = " + str(time))
    #     else:
    #         raise_value_error("Input time is neither a scalar nor a vector of length equal to target_data.shape[0]!" +
    #                           "\ntime = " + str(time))

    def select_signals_seeg(self, signals, rois, auto_selection, **kwargs):
        sensors = Sensors(self.sensors_labels, self.sensors_locations, gain_matrix=self.gain_matrix)
        inds = range(signals.shape[1])

        head_service = HeadService()
        if auto_selection.find("rois") >= 0:
            if sensors.gain_matrix is not None:
                current_selection = head_service.select_sensors_rois(sensors, kwargs.get("rois", rois),
                                                                     self.signals_inds,
                                                                     kwargs.get("gain_matrix_th", None))
                inds = np.where([s in current_selection for s in self.signals_inds])[0]
                self.signals_inds = np.array(self.signals_inds)[inds].tolist()
                signals = signals[:, inds]
        if auto_selection.find("correlation-power") >= 0:
            power = kwargs.get("power", np.sum((signals - np.mean(signals, axis=0)) ** 2, axis=0) / signals.shape[0])
            correlation = kwargs.get("correlation", np.corrcoef(signals.T))
            current_selection = head_service.select_sensors_corr(sensors, correlation, self.signals_inds, power=power,
                                                                 n_electrodes=kwargs.get("n_electrodes"),
                                                                 sensors_per_electrode=kwargs.get(
                                                                     "sensors_per_electrode", 1),
                                                                 group_electrodes=kwargs.get("group_electrodes", True))
            inds = np.where([s in current_selection for s in self.signals_inds])[0]
            self.signals_inds = np.array(self.signals_inds)[inds].tolist()
        elif auto_selection.find("power"):
            power = kwargs.get("power", np.sum(signals ** 2, axis=0) / signals.shape[0])
            inds = select_greater_values_array_inds(power, kwargs.get("power_th", None))
            self.signals_inds = (np.array(self.signals_inds)[inds]).tolist()
        self.n_signals = len(self.signals_inds)
        return signals[:, inds]

    def select_signals_lfp(self, signals, rois, auto_selection, **kwargs):
        if auto_selection.find("rois") >= 0:
            if kwargs.get("rois", rois):
                inds = np.where([s in rois for s in self.signals_inds])[0]
                signals = signals[:, inds]
                self.signals_inds = np.array(self.signals_inds)[inds].tolist()
        if auto_selection.find("power") >= 0:
            power = kwargs.get("power", np.sum((signals - np.mean(signals, axis=0)) ** 2, axis=0) / signals.shape[0])
            inds = select_greater_values_array_inds(power, kwargs.get("power_th", None))
            signals = signals[:, inds]
            self.signals_inds = (np.array(self.signals_inds)[inds]).tolist()
        self.n_signals = len(self.signals_inds)
        return signals

    def set_empirical_target_data(self, target_data, **kwargs):
        self.data_type = "seeg"
        self.signals_inds = range(len(self.sensors_labels))
        manual_selection = kwargs.get("manual_selection", [])
        if len(manual_selection) > 0:
            self.signals_inds = manual_selection
        if isinstance(target_data, dict):
            signals = np.array(target_data.get("signals", target_data.get("target_data", None)))
        if len(self.signals_inds) < signals.shape[1]:
            signals = signals[:, self.signals_inds]
        self.observation_shape = signals.shape
        (self.n_times, self.n_signals) = self.observation_shape
        return signals

    def set_simulated_target_data(self, target_data, statistical_model, dynamical_model, **kwargs):
        self.signals_inds = range(self.number_of_regions)
        self.data_type = "lfp"
        signals = np.array([])
        self.time = target_data["time"].flatten()
        if statistical_model.observation_model.find("seeg") >= 0:
            self.data_type = "seeg"
            self.signals_inds = range(self.gain_matrix.shape[0])
            if not(isequal_string(statistical_model.observation_model, "seeg_logpower")):
                signals = extract_dict_stringkeys(sort_dict(target_data), kwargs.get("seeg_dataset", "SEEG0"),
                                                  modefun="find", two_way_search=True, break_after=1)
                if len(signals) > 0:
                    signals = signals.values()[0]
            if signals.size == 0:
                signals = np.array(target_data.get("lfp", target_data["x1"]))
                if isequal_string(statistical_model.observation_model, "seeg_logpower"):
                    signals = np.log(np.dot(self.gain_matrix, np.exp(signals.T))).T
                else:
                    signals = (np.dot(self.gain_matrix, signals.T)).T
            signals, self.time, self.signals_inds, self.sensors_labels = \
                prepare_seeg_observable(signals, self.time, dynamical_model,
                                        kwargs.get("times_on_off", [self.time[0], self.time[-1]]),
                                        self.sensors_labels, kwargs.get("manual_selection", []),
                                        win_len_ratio=kwargs.get("win_len_ratio", WIN_LEN_RATIO),
                                        low_freq=kwargs.get("low_freq", LOW_FREQ),
                                        high_freq=kwargs.get("high_freq", HIGH_FREQ),
                                        bipolar=kwargs.get("bipolar", BIPOLAR),
                                        log_flag=kwargs.get("log_flag", LOG_FLAG),
                                        plotter=kwargs.get("plotter", False))
        else:
            # if statistical_model.observation_expression == "x1z_offset":
            #     signals = ((target_data["x1"].T - np.expand_dims(self.x1EQ, 1)).T +
            #                (target_data["z"].T - np.expand_dims(self.zEQ, 1)).T) / 2.75
            #     # TODO: a better normalization
            # elif statistical_model.observation_expression == "x1_offset":
            #     # TODO: a better normalization
            #     signals = (target_data["x1"].T - np.expand_dims(self.x1EQ, 1)).T / 2.0
            # else: # statistical_models.observation_expression == "lfp"
            signals = np.array(target_data.get("lfp", target_data["x1"]))
            signals, self.time, self.signals_inds = \
                prepare_signal_observable(signals, self.time, dynamical_model,
                                          kwargs.get("times_on_off", [self.time[0], self.time[-1]]),
                                          self.region_labels, rois=kwargs.get("manual_selection", []),
                                          win_len_ratio=kwargs.get("win_len_ratio", WIN_LEN_RATIO),
                                          low_freq=kwargs.get("low_freq", LOW_FREQ),
                                          high_freq=kwargs.get("high_freq", HIGH_FREQ),
                                          log_flag=kwargs.get("log_flag", LOG_FLAG),
                                          plotter=kwargs.get("plotter", False))[:3]
            target_data["signals"] = np.array(signals)
        self.observation_shape = signals.shape
        (self.n_times, self.n_signals) = self.observation_shape
        return signals, target_data

    def normalize_signals(self, signals, normalization=None):
        if isinstance(normalization, basestring):
            if isequal_string(normalization, "zscore"):
                signals = zscore(signals, axis=None) / 3.0
            elif isequal_string(normalization, "minmax"):
                signals -= signals.min()
                signals /= signals.max()
            elif isequal_string(normalization, "baseline-amplitude"):
                signals -= np.percentile(signals, 5, 0)
                signals /= np.percentile(signals, 95)
            else:
                self.logger.warn("Ignoring target signals' normalization " + normalization +
                                 ",\nwhich is not one of the currently available 'zscore' and 'minmax'!")
        return signals

    def set_target_data_and_time(self, target_data_type, target_data, statistical_model, dynamical_model, **kwargs):
        if isequal_string(target_data_type, "simulated"):
            signals, target_data = self.set_simulated_target_data(target_data, statistical_model, dynamical_model,
                                                                  **kwargs)
            self.target_data_type = "simulated"
        else:  # isequal_string(target_data_type, "empirical"):
            signals = self.set_empirical_target_data(target_data, **kwargs)
            self.target_data_type = "empirical"
            self.time = target_data.get("time", np.arange(self.dt * (self.n_times - 1)))
        if kwargs.get("auto_selection", True) is not False:
            if self.data_type == "lfp":
                signals = self.select_signals_lfp(signals, statistical_model.active_regions,
                                                  kwargs.pop("auto_selection", "rois"), **kwargs)
            else:
                signals = self.select_signals_seeg(signals, statistical_model.active_regions,
                                                   kwargs.pop("auto_selection", "rois-correlation-power"), **kwargs)
        if kwargs.get("decimate", 1) > 1:
            signals, self.time, self.dt, self.n_times = decimate_signals(signals, self.time, kwargs.get("decimate"))
            self.observation_shape = (self.n_times, self.n_signals)
        if np.sum(kwargs.get("cut_signals_tails", (0, 0))) > 0:
            signals, self.time, self.n_times = cut_signals_tails(signals, self.time, kwargs.get("cut_signals_tails"))
            self.observation_shape = (self.n_times, self.n_signals)
        # TODO: decide about signals' normalization for the different (sensors', sources' cases)
        signals = self.normalize_signals(signals, kwargs.get("normalization", None))
        statistical_model.n_signals = self.n_signals
        statistical_model.n_times = self.n_times
        statistical_model.dt = self.dt
        return signals, self.time, statistical_model, target_data

    def update_active_regions_e_values(self, statistical_model, active_regions_th=0.1, reset=False):
        if reset:
            statistical_model.update_active_regions([])
        statistical_model.update_active_regions(statistical_model.active_regions +
                                                select_greater_values_array_inds(self.e_values,
                                                                                 active_regions_th).tolist())
        return statistical_model

    def update_active_regions_x0_values(self, statistical_model, active_regions_th=0.1, reset=False):
        if reset:
            statistical_model.update_active_regions([])
        statistical_model.update_active_regions(statistical_model.active_regions +
                                                select_greater_values_array_inds(self.x0_values,
                                                                                 active_regions_th).tolist())
        return statistical_model

    def update_active_regions_lsa(self, statistical_model, active_regions_th=None, reset=False):
        if reset:
            statistical_model.update_active_regions([])
        if len(self.lsa_propagation_strengths) > 0:
            ps_strengths = self.lsa_propagation_strengths / np.max(self.lsa_propagation_strengths)
            statistical_model.update_active_regions(statistical_model.active_regions +
                                                    select_greater_values_array_inds(ps_strengths,
                                                                                     active_regions_th).tolist())
        else:
            self.logger.warning("No LSA results found (empty propagations_strengths vector)!" +
                                "\nSkipping of setting active_regions according to LSA!")
        return statistical_model

    def update_active_regions_seeg(self, statistical_model, active_regions_th=None, seeg_inds=[], reset=False):
        if reset:
            statistical_model.update_active_regions([])
        if self.gain_matrix is not None:
            active_regions = statistical_model.active_regions
            if len(seeg_inds) == 0:
                seeg_inds = self.signals_inds
            if len(seeg_inds) != 0:
                gain_matrix = self.gain_matrix[seeg_inds]
            else:
                gain_matrix = self.gain_matrix
            for proj in gain_matrix:
                active_regions += select_greater_values_array_inds(proj, active_regions_th).tolist()
            statistical_model.update_active_regions(active_regions)
        else:
            self.logger.warning(
                "Projection is not found!" + "\nSkipping of setting active_regios according to SEEG power!")
        return statistical_model

    def update_active_regions(self, statistical_model, methods=["e_values", "LSA"], reset=False, **kwargs):
        if reset:
            statistical_model.update_active_regions([])
        for m, th in zip(*assert_arrays([ensure_list(methods),
                                         ensure_list(kwargs.get("active_regions_th", None))])):
            if isequal_string(m, "e_values"):
                statistical_model = self.update_active_regions_e_values(statistical_model, th)
            elif isequal_string(m, "x0_values"):
                statistical_model = self.update_active_regions_x0_values(statistical_model, th)
            elif isequal_string(m, "lsa"):
                statistical_model = self.update_active_regions_lsa(statistical_model, th)
            elif isequal_string(m, "seeg"):
                statistical_model = self.update_active_regions_seeg(statistical_model, th,
                                                                    seeg_inds=kwargs.get("seeg_inds"))
        return statistical_model

    def _set_default_parameters(self, **kwargs):
        sig_init = kwargs.get("sig_init", SIG_INIT_DEF)
        # Generative model:
        # Integration:
        self.default_parameters.update(set_parameter_defaults("x1init", "normal", (self.number_of_regions,),  # name, pdf, shape
                                                              X1INIT_MIN, X1INIT_MAX,  # min, max
                                                              pdf_params={"mu": self.x1EQ,
                                                                          "sigma": sig_init}))
        self.default_parameters.update(set_parameter_defaults("zinit", "normal", (self.number_of_regions,),  # name, pdf, shape
                                                              ZINIT_MIN, ZINIT_MAX,  # min, max
                                                              pdf_params={"mu": self.zEQ, "sigma": sig_init}))
        self.default_parameters.update(set_parameter_defaults("sig_init", "lognormal", (),
                                                              0.0, 3.0 * sig_init,
                                                              sig_init, sig_init / 3.0,
                                                              pdf_params={"mean": 1.0, "skew": 0.0}, **kwargs))
        self.default_parameters.update(set_parameter_defaults("scale_signal", "lognormal", (),
                                                              0.1, 10.0,
                                                              1.0, 1.0,
                                                              pdf_params={"mean": 1.0, "skew": 0.0}, **kwargs))
        self.default_parameters.update(set_parameter_defaults("offset_signal", "normal", (),
                                                              pdf_params={"mu": 0.0, "sigma": 1.0}, **kwargs))

    def generate_statistical_model(self, model_name="vep_ode", **kwargs):
        tic = time.time()
        self.logger.info("Generating model...")
        active_regions = kwargs.pop("active_regions", [])
        self.default_parameters.update(kwargs)
        model = ODEStatisticalModel(model_name, self.number_of_regions, active_regions, self.n_signals, self.n_times, self.dt,
                                    **self.default_parameters)
        self.model_generation_time = time.time() - tic
        self.logger.info(str(self.model_generation_time) + ' sec required for model generation')
        return model
