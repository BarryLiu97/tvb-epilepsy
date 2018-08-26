import os
import numpy as np
from tvb_fit.base.utils.log_error_utils import initialize_logger
from tvb_fit.base.utils.data_structures_utils import isequal_string
from tvb_fit.base.model.virtual_patient.sensors import Sensors
from tvb_fit.tvb_epilepsy.base.constants.config import Config
from tvb_fit.tvb_epilepsy.io.h5_reader import H5Reader
from tvb_fit.tvb_epilepsy.io.h5_writer import H5Writer
from tvb_fit.tvb_epilepsy.plot.plotter import Plotter
from tvb_fit.tvb_epilepsy.base.model.epileptor_models import EpileptorDP2D
from tvb_fit.tvb_epilepsy.base.model.timeseries import Timeseries
from tvb_fit.tvb_epilepsy.service.simulator.simulator_builder import build_simulator_TVB_realistic, \
    build_simulator_TVB_fitting, build_simulator_TVB_default, build_simulator_TVB_paper
from tvb_fit.service.timeseries_service import TimeseriesService


logger = initialize_logger(__name__)


def _compute_and_write_seeg(source_timeseries, sensors_list, filename, hpf_flag=False, hpf_low=10.0,
                            hpf_high=256.0, seeg_gain_mode="lin", h5_writer=H5Writer()):
    ts_service = TimeseriesService()
    fsAVG = 1000.0 / source_timeseries.time_step

    if hpf_flag:
        hpf_low = max(hpf_low, 1000.0 / (source_timeseries.end_time - source_timeseries.time_start))
        hpf_high = min(fsAVG / 2.0 - 10.0, hpf_high)

    idx_proj = -1
    seeg_data = []
    for sensor in sensors_list:
        if isinstance(sensor, Sensors):
            idx_proj += 1
            seeg = ts_service.compute_seeg(source_timeseries, [sensor], sum_mode=seeg_gain_mode)[0]

            if hpf_flag:
                seeg = ts_service.filter(seeg, hpf_low, hpf_high, mode='bandpass', order=3)

            # TODO: test the case where we save subsequent seeg data from different sensors
            h5_writer.write_ts_seeg_epi(seeg, source_timeseries.time_step, filename)
            seeg_data.append(seeg)

    return seeg_data


# TODO: simplify and separate flow steps
def compute_seeg_and_write_ts_to_h5(timeseries, model, sensors_list, filename, seeg_gain_mode="lin",
                                    hpf_flag=False, hpf_low=10.0, hpf_high=256.0, h5_writer=H5Writer()):
    filename_epi = os.path.splitext(filename)[0] + "_epi.h5"
    h5_writer.write_ts(timeseries, timeseries.time_step, filename)
    source_timeseries = timeseries.get_source()
    h5_writer.write_ts_epi(timeseries, timeseries.time_step, filename_epi, source_timeseries)
    if isinstance(model, EpileptorDP2D):
        hpf_flag = False
    seeg_ts_all = _compute_and_write_seeg(source_timeseries, sensors_list, filename_epi, hpf_flag, hpf_low, hpf_high,
                                          seeg_gain_mode, h5_writer=h5_writer)

    return timeseries, seeg_ts_all


def from_model_configuration_to_simulation(model_configuration, head, lsa_hypothesis,
                                           sim_type="realistic", ts_file=None, seeg_gain_mode="lin", hpf_flag=False,
                                           hpf_low=10.0, hpf_high=512.0, config=Config(), plotter=False):
    # Choose model
    # Available models beyond the TVB Epileptor (they all encompass optional variations from the different papers):
    # EpileptorDP: similar to the TVB Epileptor + optional variations,
    # EpileptorDP2D: reduced 2D model, following Proix et all 2014 +optional variations,
    # EpleptorDPrealistic: starting from the TVB Epileptor + optional variations, but:
    #      -x0, Iext1, Iext2, slope and K become noisy state variables,
    #      -Iext2 and slope are coupled to z, g, or z*g in order for spikes to appear before seizure,
    #      -multiplicative correlated noise is also used
    # Optional variations:

    # ------------------------------Simulation--------------------------------------
    hypname = lsa_hypothesis.name.replace("_LSA", "")
    logger.info("\n\nConfiguring simulation...")
    if isequal_string(sim_type, "realistic"):
        sim, sim_settings= build_simulator_TVB_realistic(model_configuration, head.connectivity)
    elif isequal_string(sim_type, "fitting"):
        sim, sim_settings = build_simulator_TVB_fitting(model_configuration, head.connectivity)
    elif isequal_string(sim_type, "paper"):
        sim, sim_settings = build_simulator_TVB_paper(model_configuration, head.connectivity)
    else:
        sim, sim_settings = build_simulator_TVB_default(model_configuration, head.connectivity)
    dynamical_model = sim.model
    writer = H5Writer()
    writer.write_simulator_model(sim.model, os.path.join(config.out.FOLDER_RES,
                                              hypname + dynamical_model._ui_name + "_model.h5"),
                                 sim.connectivity.number_of_regions)

    seeg=[]
    if ts_file is not None and os.path.isfile(ts_file):
        logger.info("\n\nLoading previously simulated time series from file: " + ts_file)
        sim_output = H5Reader().read_timeseries(ts_file)
        seeg = TimeseriesService().compute_seeg(sim_output.get_source(), head.sensorsSEEG, sum_mode=seeg_gain_mode)
    else:
        logger.info("\n\nSimulating %s..." % sim_type)
        sim_output, status = sim.launch_simulation(report_every_n_monitor_steps=100, timeseries=Timeseries)
        if not status:
            logger.warning("\nSimulation failed!")
        else:
            time = np.array(sim_output.time_line).astype("f")
            logger.info("\n\nSimulated signal return shape: %s", sim_output.shape)
            logger.info("Time: %s - %s", time[0], time[-1])
            sim_output, seeg = compute_seeg_and_write_ts_to_h5(sim_output, sim.model, head.sensorsSEEG,
                                                               ts_file, seeg_gain_mode=seeg_gain_mode,
                                                               hpf_flag=hpf_flag, hpf_low=hpf_low, hpf_high=hpf_high)

    if plotter:
        if not isinstance(plotter, Plotter):
            plotter = Plotter(config)
        # Plot results
        plotter.plot_simulated_timeseries(sim_output, sim.model, lsa_hypothesis.lsa_propagation_indices, seeg_list=seeg,
                                          spectral_raster_plot=False, title_prefix=hypname,
                                          spectral_options={"log_scale": True})

    return {"source": sim_output, "seeg": seeg}, sim
