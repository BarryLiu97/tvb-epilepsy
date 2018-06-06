import numpy as np
# from copy import deepcopy
from tvb_epilepsy.base.utils.log_error_utils import warning
from tvb_epilepsy.base.utils.data_structures_utils import ensure_list  # isequal_string, sort_dict
# from tvb_epilepsy.base.constants.model_inversion_constants import *
# from tvb_epilepsy.base.computations.probability_distributions import ProbabilityDistributionTypes


INS_PARAMS_NAMES_DICT={"K": "k", "MC": "FC", "tau1": "time_scale", "tau0": "tau",
                       "scale": "amplitude", "target_data": "seeg_log_power", "fit_target_data": "mu_seeg_log_power",
                       "x1init": "x_init", "zinit": "z_init", "x1": "x", "dX1t": "x_eta_star", "dZt": "z_eta_star"}


def set_time(probabilistic_model, time=None):
    if time is None:
        time = np.arange(0, probabilistic_model.dt, probabilistic_model.time_length)
    return time


def convert_params_names_from_ins(dicts_list, parameter_names=INS_PARAMS_NAMES_DICT):
    output = []
    for lst in ensure_list(dicts_list):
        for dct in ensure_list(lst):
            for p, p_ins in parameter_names.iteritems():
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
            for p, p_ins in parameter_names.iteritems():
                try:
                    dct[p_ins] = dct[p]
                except:
                    warning("Parameter " + p + " not found in \n" + str(dicts_list))
        output.append(lst)

    return tuple(output)


def build_stan_model_dict_to_interface_ins(probabilistic_model, signals, connectivity_matrix, gain_matrix, time=None,
                                           parameter_names=INS_PARAMS_NAMES_DICT):
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
        k_mu = np.mean(probabilistic_model.get_truth("K"))
        k_std = 1.0
    vep_data = {"nn": probabilistic_model.number_of_active_regions,
                "nt": probabilistic_model.time_length,
                "ns": probabilistic_model.number_of_target_data,
                "dt": probabilistic_model.dt,
                "I1": probabilistic_model.model_config.Iext1,
                "x0_star_mu": probabilistic_model.parameters["x0"].star_mean[active_regions],
                "x0_star_std": probabilistic_model.parameters["x0"].star_std[active_regions],
                "x0_lo": probabilistic_model.parameters["x0"].low,
                "x0_hi": probabilistic_model.parameters["x0"].high,
                "x_init_mu": probabilistic_model.parameters["x_init"].mean[active_regions],
                "x_init_std": np.mean(probabilistic_model.parameters["x_init"].std),
                "z_init_mu": probabilistic_model.parameters["z_init"].mean[active_regions],
                "z_init_std": np.mean(probabilistic_model.parameters["z_init"].std),
                "x_eq_def": probabilistic_model.model_config.x1eq[nonactive_regions].mean(),
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
                # 9.0 * model_data["signals"] - 4.0,  # scale from (0, 1) to (-4, 5)
                "gain": gain_matrix,
                "time": set_time(probabilistic_model, time),
                "active_regions": np.array(probabilistic_model.active_regions),
                }
    return vep_data
