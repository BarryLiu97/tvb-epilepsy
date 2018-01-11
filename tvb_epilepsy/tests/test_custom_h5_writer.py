import os
import numpy

from tvb_epilepsy.base.model.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.base.model.model_configuration import ModelConfiguration
from tvb_epilepsy.base.model.vep.connectivity import Connectivity
from tvb_epilepsy.base.model.vep.head import Head
from tvb_epilepsy.base.model.vep.sensors import Sensors
from tvb_epilepsy.base.model.vep.surface import Surface
from tvb_epilepsy.io.h5.writer_custom import CustomH5Writer
from tvb_epilepsy.service.model_configuration_service import ModelConfigurationService
from tvb_epilepsy.tests.base import remove_temporary_test_files, get_temporary_folder


class TestCustomH5writer(object):
    writer = CustomH5Writer()

    dummy_connectivity = Connectivity("", numpy.array([[1.0, 2.0, 3.0], [2.0, 3.0, 1.0], [3.0, 2.0, 1.0]]),
                                      numpy.array([[4, 5, 6], [5, 6, 4], [6, 4, 5]]), labels=["a", "b", "c"],
                                      centres=numpy.array([1.0, 2.0, 3.0]))
    dummy_surface = Surface(numpy.array([[1, 2, 3], [2, 3, 1], [3, 1, 2]]), numpy.array([[0, 1, 2]]))
    dummy_sensors = Sensors(numpy.array(["sens1", "sens2"]), numpy.array([[0, 0, 0], [0, 1, 0]]),
                            gain_matrix=numpy.array([[1, 2, 3], [2, 3, 4]]))

    def _prepare_dummy_head(self):
        return Head(self.dummy_connectivity, self.dummy_surface, sensorsSEEG=[self.dummy_sensors])

    def test_write_connectivity(self):
        test_file = os.path.join(get_temporary_folder(), "TestConnectivity.h5")

        assert not os.path.exists(test_file)

        self.writer.write_connectivity(self.dummy_connectivity, test_file)

        assert os.path.exists(test_file)

    def test_write_connectivity_with_normalized_weigths(self):
        test_file = os.path.join(get_temporary_folder(), "TestConnectivityNorm.h5")

        assert not os.path.exists(test_file)

        connectivity = self.dummy_connectivity
        connectivity.normalized_weights = numpy.array([1, 2, 3])
        self.writer.write_connectivity(connectivity, test_file)

        assert os.path.exists(test_file)

    def test_write_surface(self):
        test_file = os.path.join(get_temporary_folder(), "TestSurface.h5")

        assert not os.path.exists(test_file)

        self.writer.write_surface(self.dummy_surface, test_file)

        assert os.path.exists(test_file)

    def test_write_sensors(self):
        test_file = os.path.join(get_temporary_folder(), "TestSensors.h5")

        assert not os.path.exists(test_file)

        self.writer.write_sensors(self.dummy_sensors, test_file)

        assert os.path.exists(test_file)

    def test_write_head(self):
        test_folder = os.path.join(get_temporary_folder(), "test_head")

        assert not os.path.exists(test_folder)

        head = self._prepare_dummy_head()
        self.writer.write_head(head, test_folder)

        assert os.path.exists(test_folder)
        assert len(os.listdir(test_folder)) >= 3

    def test_write_hypothesis(self):
        test_file = os.path.join(get_temporary_folder(), "TestHypothesis.h5")
        dummy_hypothesis = DiseaseHypothesis(3, excitability_hypothesis={tuple([0]): numpy.array([0.6])},
                                             epileptogenicity_hypothesis={})

        assert not os.path.exists(test_file)

        self.writer.write_hypothesis(dummy_hypothesis, test_file)

        assert os.path.exists(test_file)

    def test_write_model_configuration(self):
        test_file = os.path.join(get_temporary_folder(), "TestModelConfiguration.h5")
        dummy_mc = ModelConfiguration(x1EQ=numpy.array([2.0, 3.0, 1.0]), zmode=None,
                                      zEQ=numpy.array([3.0, 2.0, 1.0]), Ceq=numpy.array([1.0, 2.0, 3.0]),
                                      model_connectivity=self.dummy_connectivity.normalized_weights)

        assert not os.path.exists(test_file)

        self.writer.write_model_configuration(dummy_mc, test_file)

        assert os.path.exists(test_file)

    def test_write_model_configuration_service(self):
        test_file = os.path.join(get_temporary_folder(), "TestModelConfigurationService.h5")
        dummy_mc_service = ModelConfigurationService(3)

        assert not os.path.exists(test_file)

        self.writer.write_model_configuration(dummy_mc_service, test_file)

        assert os.path.exists(test_file)

    @classmethod
    def teardown_class(cls):
        remove_temporary_test_files()
