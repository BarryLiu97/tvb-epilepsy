# coding=utf-8

import os
import numpy as np

from tvb_fit.service.sensitivity_analysis_service import METHODS
from tvb_fit.tvb_epilepsy.base.constants.model_constants import K_UNSCALED_DEF
from tvb_fit.tvb_epilepsy.base.constants.config import Config
from tvb_fit.tvb_epilepsy.io.h5_writer import H5Writer
from tvb_fit.tvb_epilepsy.plot.plotter import Plotter
from tvb_fit.tvb_epilepsy.service.hypothesis_builder import HypothesisBuilder
from tvb_fit.tvb_epilepsy.top.scripts.sensitivity_analysis_sripts import sensitivity_analysis_pse_from_hypothesis
from tvb_fit.tvb_epilepsy.io.h5_reader import H5Reader as Reader

from tvb_scripts.utils.log_error_utils import initialize_logger


logger = initialize_logger(__name__)


def main_sensitivity_analysis(config=Config()):
    # -------------------------------Reading data-----------------------------------
    reader = Reader()
    writer = H5Writer()
    head = reader.read_head(config.input.HEAD)
    # --------------------------Hypothesis definition-----------------------------------
    n_samples = 100
    # Manual definition of hypothesis...:
    x0_indices = [20]
    x0_values = [0.9]
    e_indices = [70]
    e_values = [0.9]
    disease_indices = x0_indices + e_indices
    n_disease = len(disease_indices)
    n_x0 = len(x0_indices)
    n_e = len(e_indices)
    all_regions_indices = np.array(range(head.connectivity.number_of_regions))
    healthy_indices = np.delete(all_regions_indices, disease_indices).tolist()
    n_healthy = len(healthy_indices)
    # This is an example of x0_values mixed Excitability and Epileptogenicity Hypothesis:
    hyp_x0_E = HypothesisBuilder(head.connectivity.number_of_regions).set_x0_hypothesis(x0_indices,
                                                                                        x0_values).set_e_hypothesis(
        e_indices, e_values).build_hypothesis()
    # Now running the sensitivity analysis:
    logger.info("running sensitivity analysis PSE LSA...")
    for m in METHODS:
        try:
            model_configuration_builder, model_configuration, lsa_service, lsa_hypothesis, sa_results, pse_results = \
                sensitivity_analysis_pse_from_hypothesis(hyp_x0_E,
                                                         head.connectivity.normalized_weights,
                                                         head.connectivity.region_labels,
                                                         n_samples, method=m, param_range=0.1,
                                                         global_coupling=[{"indices": all_regions_indices,
                                                                           "low": 0.0, "high": 2 * K_UNSCALED_DEF}],
                                                         healthy_regions_parameters=[
                                                             {"name": "x0_values", "indices": healthy_indices}],
                                                         config=config, save_services=True)
            Plotter(config).plot_lsa(lsa_hypothesis, model_configuration, lsa_service.weighted_eigenvector_sum,
                                     lsa_service.eigen_vectors_number, region_labels=head.connectivity.region_labels,
                                     pse_results=pse_results, title=m + "_PSE_LSA_overview_" + lsa_hypothesis.name,
                                     lsa_service=lsa_service)
            # , show_flag=True, save_flag=False
            result_file = os.path.join(config.out.FOLDER_RES, m + "_PSE_LSA_results_" + lsa_hypothesis.name + ".h5")
            writer.write_dictionary(pse_results, result_file)
            result_file = os.path.join(config.out.FOLDER_RES, m + "_SA_LSA_results_" + lsa_hypothesis.name + ".h5")
            writer.write_dictionary(sa_results, result_file)
        except:
            logger.warning("Method " + m + " failed!")


if __name__ == "__main__":
    main_sensitivity_analysis()
