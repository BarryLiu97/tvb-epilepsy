import os
import h5py
from collections import OrderedDict
from tvb_fit.base.utils.log_error_utils import initialize_logger, raise_value_error
from tvb_fit.base.utils.data_structures_utils import ensure_list
from tvb_fit.base.model.parameter import Parameter
from tvb_fit.tvb_epilepsy.base.model.epileptor_probabilistic_models import EpileptorProbabilisticModels, \
    EpiProbabilisticModel, ODEEpiProbabilisticModel, SDEEpiProbabilisticModel
from tvb_fit.tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis
from tvb_fit.tvb_epilepsy.base.model.simulation_settings import SimulationSettings
from tvb_fit.tvb_epilepsy.base.model.model_configuration import ModelConfiguration
from tvb_fit.service.probabilistic_parameter_builder import generate_probabilistic_parameter
from tvb_fit.service.probabilistic_params_factory import generate_negative_lognormal_parameter
from tvb_fit.io.h5_writer import H5Writer
from tvb_fit.io.h5_reader import H5Reader as H5ReaderBase, H5GroupHandlers

H5_TYPE_ATTRIBUTE = H5Writer().H5_TYPE_ATTRIBUTE
H5_SUBTYPE_ATTRIBUTE = H5Writer().H5_SUBTYPE_ATTRIBUTE
H5_TYPES_ATTRUBUTES = [H5_TYPE_ATTRIBUTE, H5_SUBTYPE_ATTRIBUTE]


class H5Reader(H5ReaderBase):
    logger = initialize_logger(__name__)

    def read_epileptogenicity(self, root_folder, name="ep"):
        """
        :param
            root_folder: Path towards a valid custom Epileptogenicity H5 file
            name: the name of the hypothesis
        :return: Timeseries in a numpy array
        """
        path = os.path.join(root_folder, name, name + ".h5")
        self.logger.info("Starting to read Epileptogenicity from: %s" % path)
        h5_file = h5py.File(path, 'r', libver='latest')

        values = h5_file['/values'][()]

        h5_file.close()
        self.logger.info("Successfully read epileptogenicity values!")  #: %s" % values)

        return values

    def read_hypothesis(self, path, simplify=True):
        """
        :param path: Path towards a Hypothesis H5 file
        :return: DiseaseHypothesis object
        """
        self.logger.info("Starting to read Hypothesis from: %s" % path)
        h5_file = h5py.File(path, 'r', libver='latest')

        if h5_file.attrs["EPI_Subtype"] != "DiseaseHypothesis":
            self.logger.warning("This file does not seem to holds a DiseaseHypothesis!")

        hypothesis = DiseaseHypothesis()
        for dataset in h5_file.keys():
            hypothesis.set_attribute(dataset, h5_file["/" + dataset][()])

        for attr in h5_file.attrs.keys():
            if attr in ["x0_indices", "e_indices", "w_indices"]:
                hypothesis.set_attribute(attr, h5_file.attrs[attr].tolist())
            else:
                hypothesis.set_attribute(attr, h5_file.attrs[attr])

        h5_file.close()
        if simplify:
            hypothesis.simplify_hypothesis_from_h5()

        return hypothesis

    def read_model_configuration_builder(self, path):
        """
        :param path: Path towards a ModelConfigurationService H5 file
        :return: ModelConfigurationService object
        """
        self.logger.info("Starting to read ModelConfigurationService from: %s" % path)
        h5_file = h5py.File(path, 'r', libver='latest')

        from tvb_fit.tvb_epilepsy.service.model_configuration_builder import ModelConfigurationBuilder
        mc_service = ModelConfigurationBuilder()

        for dataset in h5_file.keys():
            mc_service.set_attribute(dataset, h5_file["/" + dataset][()])

        for attr in h5_file.attrs.keys():
            mc_service.set_attribute(attr, h5_file.attrs[attr])

        h5_file.close()
        return mc_service

    def read_model_configuration(self, path):
        """
        :param path: Path towards a ModelConfiguration H5 file
        :return: ModelConfiguration object
        """
        self.logger.info("Starting to read ModelConfiguration from: %s" % path)
        h5_file = h5py.File(path, 'r', libver='latest')

        if h5_file.attrs["EPI_Subtype"] != "ModelConfiguration":
            self.logger.warning("This file does not seem to hold a ModelConfiguration")

        model_configuration = ModelConfiguration()
        for dataset in h5_file.keys():
            model_configuration.set_attribute(dataset, h5_file["/" + dataset][()])

        for attr in h5_file.attrs.keys():
            model_configuration.set_attribute(attr, h5_file.attrs[attr])

        h5_file.close()
        return model_configuration

    def read_lsa_service(self, path):
        """
        :param path: Path towards a LSAService H5 file
        :return: LSAService object
        """
        self.logger.info("Starting to read LSAService from: %s" % path)
        h5_file = h5py.File(path, 'r', libver='latest')
        from tvb_fit.tvb_epilepsy.service.lsa_service import LSAService
        lsa_service = LSAService()

        for dataset in h5_file.keys():
            lsa_service.set_attribute(dataset, h5_file["/" + dataset][()])

        for attr in h5_file.attrs.keys():
            lsa_service.set_attribute(attr, h5_file.attrs[attr])

        h5_file.close()
        return lsa_service

    def read_simulation_settings(self, path):
        """
        :param path: Path towards a SimulationSettings H5 file
        :return: SimulationSettings
        """
        self.logger.info("Starting to read SimulationSettings from: %s" % path)
        h5_file = h5py.File(path, 'r', libver='latest')

        sim_settings = SimulationSettings()
        for dataset in h5_file.keys():
            sim_settings.set_attribute(dataset, h5_file["/" + dataset][()])

        for attr in h5_file.attrs.keys():
            sim_settings.set_attribute(attr, h5_file.attrs[attr])

        h5_file.close()
        return sim_settings

    def read_model_inversion_service(self, path):
        """
                :param path: Path towards a ModelConfigurationService H5 file
                :return: ModelInversionService object
                """
        # TODO: add a specialized reader function
        model_inversion_service = H5Reader().read_dictionary(path, "OrderedDictDot")
        if model_inversion_service.dict.get("signals_inds", None) is not None:
            model_inversion_service.dict["signals_inds"] = model_inversion_service.dict["signals_inds"].tolist()
        return model_inversion_service

    def read_probabilistic_model(self, path):
        h5_file = h5py.File(path, 'r', libver='latest')
        epi_subtype = h5_file.attrs[H5_SUBTYPE_ATTRIBUTE]
        probabilistic_model = None

        if epi_subtype == EpiProbabilisticModel.__class__:
            probabilistic_model = EpiProbabilisticModel()
        if epi_subtype == ODEEpiProbabilisticModel.__class__:
            probabilistic_model = ODEEpiProbabilisticModel()
        if epi_subtype == SDEEpiProbabilisticModel.__class__:
            probabilistic_model = SDEEpiProbabilisticModel()

        if probabilistic_model is None:
            raise_value_error(epi_subtype +
                              "does not correspond to one of the available epileptor probabilistic models!:\n" +
                              str(EpileptorProbabilisticModels))

        for attr in h5_file.attrs.keys():
            if attr not in H5_TYPES_ATTRUBUTES:
                probabilistic_model.__setattr__(attr, h5_file.attrs[attr])

        for key, value in h5_file.iteritems():
            if isinstance(value, h5py.Dataset):
                probabilistic_model.__setattr__(key, value[()])
            if isinstance(value, h5py.Group):
                if key == "model_config" and value.attrs[H5_SUBTYPE_ATTRIBUTE] == ModelConfiguration.__name__:
                    model_config = ModelConfiguration()

                    for mc_dataset in value.keys():
                        model_config.set_attribute(mc_dataset, value[mc_dataset][()])

                    for mc_attr in value.attrs.keys():
                        if mc_attr not in H5_TYPES_ATTRUBUTES:
                            model_config.__setattr__(mc_attr, value.attrs[mc_attr])

                    probabilistic_model.__setattr__(key, model_config)

                h5_group_handler = H5GroupHandlers()

                if key == "parameters":  # and value.attrs[epi_subtype_key] == OrderedDict.__name__:
                    parameters = h5_group_handler.handle_group_parameters(value)
                    probabilistic_model.__setattr__(key, parameters)

                if key == "ground_truth":
                    h5_group_handler.handle_group_ground_truth(value, probabilistic_model)

                if key == "active_regions":
                    probabilistic_model.active_regions = ensure_list(value)

        h5_file.close()
        return probabilistic_model