"""
Entry point for working with refactored code
"""
import os
import warnings

import numpy
from scipy.io import savemat

from tvb_epilepsy.base.constants import FOLDER_RES, FOLDER_FIGURES, SAVE_FLAG, SHOW_FLAG, SIMULATION_MODE, \
    TVB, DATA_MODE
from tvb_epilepsy.base.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.base.equilibrum_service import EquilibrumComputationService
from tvb_epilepsy.base.plot_tools import plot_nullclines_eq, plot_sim_results
from tvb_epilepsy.base.utils import initialize_logger, set_time_scales, calculate_projection, filter_data
from tvb_epilepsy.custom.read_write import write_h5_model, write_ts_epi, write_ts_seeg_epi
from tvb_epilepsy.tvb_api.epileptor_models import EpileptorDP

if DATA_MODE is TVB:
    from tvb_epilepsy.tvb_api.readers_tvb import TVBReader as Reader
else:
    from tvb_epilepsy.custom.readers_custom import CustomReader as Reader

if SIMULATION_MODE is TVB:
    from tvb_epilepsy.tvb_api.simulator_tvb import setup_simulation
else:
    from tvb_epilepsy.custom.simulator_custom import setup_simulation

if __name__ == "__main__":
    logger = initialize_logger(__name__)
    data_folder = '/WORK/Episense/trunk/demo-data/Head_TREC'

    reader = Reader()

    logger.info("Reading from: " + data_folder)
    head = reader.read_head(data_folder)

    x0_indices = [20]
    x0_values = numpy.random.normal(0.85, 0.02, (len(x0_indices),))

    hypothesis = DiseaseHypothesis("x0", head.connectivity, x0_values, x0_indices, [], [], [], "x0_Hypothesis")

    all_regions_one = numpy.ones((hypothesis.get_number_of_regions(),), dtype=numpy.float32)

    epileptor_model = EpileptorDP(Iext1=3.1 * all_regions_one, yc=all_regions_one,
                                  K=10 * all_regions_one / hypothesis.get_number_of_regions())

    equilibrum_service = EquilibrumComputationService(hypothesis, epileptor_model)

    model_configuration, lsa_hypothesis = equilibrum_service.configure_model_from_x0_hypothesis(None)

    write_h5_model(hypothesis.prepare_for_h5(), folder_name=data_folder, file_name=hypothesis.get_name() + ".h5")
    write_h5_model(lsa_hypothesis.prepare_for_h5(), folder_name=data_folder,
                   file_name=lsa_hypothesis.get_name() + ".h5")

    write_h5_model(model_configuration.prepare_for_h5(), folder_name=data_folder, file_name="Config.h5")

    # plot_hypothesis_equilibrium_and_lsa(lsa_hypothesis, model_configuration, figure_dir=data_folder)

    fs = 2 * 4096.0
    scale_time = 2.0
    time_length = 3000.0
    scale_fsavg = 2.0
    report_every_n_monitor_steps = 10.0
    (dt, fsAVG, sim_length, monitor_period, n_report_blocks) = set_time_scales(fs=fs, dt=None,
                                                                               time_length=time_length,
                                                                               scale_time=scale_time,
                                                                               scale_fsavg=scale_fsavg,
                                                                               report_every_n_monitor_steps=report_every_n_monitor_steps)
    model_name = "EpileptorDP"

    simulator_instance = setup_simulation(model_configuration, head.connectivity, dt, sim_length, monitor_period,
                                          model_name, scale_time=scale_time, noise_intensity=10 ** -8)

    simulator_instance.config_simulation()
    ttavg, tavg_data, status = simulator_instance.launch_simulation(n_report_blocks)

    if not status:
        warnings.warn("Simulation failed!")
    else:
        tavg_data = tavg_data[:, :, :, 0]

    vois = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'lfp']
    # vois custom
    # vois = ['x1', 'z', 'x2']

    sensorsSEEG = []
    projections = []
    for sensors, projection in head.sensorsSEEG.iteritems():
        if projection is None:
            continue
        else:
            projection = calculate_projection(sensors, head.connectivity)
            head.sensorsSEEG[sensors] = projection
            print projection.shape
            sensorsSEEG.append(sensors)
            projections.append(projection)

    hpf_flag = False
    hpf_low = max(16.0, 1000.0 / time_length)  # msec
    hpf_high = min(250.0, fsAVG)

    if status:

        model = simulator_instance.model

        logger.info("\nSimulated signal return shape: " + str(tavg_data.shape))
        logger.info("Time: " + str(scale_time * ttavg[0]) + " - " + str(scale_time * ttavg[-1]))
        logger.info("Values: " + str(tavg_data.min()) + " - " + str(tavg_data.max()))

        write_h5_model(simulator_instance.prepare_for_h5(), folder_name=data_folder, file_name=hypothesis.get_name() + "_sim_settings.h5")

        # Pack results into a dictionary, high pass filter, and compute SEEG
        res = dict()
        time = scale_time * numpy.array(ttavg, dtype='float32')
        dt = numpy.min(numpy.diff(time))
        for iv in range(len(vois)):
            res[vois[iv]] = numpy.array(tavg_data[:, iv, :], dtype='float32')

        if model._ui_name == "EpileptorDP2D":
            raw_data = numpy.dstack([res["x1"], res["z"], res["x1"]])
            lfp_data = res["x1"]
            for i in range(len(projections)):
                res['seeg' + str(i)] = numpy.dot(res['z'], projections[i].T)
        else:
            if model._ui_name == "CustomEpileptor":
                raw_data = numpy.dstack([res["x1"], res["z"], res["x2"]])
                lfp_data = res["x2"] - res["x1"]
            else:
                raw_data = numpy.dstack([res["x1"], res["z"], res["x2"]])
                lfp_data = res["lfp"]
            for i in range(len(projections)):
                res['seeg' + str(i)] = numpy.dot(res['lfp'], projections[i].T)
                if hpf_flag:
                    for i in range(res['seeg'].shape[0]):
                        res['seeg_hpf' + str(i)][:, i] = filter_data(res['seeg' + str(i)][:, i], hpf_low, hpf_high,
                                                                     fsAVG)

        write_ts_epi(raw_data, dt, lfp_data, path=os.path.join(FOLDER_RES, hypothesis.name + "_ep_ts.h5"))
        del raw_data, lfp_data

        for i in range(len(projections)):
            write_ts_seeg_epi(res['seeg' + str(i)], dt, path=os.path.join(FOLDER_RES, hypothesis.name + "_ep_ts.h5"))

        res['time'] = time

        del ttavg, tavg_data

        # Plot results
        plot_nullclines_eq(model_configuration, head.connectivity.region_labels,
                           special_idx=numpy.concatenate((lsa_hypothesis.get_x0_indices(),
                                                          lsa_hypothesis.get_propagation_indices())),
                           model=str(model.nvar) + "d", zmode=model.zmode,
                           figure_name="Nullclines and equilibria", save_flag=SAVE_FLAG,
                           show_flag=SHOW_FLAG, figure_dir=FOLDER_FIGURES)
        plot_sim_results(model, numpy.concatenate((lsa_hypothesis.get_x0_indices(),
                                                   lsa_hypothesis.get_propagation_indices())),
                         hypothesis.name, head, res, sensorsSEEG, hpf_flag)

        # Save results
        res['time_units'] = 'msec'
        savemat(os.path.join(FOLDER_RES, hypothesis.name + "_ts.mat"), res)

    else:
        warnings.warn("Simulation failed!")
