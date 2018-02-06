import os
import numpy as np
from tvb_epilepsy.base.constants.model_constants import K_DEF
from tvb_epilepsy.base.constants.configurations import DATA_CUSTOM, FOLDER_RES
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger
from tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.io.h5_writer import H5Writer
from tvb_epilepsy.plot.plotter import Plotter
from tvb_epilepsy.service.sensitivity_analysis_service import METHODS
from tvb_epilepsy.scripts.sensitivity_analysis_sripts import sensitivity_analysis_pse_from_hypothesis
from tvb_epilepsy.io.h5_reader import H5Reader as Reader

logger = initialize_logger(__name__)

if __name__ == "__main__":
    # -------------------------------Reading data-----------------------------------
    data_folder = os.path.join(DATA_CUSTOM, 'Head_TVB25')
    reader = Reader()
    writer = H5Writer()
    head = reader.read_head(data_folder)
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
    hyp_x0_E = DiseaseHypothesis(head.connectivity.number_of_regions,
                                 excitability_hypothesis={tuple(x0_indices): x0_values},
                                 epileptogenicity_hypothesis={tuple(e_indices): e_values},
                                 connectivity_hypothesis={})
    # Now running the sensitivity analysis:
    logger.info("running sensitivity analysis PSE LSA...")
    for m in METHODS:
        try:
            model_configuration_service, model_configuration, lsa_service, lsa_hypothesis, sa_results, pse_results = \
                sensitivity_analysis_pse_from_hypothesis(hyp_x0_E,
                                                         head.connectivity.normalized_weights,
                                                         head.connectivity.region_labels,
                                                         n_samples, method=m, param_range=0.1,
                                                         global_coupling=[{"indices": all_regions_indices,
                                                                           "low": 0.0, "high": 2 * K_DEF}],
                                                         healthy_regions_parameters=[
                                                             {"name": "x0_values", "indices": healthy_indices}],
                                                         logger=logger, save_services=True)
            Plotter().plot_lsa(lsa_hypothesis, model_configuration, lsa_service.weighted_eigenvector_sum,
                         lsa_service.eigen_vectors_number, region_labels=head.connectivity.region_labels,
                                 pse_results=pse_results, title=m + "_PSE_LSA_overview_" + lsa_hypothesis.name)
            # , show_flag=True, save_flag=False
            writer.write_dictionary(pse_results,
                                    os.path.join(FOLDER_RES, m + "_PSE_LSA_results_" + lsa_hypothesis.name + ".h5"))
            writer.write_dictionary(sa_results,
                                    os.path.join(FOLDER_RES, m + "_SA_LSA_results_" + lsa_hypothesis.name + ".h5"))
        except:
            logger.warning("Method " + m + " failed!")
