# encoding=utf8
import sys

reload(sys)
sys.setdefaultencoding('utf8')

import os
import numpy as np
from scipy.io import savemat, loadmat
import pickle

from tvb_epilepsy.base.constants import VOIS, X0_DEF, E_DEF, TVB, DATA_MODE, SIMULATION_MODE
from tvb_epilepsy.base.configurations import FOLDER_RES, DATA_CUSTOM, STATISTICAL_MODELS_PATH, FOLDER_VEP_HOME, USER_HOME
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger, warning
from tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.service.lsa_service import LSAService
from tvb_epilepsy.service.model_configuration_service import ModelConfigurationService
from tvb_epilepsy.base.utils.plot_utils import plot_sim_results, plot_fit_results
from tvb_epilepsy.scripts.simulation_scripts import set_time_scales, prepare_vois_ts_dict, \
                                                    compute_seeg_and_write_ts_h5_file

if DATA_MODE is TVB:
    from tvb_epilepsy.tvb_api.readers_tvb import TVBReader as Reader
else:
    from tvb_epilepsy.custom.readers_custom import CustomReader as Reader

if SIMULATION_MODE is TVB:
    from tvb_epilepsy.scripts.simulation_scripts import setup_TVB_simulation_from_model_configuration \
        as setup_simulation_from_model_configuration
else:
    from tvb_epilepsy.scripts.simulation_scripts import setup_custom_simulation_from_model_configuration \
        as setup_simulation_from_model_configuration


logger = initialize_logger(__name__)


def main_fit_sim_hyplsa(stats_model_name="vep_original", EMPIRICAL='', times_on_off=[], channel_lbls=[],
                        channel_inds=[]):

    # ------------------------------Model code--------------------------------------
    # Compile or load model:
    model_file = os.path.join(FOLDER_VEP_HOME, stats_model_name + "_stan_model.pkl")
    if os.path.isfile(model_file):
        stats_model = pickle.load(open(model_file, 'rb'))
    else:
        # vep_original_DP
        if stats_model_name is "vep_dWt":
            model_path = os.path.join(STATISTICAL_MODELS_PATH, "vep_dWt.stan")
        elif stats_model_name is "vep_original_x0":
            model_path = os.path.join(STATISTICAL_MODELS_PATH, "vep_original_x0.stan")
        else:
            model_path = os.path.join(STATISTICAL_MODELS_PATH, "vep_original_DP.stan")
        stats_model = compile_model(model_stan_code_path=model_path)
        with open(model_file, 'wb') as f:
            pickle.dump(stats_model, f)

    # -------------------------------Reading model_data-----------------------------------

    data_folder = os.path.join(DATA_CUSTOM, 'Head')

    reader = Reader()

    logger.info("Reading from: " + data_folder)
    head = reader.read_head(data_folder, seeg_sensors_files=[("SensorsInternal.h5", "")])

    # head.plot()

    if len(channel_inds) > 1:
        channel_inds, _ = get_bipolar_channels(channel_inds, channel_lbls)

    # --------------------------Hypothesis definition-----------------------------------

    n_samples = 100

    # # Manual definition of hypothesis...:
    # x0_indices = [20]
    # x0_values = [0.9]
    # e_indices = [70]
    # e_values = [0.9]
    # disease_values = x0_values + e_values
    # disease_indices = x0_indices + e_indices

    # ...or reading a custom file:
    ep_name = "ep_l_frontal_complex"
    # FOLDER_RES = os.path.join(data_folder, ep_name)
    from tvb_epilepsy.custom.readers_custom import CustomReader

    if not isinstance(reader, CustomReader):
        reader = CustomReader()
    disease_values = reader.read_epileptogenicity(data_folder, name=ep_name)
    disease_indices, = np.where(disease_values > np.min([X0_DEF, E_DEF]))
    disease_values = disease_values[disease_indices]
    inds = np.argsort(disease_values)
    disease_values = disease_values[inds]
    disease_indices = disease_indices[inds]
    x0_indices = [disease_indices[-1]]
    x0_values = [disease_values[-1]]
    e_indices = disease_indices[0:-1].tolist()
    e_values = disease_values[0:-1].tolist()
    disease_indices = list(disease_indices)

    n_x0 = len(x0_indices)
    n_e = len(e_indices)
    n_disease = len(disease_indices)
    all_regions_indices = np.array(range(head.number_of_regions))
    healthy_indices = np.delete(all_regions_indices, disease_indices).tolist()
    n_healthy = len(healthy_indices)

    # This is an example of Excitability Hypothesis:
    hyp_x0 = DiseaseHypothesis(head.connectivity.number_of_regions,
                               excitability_hypothesis={tuple(disease_indices): disease_values},
                               epileptogenicity_hypothesis={}, connectivity_hypothesis={})

    # This is an example of Mixed Hypothesis:
    hyp_x0_E = DiseaseHypothesis(head.connectivity.number_of_regions,
                               excitability_hypothesis={tuple(x0_indices): x0_values},
                               epileptogenicity_hypothesis={tuple(e_indices): e_values}, connectivity_hypothesis={})

    hyp_E = DiseaseHypothesis(head.connectivity.number_of_regions,
                               excitability_hypothesis={},
                               epileptogenicity_hypothesis={tuple(disease_indices): disease_values}, connectivity_hypothesis={})

    hypos = (hyp_x0_E, hyp_x0, hyp_E)
    # --------------------------Simulation preparations-----------------------------------
    tau1 = 0.5
    # TODO: maybe use a custom Monitor class
    fs = 10*2048.0*(2*tau1)  # this is the simulation sampling rate that is necessary for the simulation to be stable
    time_length = 50.0 / tau1  # msecs, the final output nominal time length of the simulation
    report_every_n_monitor_steps = 100.0
    (dt, fsAVG, sim_length, monitor_period, n_report_blocks) = \
        set_time_scales(fs=fs, time_length=time_length, scale_fsavg=1,
                        report_every_n_monitor_steps=report_every_n_monitor_steps)

    # Choose model
    # Available models beyond the TVB Epileptor (they all encompass optional variations from the different papers):
    # EpileptorDP: similar to the TVB Epileptor + optional variations,
    # EpileptorDP2D: reduced 2D model, following Proix et all 2014 +optional variations,
    # EpleptorDPrealistic: starting from the TVB Epileptor + optional variations, but:
    #      -x0, Iext1, Iext2, slope and K become noisy state variables,
    #      -Iext2 and slope are coupled to z, g, or z*g in order for spikes to appear before seizure,
    #      -multiplicative correlated noise is also used
    # Optional variations:
    zmode = "lin"  # by default, or "sig" for the sigmoidal expression for the slow z variable in Proix et al. 2014
    pmode = "z"  # by default, "g" or "z*g" for the feedback coupling to Iext2 and slope for EpileptorDPrealistic

    model_name = "EpileptorDP2D"
    if model_name is "EpileptorDP2D":
        spectral_raster_plot = False
        trajectories_plot = True
    else:
        spectral_raster_plot = False # "lfp"
        trajectories_plot = False
    # We don't want any time delays for the moment
    # head.connectivity.tract_lengths *= TIME_DELAYS_FLAG

    # --------------------------Hypothesis and LSA-----------------------------------

    for hyp in hypos: #hypotheses:

        logger.info("\n\nRunning hypothesis: " + hyp.name)

        # hyp.write_to_h5(FOLDER_RES, hyp.name + ".h5")

        logger.info("\n\nCreating model configuration...")
        model_configuration_service = ModelConfigurationService(hyp.number_of_regions, K=10.0)
        # model_configuration_service.write_to_h5(FOLDER_RES, hyp.name + "_model_config_service.h5")

        if hyp.type == "Epileptogenicity":
            model_configuration = model_configuration_service. \
                configure_model_from_E_hypothesis(hyp, head.connectivity.normalized_weights)
        else:
            model_configuration = model_configuration_service. \
                configure_model_from_hypothesis(hyp, head.connectivity.normalized_weights)
        model_configuration.write_to_h5(FOLDER_RES, hyp.name + "_ModelConfig.h5")

        # Plot nullclines and equilibria of model configuration
        model_configuration_service.plot_nullclines_eq(model_configuration, head.connectivity.region_labels,
                                                       special_idx=disease_indices, model="6d", zmode="lin",
                                                       figure_name=hyp.name + "_Nullclines and equilibria")

        logger.info("\n\nRunning LSA...")
        lsa_service = LSAService(eigen_vectors_number=None, weighted_eigenvector_sum=True)
        lsa_hypothesis = lsa_service.run_lsa(hyp, model_configuration)

        lsa_hypothesis.write_to_h5(FOLDER_RES, lsa_hypothesis.name + "_LSA.h5")
        lsa_service.write_to_h5(FOLDER_RES, lsa_hypothesis.name + "_LSAConfig.h5")

        lsa_service.plot_lsa(lsa_hypothesis, model_configuration, head.connectivity.region_labels, None)

        # ------------------------------Simulation--------------------------------------
        logger.info("\n\nConfiguring simulation...")
        noise_intensity = 10 ** -2.8
        sim = setup_simulation_from_model_configuration(model_configuration, head.connectivity, dt,
                                                        sim_length, monitor_period, model_name,
                                                        zmode=np.array(zmode), pmode=np.array(pmode),
                                                        noise_instance=None, noise_intensity=noise_intensity,
                                                        monitor_expressions=None)
        sim.model.tau1 = tau1
        sim.model.tau0 = 30.0

        # Integrator and initial conditions initialization.
        # By default initial condition is set right on the equilibrium point.
        sim.config_simulation(initial_conditions=None)

        # convert_to_h5_model(sim.model).write_to_h5(FOLDER_RES, lsa_hypothesis.name + "_sim_model.h5")

        if os.path.isfile(EMPIRICAL):

            observation, time, fs = prepare_seeg_observable(EMPIRICAL, times_on_off, channel_lbls, log_flag=True)
            vois_ts_dict = {"time": time, "signals": observation}
            #
            # prepare_seeg_observable(os.path.join(SEEG_data, 'SZ2_0001.edf'), [15.0, 40.0], channel_lbls)

            # prepare_seeg_observable(os.path.join(SEEG_data, 'SZ5_0001.edf'), [20.0, 45.0], channel_lbls)
        else:

            ts_file = os.path.join(FOLDER_VEP_HOME, lsa_hypothesis.name + "_ts.mat")
            if os.path.isfile(ts_file):
                logger.info("\n\nLoading previously simulated time series...")
                vois_ts_dict = loadmat(ts_file)
            else:
                logger.info("\n\nSimulating...")
                ttavg, tavg_data, status = sim.launch_simulation(n_report_blocks)

                # convert_to_h5_model(sim.simulation_settings).write_to_h5(FOLDER_RES,
                #                                                          lsa_hypothesis.name + "_sim_settings.h5")

                if not status:
                    warning("\nSimulation failed!")

                else:

                    time = np.array(ttavg, dtype='float32').flatten()

                    output_sampling_time = np.mean(np.diff(time))
                    tavg_data = tavg_data[:, :, :, 0]

                    logger.info("\n\nSimulated signal return shape: %s", tavg_data.shape)
                    logger.info("Time: %s - %s", time[0], time[-1])
                    logger.info("Values: %s - %s", tavg_data.min(), tavg_data.max())

                    # Variables of interest in a dictionary:
                    vois_ts_dict = prepare_vois_ts_dict(VOIS[model_name], tavg_data)
                    vois_ts_dict['time'] = time
                    vois_ts_dict['time_units'] = 'msec'

                    vois_ts_dict=compute_seeg_and_write_ts_h5_file(FOLDER_RES, lsa_hypothesis.name + "_ts.h5", sim.model,
                                                                   vois_ts_dict, output_sampling_time, time_length,
                                                                   hpf_flag=True, hpf_low=10.0, hpf_high=512.0,
                                                                   sensor_dicts_list=[head.sensorsSEEG])

                    # Plot results
                    plot_sim_results(sim.model, lsa_hypothesis.propagation_indices, lsa_hypothesis.name, head, vois_ts_dict,
                                     head.sensorsSEEG.keys(), hpf_flag=False, trajectories_plot=trajectories_plot,
                                     spectral_raster_plot=spectral_raster_plot, log_scale=True)

                    # Optionally save results in mat files
                    savemat(os.path.join(FOLDER_RES, lsa_hypothesis.name + "_ts.mat"), vois_ts_dict)

        # Get model_data and observation signals:
        data, active_regions = prepare_data_for_fitting_vep(stats_model_name, model_configuration, lsa_hypothesis,
                                                            fsAVG, vois_ts_dict, sim.model,
                                                            noise_intensity, active_regions=None,
                                                            active_regions_th=0.1, euler_method=1,
                                                            observation_model=1, channel_inds=channel_inds,
                                                            mixing=head.sensorsSEEG.values()[0])
        savemat(os.path.join(FOLDER_RES, lsa_hypothesis.name + "_fit_data.mat"), data)

        # Fit and get estimates:
        est, fit = stanfit_model(stats_model, data, mode="optimizing", iter=30000) #
        savemat(os.path.join(FOLDER_RES, lsa_hypothesis.name + "_fit_est.mat"), est)

        plot_fit_results(lsa_hypothesis.name, head, est, data, active_regions,
                         time=vois_ts_dict['time'], seizure_indices=[0, 1], trajectories_plot=True)

        # Reconfigure model after fitting:
        fit_model_configuration_service = ModelConfigurationService(hyp.number_of_regions,
                                                                    K=est['K'] * hyp.number_of_regions)

        x0_values_fit = fit_model_configuration_service._compute_x0_values_from_x0_model(est['x0'])
        disease_indices = active_regions.tolist()
        hyp_fit = DiseaseHypothesis(head.connectivity.number_of_regions,
                                    excitability_hypothesis={tuple(disease_indices): x0_values_fit},
                                    epileptogenicity_hypothesis={}, connectivity_hypothesis={},
                                    name='fit_' + hyp_x0.name)

        connectivity_matrix_fit = np.array(model_configuration.connectivity_matrix)
        connectivity_matrix_fit[active_regions][:, active_regions] = est["FC"]
        model_configuration_fit = fit_model_configuration_service.configure_model_from_hypothesis(hyp_fit,
                                                                                             connectivity_matrix_fit)
        model_configuration_fit.write_to_h5(FOLDER_RES, hyp_fit.name + "_ModelConfig.h5")

        # Plot nullclines and equilibria of model configuration
        model_configuration_service.plot_nullclines_eq(model_configuration_fit, head.connectivity.region_labels,
                                                       special_idx=disease_indices, model="6d", zmode="lin",
                                                       figure_name=hyp_fit.name + "_Nullclines and equilibria")

        print("Done!")


if __name__ == "__main__":

    VEP_HOME = os.path.join(USER_HOME, 'VEP/CC')
    VEP_FOLDER = os.path.join(VEP_HOME, 'TVB3')
    CT = os.path.join(VEP_FOLDER, 'CT')
    SEEG = os.path.join(VEP_FOLDER, 'SEEG')
    SEEG_data = os.path.join(VEP_FOLDER, 'SEEG_data')
    #
    channels = [u"G'1", u"G'2", u"G'3", u"G'8", u"G'9", u"G'10", u"G'11", u"G'12", u"M'6", u"M'7", u"M'8", u"L'4",
                u"L'5",  u"L'6", u"L'7", u"L'8", u"L'9"]

    channel_inds = [67, 68, 69, 74, 75, 76, 77, 78, 21, 22, 23, 43, 44, 45, 46,  47, 48] #


    # -------------------------------Reading model_data-----------------------------------


    # data_folder = os.path.join(DATA_CUSTOM, 'Head')
    #
    # reader = Reader()
    #
    # logger.info("Reading from: " + data_folder)
    # head = reader.read_head(data_folder, seeg_sensors_files=[("SensorsInternal.h5", "")])
    # nearest_regions = head.compute_nearest_regions_to_sensors("SEEG", channels_inds)
    #
    # for ic, ch in enumerate(channels):
    #     print("\n" + ch + "<-" + str(nearest_regions[ic][1]) + str(nearest_regions[ic][2]))

    channels = [u"G'1", u"G'2", u"G'11", u"G'12", u"M'6", u"M'7", u"L'6", u"L'7"]
    channel_inds = [67, 68, 77, 78, 21, 22, 45, 46]

    # prepare_seeg_observable(os.path.join(SEEG_data, 'SZ1_0001.edf'), [10.0, 35.0], channels)
    #
    # prepare_seeg_observable(os.path.join(SEEG_data, 'SZ2_0001.edf'), [15.0, 40.0], channels)

    # prepare_seeg_observable(os.path.join(SEEG_data, 'SZ5_0001.edf'), [20.0, 45.0], channels)

    stats_model_name = "vep_original_x0"
    main_fit_sim_hyplsa(stats_model_name, EMPIRICAL=os.path.join(SEEG_data, 'SZ1_0001.edf'), times_on_off=[10.0, 35.0],
                       channel_lbls=channels, channel_inds=channel_inds)
    # main_fit_sim_hyplsa(stats_model_name, channel_lbls=channels, channel_inds=channel_inds)