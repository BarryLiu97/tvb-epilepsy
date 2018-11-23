
import numpy as np

from scipy.stats import zscore

from tvb_fit.base.utils.log_error_utils import warning
from tvb_fit.base.utils.data_structures_utils import ensure_list

from tvb_fit.tvb_epilepsy.base.constants.model_inversion_constants\
    import XModes, OBSERVATION_MODELS, X1EQ_CR, X1EQ_DEF
from tvb_fit.tvb_epilepsy.base.model.epileptor_probabilistic_models import SDEEpiProbabilisticModel


def set_time(probabilistic_model, time=None):
    if time is None:
        time = np.arange(0, probabilistic_model.dt, probabilistic_model.time_length)
    return time


def build_stan_model_data_dict(probabilistic_model, signals, connectivity_matrix,
                               x1prior=None, x1eps=None, time=None):
    """
    Usually takes as input the model_data created with <build_stan_model_dict> and adds fields that are needed to
    interface the ins stan model.
    :param
    """
    active_regions = probabilistic_model.active_regions
    nonactive_regions = probabilistic_model.nonactive_regions
    if time is None:
        time = np.arange(0, probabilistic_model.dt, probabilistic_model.time_length)
    x = probabilistic_model.xmode
    x1_prior_weight = getattr(probabilistic_model, "x1_prior_weight", 0.0)
    vep_data = {"LINEAR": int(getattr(probabilistic_model, "linear_flag", 0)),
                "NORMAL": probabilistic_model.normal_flag,
                "UPSAMPLE": probabilistic_model.upsample,
                "n_active_regions": probabilistic_model.number_of_active_regions,
                "n_times": probabilistic_model.time_length,
                "n_target_data": probabilistic_model.number_of_target_data,
                "n_seizures": getattr(probabilistic_model, "number_of_seizures", 1),
                "dt": probabilistic_model.dt,
                "yc": np.mean(probabilistic_model.model_config.yc),
                "Iext1": np.mean(probabilistic_model.model_config.Iext1),
                "XMODE": int(probabilistic_model.xmode == XModes.X1EQMODE.value),
                "x1eq_cr": getattr(probabilistic_model, "x1eq_cr", X1EQ_CR),
                "x1eq_def": getattr(probabilistic_model, "x1eq_def", X1EQ_DEF),
                "x_mu": probabilistic_model.parameters[x].mean[active_regions],
                "x_std": probabilistic_model.parameters[x].std[active_regions],
                "x_lo": probabilistic_model.parameters[x].low,
                "x_hi": probabilistic_model.parameters[x].high,
                "X1_PRIOR": x1_prior_weight,
                "x1_init_lo": np.min(probabilistic_model.parameters["x1_init"].low),
                "x1_init_hi": np.max(probabilistic_model.parameters["x1_init"].high),
                "x1_init_mu": probabilistic_model.parameters["x1_init"].mean[active_regions],
                "z_init_lo": np.min(probabilistic_model.parameters["z_init"].low),
                "z_init_hi": np.max(probabilistic_model.parameters["z_init"].high),
                "x1_init_std": np.mean(probabilistic_model.parameters["x1_init"].std),
                "z_init_mu": probabilistic_model.parameters["z_init"].mean[active_regions],
                "z_init_std": np.mean(probabilistic_model.parameters["z_init"].std),
                "x1_eq_def": probabilistic_model.model_config.x1eq[nonactive_regions].mean(),
                "SC": connectivity_matrix[active_regions][:, active_regions],
                "Ic": np.sum(connectivity_matrix[active_regions][:, nonactive_regions], axis=1),
                "epsilon_lo": np.min(probabilistic_model.parameters["epsilon"].low),
                "epsilon_hi": np.max(probabilistic_model.parameters["epsilon"].high),
                "epsilon_mu": probabilistic_model.parameters["epsilon"].mean,
                "epsilon_std": probabilistic_model.parameters["epsilon"].std,
                "scale_mu": probabilistic_model.parameters["scale"].mean,
                "scale_std": probabilistic_model.parameters["scale"].std,
                "scale_lo": probabilistic_model.parameters["scale"].low,
                "scale_hi": probabilistic_model.parameters["scale"].high,
                "offset_mu": probabilistic_model.parameters["offset"].mean,
                "offset_std": probabilistic_model.parameters["offset"].std,
                "offset_lo": probabilistic_model.parameters["offset"].low,
                "offset_hi": probabilistic_model.parameters["offset"].high,
                "LOG_TARGET_DATA": int(probabilistic_model.observation_model == OBSERVATION_MODELS.SEEG_LOGPOWER.value),
                "SOURCE_TARGET_DATA": int(
                    probabilistic_model.observation_model == OBSERVATION_MODELS.SOURCE_POWER.value),
                "target_data": signals,
                "gain": probabilistic_model.gain_matrix,
                "time": set_time(probabilistic_model, time),
                "active_regions": np.array(probabilistic_model.active_regions),
                }
    for p in ["x1", "z"]:
        if p in probabilistic_model.parameters.keys():
            vep_data.update({p + "_lo": np.min(probabilistic_model.parameters[p].low),
                             p + "_hi": np.max(probabilistic_model.parameters[p].high)})
    NO_PRIOR_CONST = 0.001
    p_names = ["tau1", "tau0", "K"]
    p_flags = ["TAU1_PRIOR", "TAU0_PRIOR", "K_PRIOR"]
    if isinstance(probabilistic_model, SDEEpiProbabilisticModel):
        p_names += ["sigma"]
        p_flags += ["SDE"]
    else:
        vep_data["SDE"] = int(0)
    for pkey, pflag in zip(p_names, p_flags):
        param = probabilistic_model.parameters.get(pkey, None)
        if param is None:
            mean = np.mean(getattr(probabilistic_model,pkey, NO_PRIOR_CONST))
            vep_data.update({pflag: int(0), pkey+"_mu": mean, pkey + "_std": NO_PRIOR_CONST,
                             pkey + "_lo": mean-3*NO_PRIOR_CONST, pkey + "_hi": mean+3*NO_PRIOR_CONST})
            if pflag == "SDE":
                vep_data["SDE"] = int(1)
        else:
            vep_data.update({pflag: int(1), pkey+"_mu": np.mean(param.mean), pkey + "_std": np.mean(param.std),
                             pkey + "_lo": np.min(param.low), pkey + "_hi": np.max(param.high)})
    for pkey in ["x1_scale", "x1_offset"]:
        param = probabilistic_model.parameters.get(pkey)
        if param is None:
            mean = np.mean(getattr(probabilistic_model, pkey, NO_PRIOR_CONST))
            vep_data.update({pkey + "_mu": mean, pkey + "_std": NO_PRIOR_CONST,
                             pkey + "_lo": mean - NO_PRIOR_CONST, pkey + "_hi": mean + NO_PRIOR_CONST})
        else:
            vep_data.update({pkey+"_mu": param.mean, pkey + "_std": param.std,
                             pkey + "_lo": param.low, pkey + "_hi": param.high})
    if x1_prior_weight > 0:
        vep_data.update({"x1prior": x1prior, "x1eps": x1eps})
    else:
        x1_shape = (probabilistic_model.time_length, probabilistic_model.number_of_active_regions)
        vep_data.update({"x1prior": np.zeros(x1_shape), "x1eps": np.ones(x1_shape)})
        # if isinstance(x1eps, np.ndarray):
        #     x1eps = zscore(x1eps)
        #     x1eps /= np.max(np.abs(x1eps))
        #     vep_data["epsilon_mu"] = vep_data["epsilon_mu"] * (1.01 + x1eps)
        #     vep_data["epsilon_std"] = vep_data["epsilon_mu"]
        #     vep_data["epsilon_lo"] = 0.0
        #     vep_data["epsilon_hi"] = np.max(vep_data["epsilon_mu"] + 6*vep_data["epsilon_std"])
    return vep_data


INS_PARAMS_NAMES_DICT={"K": "k", "MC": "FC", "tau1": "time_scale", "tau0": "tau",
                       "scale": "amplitude", "target_data": "seeg_log_power", "fit_target_data": "mu_seeg_log_power",
                       "x1_init": "x_init", "x1": "x", "dX1t": "x_eta_star", "dZt": "z_eta_star"}


def convert_params_names_from_ins(dicts_list, parameter_names=INS_PARAMS_NAMES_DICT):
    output = []
    for lst in ensure_list(dicts_list):
        for dct in ensure_list(lst):
            for p, p_ins in parameter_names.items():
                try:
                    dct[p] = dct[p_ins]
                except:
                    warning("Parameter " + p_ins + " not found in \n" + str(dicts_list))
        output.append(lst)
    return tuple(output)


def convert_params_names_to_ins(dicts_list, parameter_names=INS_PARAMS_NAMES_DICT):
    output = []
    for lst in ensure_list(dicts_list):
        for dct in ensure_list(lst):
            for p, p_ins in parameter_names.items():
                try:
                    dct[p_ins] = dct[p]
                except:
                    warning("Parameter " + p + " not found in \n" + str(dicts_list))
        output.append(lst)
    return tuple(output)


def build_stan_model_data_dict_to_interface_ins(probabilistic_model, signals, connectivity_matrix, gain_matrix,
                                                time=None, parameter_names=INS_PARAMS_NAMES_DICT):
    """
    Usually takes as input the model_data created with <build_stan_model_dict> and adds fields that are needed to
    interface the ins stan model.
    :param
    """
    active_regions = probabilistic_model.active_regions
    nonactive_regions = probabilistic_model.nonactive_regions
    if time is None:
        time = np.arange(0, probabilistic_model.dt, probabilistic_model.time_length)
    probabilistic_model.parameters = convert_params_names_to_ins(probabilistic_model.parameters, parameter_names)[0]
    if "k" in probabilistic_model.parameters.keys():
        k_mu = np.mean(probabilistic_model.parameters["k"].mean)
        k_std = np.mean(probabilistic_model.parameters["k"].std)
    else:
        k_mu = np.mean(probabilistic_model.model_config.K)
        k_std = 1.0
    vep_data = {"nn": probabilistic_model.number_of_active_regions,
                "nt": probabilistic_model.time_length,
                "ns": probabilistic_model.number_of_target_data,
                "dt": probabilistic_model.dt,
                "I1": np.mean(probabilistic_model.model_config.Iext1),
                "x0_star_mu": probabilistic_model.parameters["x0"].star_mean[active_regions],
                "x0_star_std": probabilistic_model.parameters["x0"].star_std[active_regions],
                "x0_lo": probabilistic_model.parameters["x0"].low,
                "x0_hi": probabilistic_model.parameters["x0"].high,
                "x_init_mu": probabilistic_model.parameters["x_init"].mean[active_regions],
                "x_init_std": np.mean(probabilistic_model.parameters["x_init"].std),
                "z_init_mu": probabilistic_model.parameters["z_init"].mean[active_regions],
                "z_init_std": np.mean(probabilistic_model.parameters["z_init"].std),
                "x1_eq_def": probabilistic_model.model_config.x1eq[nonactive_regions].mean(),
                "tau0": probabilistic_model.tau0,  # 10.0
                "time_scale_mu": probabilistic_model.parameters["time_scale"].mean,
                "time_scale_std": probabilistic_model.parameters["time_scale"].std,
                "k_mu": k_mu,
                "k_std": k_std,
                "SC": connectivity_matrix[active_regions][:, active_regions],
                "SC_var": 5.0,  # 1/36 = 0.02777777,
                "Ic": np.sum(connectivity_matrix[active_regions][:, nonactive_regions], axis=1),
                "sigma_mu": probabilistic_model.parameters["sigma"].mean,
                "sigma_std": probabilistic_model.parameters["sigma"].std,
                "epsilon_mu": probabilistic_model.parameters["epsilon"].mean,
                "epsilon_std": probabilistic_model.parameters["epsilon"].std,
                "sig_hi": 0.025,  # model_data["sig_hi"],
                "amplitude_mu": probabilistic_model.parameters["amplitude"].mean,
                "amplitude_std": probabilistic_model.parameters["amplitude"].std,
                "amplitude_lo": 0.3,
                "offset_mu": probabilistic_model.parameters["offset"].mean,
                "offset_std": probabilistic_model.parameters["offset"].std,
                "seeg_log_power": signals,
                "gain": gain_matrix,
                "time": set_time(probabilistic_model, time),
                "active_regions": np.array(probabilistic_model.active_regions),
                }
    return vep_data