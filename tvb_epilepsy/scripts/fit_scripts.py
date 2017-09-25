import os
import time
import numpy as np
import pystan as ps

from tvb_epilepsy.base.constants import X1_DEF, X1_EQ_CR_DEF, X0_DEF, X0_CR_DEF, VOIS, X0_DEF, E_DEF, TVB, DATA_MODE, \
                                        SIMULATION_MODE
from tvb_epilepsy.base.configurations import FOLDER_RES, DATA_CUSTOM, STATISTICAL_MODELS_PATH
from tvb_epilepsy.base.utils import warning, raise_not_implemented_error, initialize_logger
from tvb_epilepsy.base.computations.calculations_utils import calc_x0cr_r
from tvb_epilepsy.base.computations.equilibrium_computation import calc_eq_z
from tvb_epilepsy.service.sampling_service import gamma_from_mu_std
from tvb_epilepsy.service.epileptor_model_factory import model_noise_intensity_dict
from tvb_epilepsy.base.h5_model import convert_to_h5_model
from tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.service.lsa_service import LSAService
from tvb_epilepsy.service.model_configuration_service import ModelConfigurationService
from tvb_epilepsy.base.plot_utils import plot_sim_results
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


def prepare_model_and_data_for_fitting(model_configuration, hypothesis, fs, signals,
                                       model_path=os.path.join(STATISTICAL_MODELS_PATH, "vep_autoregress.stan"),
                                       active_regions=None, active_regions_th=0.1, observation_model=3, mixing=None,
                                       **kwargs):

    tic = time.time()
    logger.info("Compiling model...")
    model = ps.StanModel(file=model_path, model_name=kwargs.get("model_name", 'vep_epileptor2D_autoregress'))
    logger.info(str(time.time() - tic) + ' sec required to compile')

    logger.info("Constructing data dictionary...")
    active_regions_flag = np.zeros((hypothesis.number_of_regions, ), dtype="i")

    if active_regions is None:
        if len(hypothesis.propagation_strengths) > 0:
            active_regions = np.where(hypothesis.propagation_strengths / np.max(hypothesis.propagation_strengths)
                                      > active_regions_th)[0]
        else:
            raise_not_implemented_error("There is no other way of automatic selection of " +
                                        "active regions implemented yet!")

    active_regions_flag[active_regions] = 1
    n_active_regions = len(active_regions)

    # Gamma distributions' parameters
    # visualize gamma distributions here: http://homepage.divms.uiowa.edu/~mbognar/applets/gamma.html
    tau1 = gamma_from_mu_std(kwargs.get("tau1_mu", 0.2), kwargs.get("tau1_std", 0.1))
    tau0 = gamma_from_mu_std(kwargs.get("tau0_mu", 10000.0), kwargs.get("tau0_std", 10000.0))
    K = gamma_from_mu_std(kwargs.get("K_mu", 10.0 / hypothesis.number_of_regions),
                          kwargs.get("K_std", 10.0 / hypothesis.number_of_regions))
    # zero effective connectivity:
    conn0 = gamma_from_mu_std(kwargs.get("conn0_mu", 0.001), kwargs.get("conn0_std", 0.001))
    sig_mu = np.mean(model_noise_intensity_dict["EpileptorDP2D"])
    sig = gamma_from_mu_std(kwargs.get("sig_mu", sig_mu), kwargs.get("sig_std", sig_mu))
    sig_eq_mu = 0.1/3.0
    sig_eq = gamma_from_mu_std(kwargs.get("sig_eq_mu", sig_eq_mu), kwargs.get("sig_eq_std", sig_eq_mu))
    sig_init_mu = sig_eq_mu
    sig_init = gamma_from_mu_std(kwargs.get("sig_init_mu", sig_init_mu), kwargs.get("sig_init_std", sig_init_mu))

    if mixing is None:
        observation_model = 3;
        mixing = np.eye(n_active_regions)
        signals = signals[:, active_regions]


    data = {"n_regions": hypothesis.number_of_regions,
            "n_active_regions": n_active_regions,
            "n_nonactive_regions": hypothesis.number_of_regions-n_active_regions,
            "active_regions_flag": active_regions_flag,
            "n_time": signals.shape[0],
            "n_signals": signals.shape[1],
            "x0_nonactive": model_configuration.x0[~active_regions_flag.astype("bool")],
            "x1eq0": model_configuration.x1EQ,
            "x1eq_lo": kwargs.get("x1eq_lo", -2.0),
            "x1eq_hi": kwargs.get("x1eq_hi", X1_EQ_CR_DEF),
            "x1init_lo": kwargs.get("x1init_lo", -2.0),
            "x1init_hi": kwargs.get("x1init_hi", -1.0),
            "x1_lo": kwargs.get("x1_lo", -2.5),
            "x1_hi": kwargs.get("x1_hi", 1.5),
            "z_lo": kwargs.get("z_lo", 2.0),
            "z_hi": kwargs.get("z_hi", 5.0),
            "tau1_lo": kwargs.get("tau1_lo", 0.001),
            "tau1_hi": kwargs.get("tau1_hi", 1.0),
            "tau0_lo": kwargs.get("tau0_lo", 1000.0),
            "tau0_hi": kwargs.get("tau0_hi", 100000.0),
            "tau1_a": kwargs.get("tau1_a", tau1["alpha"]),
            "tau1_b": kwargs.get("tau1_b", tau1["beta"]),
            "tau0_a": kwargs.get("tau0_a", tau0["alpha"]),
            "tau0_b": kwargs.get("tau0_b", tau0["beta"]),
            "SC": model_configuration.connectivity_matrix,
            "SC_sig": kwargs.get("SC_sig", 0.1),
            "K_lo": kwargs.get("K_lo", 1.0 / hypothesis.number_of_regions),
            "K_hi": kwargs.get("K_hi", 100.0 / hypothesis.number_of_regions),
            "K_a": kwargs.get("K_a", K["alpha"]),
            "K_b": kwargs.get("K_b", K["beta"]),
            "gamma0": kwargs.get("gamma0", np.array([conn0["alpha"], conn0["beta"]])),
            "dt": 1000.0 / fs,
            "sig_hi": kwargs.get("sig_hi", 1.0 / fs),
            "sig_a": kwargs.get("sig_a", sig["alpha"]),
            "sig_b": kwargs.get("sig_b", sig["beta"]),
            "sig_eq_hi": kwargs.get("sig_eq_hi", 3*sig_eq_mu),
            "sig_eq_a": kwargs.get("sig_eq_a", sig_eq["alpha"]),
            "sig_eq_b": kwargs.get("sig_eq_b", sig_eq["beta"]),
            "sig_init_hi": kwargs.get("sig_init_hi", 3 * sig_init_mu),
            "sig_init_a": kwargs.get("sig_init_a", sig_init["alpha"]),
            "sig_init_b": kwargs.get("sig_init_b", sig_init["beta"]),
            "observation_model": observation_model,
            "signals": signals,
            "mixing": mixing,
            "eps_hi": kwargs.get("eps_hi", (np.max(signals.flatten()) - np.min(signals.flatten()) / 100.0)),
            "eps_x0": kwargs.get("eps_x0", 0.1),
    }

    for p in ["a", "b", "d", "yc", "Iext1", "slope"]:

        temp = getattr(model_configuration, p)
        if isinstance(temp, (np.ndarray, list)):
            if np.all(temp[0], np.array(temp)):
                temp = temp[0]
            else:
                raise_not_implemented_error("Statistical models where not all regions have the same value " +
                                            " for parameter " + p + " are not implemented yet!")
        data.update({p: temp})

    zeq_lo = calc_eq_z(data["x1eq_hi"], data["yc"], data["Iext1"], "2d", x2=0.0, slope=data["slope"], a=data["a"],
                       b=data["b"], d=data["d"])
    zeq_hi = calc_eq_z(data["x1eq_lo"], data["yc"], data["Iext1"], "2d", x2=0.0, slope=data["slope"], a=data["a"],
                       b=data["b"], d=data["d"])
    data.update({"zeq_lo": kwargs.get("zeq_lo", zeq_lo),
                 "zeq_hi": kwargs.get("zeq_hi", zeq_hi)})
    data.update({"zinit_lo": kwargs.get("zinit_lo", zeq_lo - sig_init_mu),
                 "zinit_hi": kwargs.get("zinit_hi", zeq_hi + sig_init_mu)})

    x0cr, rx0 = calc_x0cr_r(data["yc"], data["Iext1"], data["a"], data["b"], data["d"], zmode=np.array("lin"),
                            x1_rest=X1_DEF, x1_cr=X1_EQ_CR_DEF, x0def=X0_DEF, x0cr_def=X0_CR_DEF, test=False,
                            shape=None, calc_mode="non_symbol")

    data.update({"x0cr": x0cr, "rx0": rx0})
    logger.info("data dictionary completed with " + str(len(data)) + " fields:\n" + str(data.keys()))

    return model, data


def stanfit_model(model, data, mode="sampling", **kwargs):

    logger.info("Model sampling...")
    fit = getattr(model, mode)(data=data, **kwargs)

    logger.info("Extracting estimates...")
    est = fit.extract(permuted=True)

    return fit, est


def main_fit_sim_hyplsa():

    # -------------------------------Reading data-----------------------------------

    data_folder = os.path.join(DATA_CUSTOM, 'Head')

    reader = Reader()

    logger.info("Reading from: " + data_folder)
    head = reader.read_head(data_folder)

    head.plot()

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
    ep_name = "ep_test1"
    # FOLDER_RES = os.path.join(data_folder, ep_name)
    from tvb_epilepsy.custom.readers_custom import CustomReader

    if not isinstance(reader, CustomReader):
        reader = CustomReader()
    disease_values = reader.read_epileptogenicity(data_folder, name=ep_name)
    disease_indices, = np.where(disease_values > np.min([X0_DEF, E_DEF]))
    disease_values = disease_values[disease_indices]
    if disease_values.size > 1:
        inds_split = np.ceil(disease_values.size * 1.0 / 2).astype("int")
        x0_indices = disease_indices[:inds_split].tolist()
        e_indices = disease_indices[inds_split:].tolist()
        x0_values = disease_values[:inds_split].tolist()
        e_values = disease_values[inds_split:].tolist()
    else:
        x0_indices = disease_indices.tolist()
        x0_values = disease_values.tolist()
        e_indices = []
        e_values = []
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

    # This is an example of Epileptogenicity Hypothesis:
    hyp_E = DiseaseHypothesis(head.connectivity.number_of_regions,
                              excitability_hypothesis={},
                              epileptogenicity_hypothesis={tuple(disease_indices): disease_values},
                              connectivity_hypothesis={})

    if len(e_indices) > 0:
        # This is an example of x0_values mixed Excitability and Epileptogenicity Hypothesis:
        hyp_x0_E = DiseaseHypothesis(head.connectivity.number_of_regions,
                                     excitability_hypothesis={tuple(x0_indices): x0_values},
                                     epileptogenicity_hypothesis={tuple(e_indices): e_values},
                                     connectivity_hypothesis={})
        hypotheses = (hyp_x0, hyp_E, hyp_x0_E)

    else:
        hypotheses = (hyp_x0, hyp_E)

    # --------------------------Simulation preparations-----------------------------------

    # TODO: maybe use a custom Monitor class
    fs = 2048.0  # this is the simulation sampling rate that is necessary for the simulation to be stable
    time_length = 10000.0  # =100 secs, the final output nominal time length of the simulation
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
        spectral_raster_plot = "lfp"
        trajectories_plot = False
    # We don't want any time delays for the moment
    # head.connectivity.tract_lengths *= TIME_DELAYS_FLAG

    # --------------------------Hypothesis and LSA-----------------------------------

    for hyp in hypotheses:

        logger.info("\n\nRunning hypothesis: " + hyp.name)

        # hyp.write_to_h5(FOLDER_RES, hyp.name + ".h5")

        logger.info("\n\nCreating model configuration...")
        model_configuration_service = ModelConfigurationService(hyp.number_of_regions)
        model_configuration_service.write_to_h5(FOLDER_RES, hyp.name + "_model_config_service.h5")

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
        sim = setup_simulation_from_model_configuration(model_configuration, head.connectivity, dt,
                                                        sim_length, monitor_period, model_name,
                                                        zmode=np.array(zmode), pmode=np.array(pmode),
                                                        noise_instance=None, noise_intensity=None,
                                                        monitor_expressions=None)

        # Integrator and initial conditions initialization.
        # By default initial condition is set right on the equilibrium point.
        sim.config_simulation(initial_conditions=None)

        convert_to_h5_model(sim.model).write_to_h5(FOLDER_RES, lsa_hypothesis.name + "_sim_model.h5")

        logger.info("\n\nSimulating...")
        ttavg, tavg_data, status = sim.launch_simulation(n_report_blocks)

        convert_to_h5_model(sim.simulation_settings).write_to_h5(FOLDER_RES,
                                                                 lsa_hypothesis.name + "_sim_settings.h5")

        if not status:
            warning("\nSimulation failed!")

        else:

            time = np.array(ttavg, dtype='float32')

            output_sampling_time = np.mean(np.diff(time))
            tavg_data = tavg_data[:, :, :, 0]

            logger.info("\n\nSimulated signal return shape: %s", tavg_data.shape)
            logger.info("Time: %s - %s", time[0], time[-1])
            logger.info("Values: %s - %s", tavg_data.min(), tavg_data.max())

            # Variables of interest in a dictionary:
            vois_ts_dict = prepare_vois_ts_dict(VOIS[model_name], tavg_data)
            vois_ts_dict['time'] = time
            vois_ts_dict['time_units'] = 'msec'

            compute_seeg_and_write_ts_h5_file(FOLDER_RES, lsa_hypothesis.name + "_ts.h5", sim.model, vois_ts_dict,
                                              output_sampling_time, time_length,
                                              hpf_flag=True, hpf_low=10.0, hpf_high=512.0,
                                              sensor_dicts_list=[head.sensorsSEEG])

            # Plot results
            plot_sim_results(sim.model, lsa_hypothesis.propagation_indices, lsa_hypothesis.name, head, vois_ts_dict,
                             head.sensorsSEEG.keys(), hpf_flag=True, trajectories_plot=trajectories_plot,
                             spectral_raster_plot=spectral_raster_plot, log_scale=True)

            # Optionally save results in mat files
            # from scipy.io import savemat
            # savemat(os.path.join(FOLDER_RES, lsa_hypothesis.name + "_ts.mat"), vois_ts_dict)

            model, data = prepare_model_and_data_for_fitting(model_configuration, lsa_hypothesis, fs,
                                                             vois_ts_dict["x1"],
                                                             active_regions=None,
                                                             active_regions_th=0.1,
                                                             observation_model=3,
                                                             mixing=None)

            fit,  est = stanfit_model(model, data, mode="sampling", chains=1)

            print("Done!")



if __name__ == "__main__":

    main_fit_sim_hyplsa()