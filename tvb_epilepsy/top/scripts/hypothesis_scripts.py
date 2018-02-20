import os
from tvb_epilepsy.base.constants.config import Config
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger
from tvb_epilepsy.io.h5_writer import H5Writer
from tvb_epilepsy.plot.plotter import Plotter
from tvb_epilepsy.service.hypothesis_builder import HypothesisBuilder
from tvb_epilepsy.service.model_configuration_builder import ModelConfigurationBuilder
from tvb_epilepsy.service.lsa_service import LSAService
from tvb_epilepsy.io.tvb_data_reader import TVBReader
from tvb_epilepsy.io.h5_reader import H5Reader

logger = initialize_logger(__name__)


def start_lsa_run(hypothesis, model_connectivity, config=Config()):
    logger.info("creating model configuration...")
    model_configuration_builder = ModelConfigurationBuilder(hypothesis.number_of_regions)
    model_configuration = model_configuration_builder.build_model_from_hypothesis(hypothesis, model_connectivity)

    logger.info("running LSA...")
    lsa_service = LSAService(eigen_vectors_number_selection=config.calcul.EIGENVECTORS_NUMBER_SELECTION,
                             eigen_vectors_number=None, weighted_eigenvector_sum=config.calcul.WEIGHTED_EIGENVECTOR_SUM,
                             normalize_propagation_strength=False)
    lsa_hypothesis = lsa_service.run_lsa(hypothesis, model_configuration)

    return model_configuration_builder, model_configuration, lsa_service, lsa_hypothesis


def from_head_to_hypotheses(ep_name, config, plot_head=False):
    # -------------------------------Reading model_data-----------------------------------
    reader = TVBReader() if config.input.IS_TVB_MODE else H5Reader()
    logger.info("Reading from: " + config.input.HEAD)
    head = reader.read_head(config.input.HEAD)
    if plot_head:
        plotter = Plotter(config)
        plotter.plot_head(head)
    # --------------------------Hypothesis definition-----------------------------------
    # # Manual definition of hypothesis...:
    # x0_indices = [20]
    # x0_values = [0.9]
    # e_indices = [70]
    # e_values = [0.9]
    # disease_values = x0_values + e_values
    # disease_indices = x0_indices + e_indices
    # ...or reading a custom file:
    # FOLDER_RES = os.path.join(data_folder, ep_name)

    hypo_builder = HypothesisBuilder(config=config).\
        set_nr_of_regions(head.connectivity.number_of_regions).\
        set_sort_disease_values(True)

    # This is an example of Excitability Hypothesis:
    hyp_x0 = hypo_builder.build_hypothesis_from_file(ep_name)

    # This is an example of Epileptogenicity Hypothesis:
    hyp_E = hypo_builder.build_hypothesis_from_file(ep_name, hyp_x0.x0_indices)

    # This is an example of Mixed Hypothesis:
    x0_indices = [hyp_x0.x0_indices[-1]]
    x0_values = [hyp_x0.x0_values[-1]]
    e_indices = hyp_x0.x0_indices[0:-1].tolist()
    e_values = hyp_x0.x0_values[0:-1].tolist()
    hyp_x0_E = hypo_builder.build_hypothesis_from_manual_input(e_values, e_indices, x0_values, x0_indices)

    hypos = (hyp_x0, hyp_E, hyp_x0_E)
    return head, hypos


def from_hypothesis_to_model_config_lsa(hyp, head, eigen_vectors_number=None, weighted_eigenvector_sum=True,
                                        config=Config(), **kwargs):
    logger.info("\n\nRunning hypothesis: " + hyp.name)
    logger.info("\n\nCreating model configuration...")
    builder = ModelConfigurationBuilder(hyp.number_of_regions, **kwargs)
    if hyp.type == "Epileptogenicity":
        model_configuration = builder.build_model_from_E_hypothesis(hyp, head.connectivity.normalized_weights)
    else:
        model_configuration = builder.build_model_from_hypothesis(hyp, head.connectivity.normalized_weights)
    writer = H5Writer()
    if config.figures.SAVE_FLAG:
        path_mc = os.path.join(config.out.FOLDER_RES, hyp.name + "_ModelConfig.h5")
        writer.write_model_configuration(model_configuration, path_mc)
    # Plot nullclines and equilibria of model configuration
    plotter = Plotter(config)
    if config.figures.SHOW_FLAG:
        plotter.plot_state_space(model_configuration, head.connectivity.region_labels,
                                 special_idx=hyp.get_regions_disease(), model="6d", zmode="lin",
                                 figure_name=hyp.name + "_StateSpace")

    logger.info("\n\nRunning LSA...")
    lsa_service = LSAService(eigen_vectors_number=eigen_vectors_number,
                             weighted_eigenvector_sum=weighted_eigenvector_sum)
    lsa_hypothesis = lsa_service.run_lsa(hyp, model_configuration)
    if config.figures.SAVE_FLAG:
        writer.write_hypothesis(lsa_hypothesis, os.path.join(config.out.FOLDER_RES, lsa_hypothesis.name + "_LSA.h5"))
    if config.figures.SHOW_FLAG:
        plotter.plot_lsa(lsa_hypothesis, model_configuration, lsa_service.weighted_eigenvector_sum,
                         lsa_service.eigen_vectors_number, head.connectivity.region_labels, None)
    return model_configuration, lsa_hypothesis, builder, lsa_service
