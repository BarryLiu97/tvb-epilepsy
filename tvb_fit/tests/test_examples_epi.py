import os

from tvb_fit.tests.base import BaseTest
from tvb_fit.tvb_epilepsy.top.examples.vep_study import vep_study
from tvb_fit.tvb_epilepsy.top.examples.main_simulation import main_simulation
from tvb_fit.tvb_epilepsy.top.examples.main_pse import main_pse
from tvb_fit.tvb_epilepsy.top.examples.main_sensitivity_analysis import main_sensitivity_analysis
from tvb_fit.tvb_epilepsy.top.examples.main_sampling_service import main_sampling_service


class TestExamples(BaseTest):

    def test_main_sensitivity_analysis(self):
        main_sensitivity_analysis(self.config)

    def test_main_pse(self):
        main_pse(self.config)

    def test_main_sampling_service(self):
        main_sampling_service(self.config)

    def test_main_simulation(self):
        main_simulation(self.config)

    def test_vep_study(self):
        vep_study()

    # def test_main_fitting_default(self):
    #     main_fit_sim_hyplsa()

    @classmethod
    def teardown_class(cls):
        head_dir = os.path.join(cls.config.out.FOLDER_RES, "Head")
        if os.path.exists(head_dir):
            for dir_file in os.listdir(head_dir):
                os.remove(os.path.join(os.path.abspath(head_dir), dir_file))
            os.rmdir(head_dir)
        BaseTest.teardown_class()
