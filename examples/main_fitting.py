# encoding=utf8

import os
import numpy as np
from scipy.io import loadmat, savemat
from tvb_epilepsy.base.constants.configurations import FOLDER_RES, DATA_CUSTOM, FOLDER_FIGURES, FOLDER_VEP_ONLINE, \
                                                                                                    TVB_EPILEPSY_PATH
from tvb_epilepsy.base.constants.module_constants import TVB, CUSTOM
from tvb_epilepsy.base.constants.model_constants import K_DEF
from tvb_epilepsy.base.utils.data_structures_utils import isequal_string, ensure_list
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger
from tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.io.h5_writer import H5Writer
from tvb_epilepsy.io.h5_reader import H5Reader
from tvb_epilepsy.plot.plotter import Plotter
from tvb_epilepsy.service.model_configuration_service import ModelConfigurationService
from tvb_epilepsy.service.model_inversion.sde_model_inversion_service import SDEModelInversionService
from tvb_epilepsy.service.model_inversion.stan.cmdstan_service import CmdStanService
from tvb_epilepsy.service.model_inversion.stan.pystan_service import PyStanService
from tvb_epilepsy.scripts.hypothesis_scripts import from_head_to_hypotheses, from_hypothesis_to_model_config_lsa
from tvb_epilepsy.scripts.simulation_scripts import from_model_configuration_to_simulation
from tvb_epilepsy.scripts.seeg_data_scripts import prepare_seeg_observable

logger = initialize_logger(__name__)

reader = H5Reader()
writer = H5Writer()

plotter = Plotter()

FOLDER_VEP_HOME = os.path.join(FOLDER_VEP_ONLINE, "tests")


def convert_to_vep_stan(model_data, statistical_model, model_inversion, gain_matrix=None):
    from copy import deepcopy
    active_regions = model_data["active_regions"]-1
    nonactive_regions = model_data["nonactive_regions"] - 1
    SC = statistical_model.parameters["MC"].mode
    act_reg_ones = np.ones((model_data["n_active_regions"],))
    x0_hi = -2.0
    x0_star_mu = x0_hi - model_inversion.x0[active_regions].mean() * act_reg_ones
    x0_star_std = np.minimum(0.05, x0_star_mu/3.0)
    vep_data = {"nn": model_data["n_active_regions"],
                "nt": model_data["n_times"],
                "ns": model_data["n_signals"],
                "dt": model_data["dt"],  # model_data["dt"],
                "I1": model_data["Iext1"],
                "x0_star_mu": x0_star_mu,
                # model_inversion.x0[statistical_model.active_regions],
                "x0_star_std": x0_star_std,
                "x0_lo": -3.0,
                "x0_hi": x0_hi,
                "x_init_mu": statistical_model.parameters["x1init"].mean[active_regions].mean()*act_reg_ones,
                "z_init_mu": statistical_model.parameters["zinit"].mean[active_regions].mean()*act_reg_ones,
                "x_eq_def": model_inversion.x1EQ[nonactive_regions].mean(),
                "init_std": np.mean(statistical_model.parameters["x1init"].std),
                "tau0": 30.0,#statistical_model.parameters["tau0"].mean,
                # "K_lo": statistical_model.parameters["K"].low,
                # "K_u": statistical_model.parameters["K"].mode,
                # "K_v": statistical_model.parameters["K"].var,
                "time_scale_mu": statistical_model.parameters["tau1"].mean,
                "time_scale_std": statistical_model.parameters["tau1"].std,
                "k_mu": statistical_model.parameters["K"].mean,
                "k_std": statistical_model.parameters["K"].std,
                "SC": SC[active_regions][:, active_regions],
                "SC_var": 5.0,  # 1/36 = 0.02777777,
                "Ic": np.sum(SC[active_regions][:, nonactive_regions], axis=1),
                "sigma_mu": statistical_model.parameters["sig"].mean*10,
                "sigma_std": statistical_model.parameters["sig"].std*10,
                "epsilon_mu": statistical_model.parameters["eps"].mean,
                "epsilon_std": statistical_model.parameters["eps"].std,
                "sig_hi": 0.025,  # model_data["sig_hi"],
                "amplitude_mu": statistical_model.parameters["scale_signal"].mean,
                "amplitude_std": statistical_model.parameters["scale_signal"].std/6,
                "amplitude_lo": 0.3,
                "offset_mu": statistical_model.parameters["offset_signal"].mean,
                "offset_std": statistical_model.parameters["offset_signal"].std,
                "seeg_log_power": model_data["signals"],
                # 9.0 * model_data["signals"] - 4.0,  # scale from (0, 1) to (-4, 5)
                "time": model_data["time"]
                }
    if gain_matrix is None:
        if statistical_model.observation_model.find("seeg") >= 0:
            gain_matrix = model_inversion.gain_matrix
            mixing = deepcopy(gain_matrix)[:, statistical_model.active_regions]
        else:
            mixing = np.eye(vep_data["nn"])
        if mixing.shape[0] > vep_data["ns"]:
            mixing = mixing[model_inversion.signals_inds]
        vep_data["gain"] = mixing
    return vep_data


def main_fit_sim_hyplsa(ep_name="ep_l_frontal_complex", data_folder=os.path.join(DATA_CUSTOM, 'Head'),
                        sensors_filename="SensorsSEEG_116.h5", stats_model_name="vep_sde",
                        model_code_dir=os.path.join(TVB_EPILEPSY_PATH, "stan"), EMPIRICAL="",
                        times_on_off=[], sensors_lbls=[], sensors_inds=[], fitmethod="optimizing",
                        stan_service="CmdStan", results_dir=FOLDER_RES, figure_dir=FOLDER_FIGURES, **kwargs):
    # ------------------------------Stan model and service--------------------------------------
    # Compile or load model:
    # model_code_path = os.path.join(STATS_MODELS_PATH, stats_model_name + ".stan")
    model_code_path = os.path.join(model_code_dir, stats_model_name + ".stan")
    if isequal_string(stan_service, "CmdStan"):
        stan_service = CmdStanService(model_name=stats_model_name, model=None, model_code=None,
                                      model_dir=FOLDER_VEP_HOME, model_code_path=model_code_path,
                                      fitmethod=fitmethod, random_seed=12345, init="random")
    else:
        stan_service = PyStanService(model_name=stats_model_name, model=None, model_code=None,
                                     model_dir=FOLDER_VEP_HOME, model_code_path=model_code_path,
                                     fitmethod=fitmethod, random_seed=12345, init="random")
    stan_service.set_or_compile_model()

    # -------------------------------Reading model_data and hypotheses--------------------------------------------------
    head, hypos = from_head_to_hypotheses(ep_name, data_mode=CUSTOM, data_folder=data_folder,
                                          plot_head=False, figure_dir=figure_dir, sensors_filename=sensors_filename)

    for hyp in hypos[:1]:

        # --------------------------Model configuration and LSA-----------------------------------
        model_config_file = os.path.join(FOLDER_VEP_HOME, hyp.name + "_ModelConfig.h5")
        hyp_file =os.path.join(FOLDER_VEP_HOME, hyp.name + "_LSA.h5")
        if os.path.isfile(hyp_file) and \
           os.path.isfile(model_config_file):
            model_configuration = reader.read_model_configuration(model_config_file)
            lsa_hypothesis = reader.read_hypothesis(hyp_file)
        else:
            model_configuration, lsa_hypothesis, model_configuration_service, lsa_service = \
               from_hypothesis_to_model_config_lsa(hyp, head, eigen_vectors_number=None, weighted_eigenvector_sum=True,
                                                   plot_flag=False, figure_dir=figure_dir, K=K_DEF)

        dynamical_model = "EpileptorDP2D"

        # -------------------------- Get model_data and observation signals: -------------------------------------------
        model_inversion_file = os.path.join(FOLDER_VEP_HOME, hyp.name + "_ModelInversionService.h5")
        stats_model_file = os.path.join(FOLDER_VEP_HOME, hyp.name + "_StatsModel.h5")
        model_data_file = os.path.join(FOLDER_VEP_HOME, hyp.name + "_ModelData.h5")
        if os.path.isfile(model_inversion_file) and \
           os.path.isfile(stats_model_file) and \
           os.path.isfile(model_data_file):
            model_inversion = reader.read_dictionary(model_inversion_file, "OrderedDictDot")
            statistical_model = reader.read_generic(stats_model_file)
            model_data = reader.read_dictionary(model_data_file)
        else:
            model_inversion = SDEModelInversionService(model_configuration, lsa_hypothesis, head, dynamical_model,
                                                       sig=0.001)

            statistical_model = model_inversion.generate_statistical_model(observation_model="lfp_power") # observation_expression="lfp"
            statistical_model = model_inversion.update_active_regions(statistical_model, methods=["e_values", "LSA"],
                                                                      active_regions_th=0.1, reset=True)
            plotter.plot_statistical_model(statistical_model, "Statistical Model")
            decimate = 1
            cut_signals_tails = (6, 6)
            if os.path.isfile(EMPIRICAL):
                # ---------------------------------------Get empirical data----------------------------------------------
                target_data_type = "empirical"
                ts_file = os.path.join(FOLDER_VEP_HOME, hyp.name + "_ts_empirical.mat")
                try:
                    vois_ts_dict = loadmat(ts_file)
                    time = vois_ts_dict["time"].flatten()
                    sensors_inds = np.array(vois_ts_dict["sensors_inds"]).flatten().tolist()
                    sensors_lbls = np.array(vois_ts_dict["sensors_lbls"]).flatten().tolist()
                    vois_ts_dict.update({"time": time, "sensors_inds": sensors_inds, "sensors_lbls": sensors_lbls})
                    savemat(ts_file, vois_ts_dict)
                except:
                    signals, time, fs = prepare_seeg_observable(EMPIRICAL, times_on_off, sensors_lbls, plot_flag=True,
                                                                log_flag=True)
                    if len(sensors_inds) > 1:  # get_bipolar_channels(sensors_inds, sensors_lbls)
                        sensors_inds, sensors_lbls = head.get_sensors_id().get_bipolar_sensors(sensors_inds=sensors_inds)
                    inds = np.argsort(sensors_inds)
                    sensors_inds = np.array(sensors_inds)[inds].flatten().tolist()
                    sensors_lbls = np.array(sensors_lbls)[inds].flatten().tolist()
                    all_signals = np.zeros((signals.shape[0], len(model_inversion.sensors_labels)))
                    all_signals[:, sensors_inds] = signals[:, inds]
                    signals = all_signals
                    del all_signals
                    vois_ts_dict = {"time": time.flatten(), "signals": signals,
                                    "sensors_inds": sensors_inds, "sensors_lbls": sensors_lbls}
                    savemat(ts_file, vois_ts_dict)
                model_inversion.sensors_labels[vois_ts_dict["sensors_inds"]] = sensors_lbls
                manual_selection = sensors_inds
                n_electrodes = 4
                sensors_per_electrode = 2
            else:
                # -------------------------- Get simulated data (simulate if necessary) -----------------------------------
                target_data_type = "simulated"
                ts_file = os.path.join(FOLDER_VEP_HOME, hyp.name + "_ts.h5")
                vois_ts_dict = \
                    from_model_configuration_to_simulation(model_configuration, head, lsa_hypothesis, simulation_mode=TVB,
                                                           sim_type="fitting", dynamical_model=dynamical_model,
                                                           ts_file=ts_file, plot_flag=True,
                                                           save_flag=True, results_dir=results_dir,
                                                           figure_dir=figure_dir, tau1=0.5, tau0=30.0,
                                                           noise_intensity=10 ** -3)
                manual_selection = statistical_model.active_regions
                n_electrodes = 8
                sensors_per_electrode = 2
                sensors_lbls = model_inversion.sensors_labels
                # -------------------------- Select and set observation signals -----------------------------------
            signals, time, statistical_model, vois_ts_dict = \
                model_inversion.set_target_data_and_time(target_data_type, vois_ts_dict, statistical_model,
                                                         decimate=decimate, cut_signals_tails=cut_signals_tails,
                                                         select_signals=True, manual_selection=manual_selection,
                                                         auto_selection=False, # auto_selection="correlation-power",
                                                         # n_electrodes=n_electrodes,
                                                         # sensors_per_electrode=sensors_per_electrode,
                                                         # group_electrodes=True,
                                                         )
            # if len(model_inversion.signals_inds) < head.get_sensors_id().number_of_sensors:
            #     statistical_model = \
            #             model_inversion.update_active_regions_seeg(statistical_model)
            # if model_inversion.data_type == "lfp":
            #     labels = model_inversion.region_labels
            # else:
            #     labels = model_inversion.sensors_labels
            # if vois_ts_dict.get("signals", None) is not None:
            #     vois_ts_dict["signals"] -= vois_ts_dict["signals"].min()
            #     vois_ts_dict["signals"] /= vois_ts_dict["signals"].max()
            #     plotter.plot_raster({'Target Signals': vois_ts_dict["signals"]}, vois_ts_dict["time"].flatten(),
            #                 time_units="ms", title=hyp.name + ' Target Signals raster',
            #                 special_idx=model_inversion.signals_inds, offset=1, labels=labels,
            #                 figure_dir=figure_dir)
            # plotter.plot_timeseries({'Target Signals': signals}, time, time_units="ms", title=hyp.name + 'Target Signals ',
            #                 labels=labels[model_inversion.signals_inds],
            #                 figure_dir=figure_dir)
            writer.write_model_inversion_service(model_inversion, os.path.join(FOLDER_RES,
                                                                               hyp.name + "_ModelInversionService.h5"))
            writer.write_generic(statistical_model, results_dir, hyp.name + "_StatsModel.h5")
            # try:
            #     model_data = stan_service.load_model_data_from_file()
            # except:
            model_data = model_inversion.generate_model_data(statistical_model, signals)
            writer.write_dictionary(model_data, os.path.join(results_dir, hyp.name + "_ModelData.h5"))
        if os.path.isfile(EMPIRICAL):
            simulation_values = None
        else:
            simulation_values = {"x0": model_configuration.x0, "x1eq": model_configuration.x1EQ,
                                 "x1init": model_configuration.x1EQ, "zinit": model_configuration.zEQ}
        # Stupid code to interface with INS stan model
        if stats_model_name in ["vep-fe-rev-05", "vep-fe-rev-08", "vep-fe-rev-08a", "vep-fe-rev-08b"]:
            model_data = convert_to_vep_stan(model_data, statistical_model, model_inversion)
            x1_str = "x"
            input_signals_str = "seeg_log_power"
            signals_str = "mu_seeg_log_power"
            dX1t_str = "x_eta"
            dZt_str = "z_eta"
            sig_str = "sigma"
            eps_str = "epsilon"
            k_str = "k"
            pair_plot_params=["time_scale", "k", "sigma", "epsilon", "amplitude", "offset"]
            region_violin_params = ["x0", "x_init", "z_init"]
            if simulation_values is not None:
                simulation_values.update({"x0": simulation_values["x0"][statistical_model.active_regions]})
                simulation_values.update({"x_init": simulation_values["x1init"][statistical_model.active_regions]})
                simulation_values.update({"z_init": simulation_values["zinit"][statistical_model.active_regions]})
            connectivity_plot = False
            estMC = lambda: model_configuration.model_connectivity
            region_mode = "active"
        else:
            x1_str = "x1"
            input_signals_str = "signals"
            signals_str = "fit_signals"
            dX1t_str = "dX1t"  # "x1_dWt"
            dZt_str = "dZt" # "z_dWt"
            sig_str = "sig"
            eps_str = "eps"
            k_str = "K"
            pair_plot_params = ["tau1", "tau0", "K", "sig_eq", "sig_init", "sig", "eps", "scale_signal", "offset_signal"]
            region_violin_params = ["x0", "x1eq", "x1init", "zinit"]
            connectivity_plot = True
            estMC = lambda est: est["MC"]
            region_mode = "all"
        # -------------------------- Fit and get estimates: ------------------------------------------------------------
        ests, samples, summary = stan_service.fit(debug=1, simulate=0, model_data=model_data, merge_outputs=False,
                                                  chains=4, refresh=1, num_warmup=200, num_samples=300, **kwargs)
        writer.write_generic(ests, results_dir, hyp.name + "_fit_est.h5")
        writer.write_generic(samples, results_dir, hyp.name + "_fit_samples.h5")
        if summary is not None:
            writer.write_generic(summary, results_dir, hyp.name + "_fit_summary.h5")
            if isinstance(summary, dict):
                R_hat = summary.get("R_hat", None)
                if R_hat is not None:
                    R_hat = {"R_hat": R_hat}
        ests = ensure_list(ests)
        plotter.plot_fit_results(model_inversion, ests, samples, statistical_model, model_data[input_signals_str],
                                 R_hat, model_data["time"], simulation_values, region_mode,
                                 seizure_indices=lsa_hypothesis.get_regions_disease_indices(), x1_str=x1_str,
                                 signals_str=signals_str, sig_str=sig_str, dX1t_str=dX1t_str,
                                 dZt_str=dZt_str,  trajectories_plot=True, connectivity_plot=connectivity_plot,
                                 pair_plot_params=pair_plot_params, region_violin_params=region_violin_params)
        # -------------------------- Reconfigure model after fitting:---------------------------------------------------
        for id_est, est in enumerate(ensure_list(ests)):
            fit_model_configuration_service = \
                ModelConfigurationService(hyp.number_of_regions, K=est[k_str] * hyp.number_of_regions)
            x0_values_fit = \
                fit_model_configuration_service._compute_x0_values_from_x0_model(est['x0'])
            hyp_fit = \
                DiseaseHypothesis(head.connectivity.number_of_regions,
                                  excitability_hypothesis={tuple(range(model_configuration.n_regions)): x0_values_fit},
                                  epileptogenicity_hypothesis={}, connectivity_hypothesis={},
                                  name='fit' + str(id_est) + "_" + hyp.name)
            model_configuration_fit = fit_model_configuration_service.configure_model_from_hypothesis(hyp_fit, #est["MC"]
                                                                                                      estMC(est))
            writer.write_model_configuration(model_configuration_fit,
                                             os.path.join(results_dir, hyp_fit.name + "_ModelConfig.h5"))

            # Plot nullclines and equilibria of model configuration
            plotter.plot_state_space(model_configuration_fit,
                                     model_inversion.region_labels,
                                     special_idx=statistical_model.active_regions,
                                     model="6d", zmode="lin",
                                     figure_name=hyp_fit.name + "_Nullclines and equilibria")
        logger.info("Done!")


if __name__ == "__main__":
    SUBJECT = "TVB3"
    VEP_HOME = os.path.join("/Users/dionperd/Dropbox/Work/VBtech/VEP/results/CC")
    VEP_FOLDER = os.path.join(VEP_HOME, SUBJECT)
    DATA_CUSTOM = "/Users/dionperd/Dropbox/Work/VBtech/VEP/results/CC/" + SUBJECT
    SEEG_data = os.path.join("/Users/dionperd/Dropbox/Work/VBtech/VEP/data/CC", SUBJECT, "raw/seeg/ts_seizure")
    # TVB3 preselection:
    # sensors_lbls = [u"G'1", u"G'2", u"G'3", u"G'8", u"G'9", u"G'10", u"G'11", u"G'12", u"M'6", u"M'7", u"M'8", u"L'4",
    #                 u"L'5",  u"L'6", u"L'7", u"L'8", u"L'9"]
    # sensors_inds = [28, 29, 30, 35, 36, 37, 38, 39, 63, 64, 65, 47, 48, 49, 50, 51, 52]
    # TVB3 selection:
    sensors_lbls = [u"G'1", u"G'2", u"G'11", u"G'12", u"M'7", u"M'8", u"L'5", u"L'6"]
    sensors_inds = [28, 29, 38, 39, 64, 65, 48, 49]
    seizure = 'SZ1_0001.edf'
    times_on_off = [15.0, 35.0]
    ep_name = "clinical_hypothesis_postseeg"
    sensors_filename = "SensorsSEEG_116.h5"
    # # TVB4 preselection:
    # sensors_lbls = [u"D5", u"D6", u"D7",  u"D8", u"D9", u"D10", u"Z9", u"Z10", u"Z11", u"Z12", u"Z13", u"Z14",
    #                 u"S1", u"S2", u"S3", u"D'3", u"D'4", u"D'10", u"D'11", u"D'12", u"D'13", u"D'14"]
    # sensors_inds = [4, 5, 6, 7, 8, 9, 86, 87, 88, 89, 90, 91, 94, 95, 96, 112, 113, 119, 120, 121, 122, 123]
    # # TVB4:
    # seizure = 'SZ3_0001.edf'
    # sensors_filename = "SensorsSEEG_210.h5"
    # times_on_off = [20.0, 100.0]
    # ep_name = "clinical_hypothesis_preseeg_right"
    EMPIRICAL = False
    # stats_model_name = "vep_sde"
    stats_model_name = "vep-fe-rev-08a"
    fitmethod = "sample"
    if EMPIRICAL:
        main_fit_sim_hyplsa(ep_name=ep_name, data_folder=os.path.join(DATA_CUSTOM, 'Head'),
                            sensors_filename=sensors_filename, stats_model_name=stats_model_name,
                            EMPIRICAL=os.path.join(SEEG_data, seizure),
                            times_on_off=[15.0, 35.0], sensors_lbls=sensors_lbls, sensors_inds=sensors_inds,
                            fitmethod=fitmethod, stan_service="CmdStan", results_dir=FOLDER_RES,
                            figure_dir=FOLDER_FIGURES)  # , stan_service="PyStan"
    else:
        main_fit_sim_hyplsa(ep_name=ep_name, data_folder=os.path.join(DATA_CUSTOM, 'Head'),
                            sensors_filename=sensors_filename, stats_model_name=stats_model_name,
                            fitmethod=fitmethod, stan_service="CmdStan",
                            results_dir=FOLDER_RES, figure_dir=FOLDER_FIGURES)  # , stan_service="PyStan"
