# coding=utf-8
"""
Service to do LSA computation.
"""
import numpy
from tvb.basic.logger.builder import get_logger

from tvb_epilepsy.base.calculations import calc_fz_jac_square_taylor
from tvb_epilepsy.base.constants import EIGENVECTORS_NUMBER_SELECTION
from tvb_epilepsy.base.utils import curve_elbow_point
from tvb_epilepsy.base.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.base.model_configuration import ModelConfiguration

LOG = get_logger(__name__)

# TODO: it might be useful to store eigenvalues and eigenvectors, as well as the parameters of the computation, such as
# eigen_vectors_number and LSAService in a h5 file

# NOTES: currently the disease_hypothesis (after it has configured a model) is needed only for the connectivity weights.
# In the future this could be part of the model configuration. Disease hypothesis should hold only specific hypotheses,
# on the connectivity matrix (changes, lesions, etc)


class LSAService(object):

    def __init__(self, eigen_vectors_number_selection=EIGENVECTORS_NUMBER_SELECTION):
        self.eigen_vectors_number_selection = eigen_vectors_number_selection
        self.eigen_values = []
        self.eigen_vectors = []

    def get_curve_elbow_point(self, values_array):
        return curve_elbow_point(values_array)

    def _ensure_eigen_vectors_number(self, eigen_vectors_number, eigen_values, e_values, x0_values):
        if eigen_vectors_number is None:
            if self.eigen_vectors_number_selection is "auto_eigenvals":
                eigen_vectors_number = self.get_curve_elbow_point(numpy.abs(eigen_values)) + 1

            elif self.eigen_vectors_number_selection is "auto_epileptogenicity":
                eigen_vectors_number = self.get_curve_elbow_point(e_values) + 1

            elif self.eigen_vectors_number_selection is "auto_x0":
                eigen_vectors_number = self.get_curve_elbow_point(x0_values) + 1

        return eigen_vectors_number

    def _compute_jacobian(self, model_configuration, weights):
        fz_jacobian = calc_fz_jac_square_taylor(model_configuration.zEQ, model_configuration.yc,
                                                model_configuration.Iext1, model_configuration.K, weights,
                                                model_configuration.a, model_configuration.b)

        if numpy.any([numpy.any(numpy.isnan(fz_jacobian.flatten())), numpy.any(numpy.isinf(fz_jacobian.flatten()))]):
            raise ValueError("nan or inf values in dfz")

        return fz_jacobian

    def run_lsa(self, disease_hypothesis, model_configuration, eigen_vectors_number=None):

        jacobian = self._compute_jacobian(model_configuration, disease_hypothesis.get_weights())

        # Perform eigenvalue decomposition
        eigen_values, eigen_vectors = numpy.linalg.eig(jacobian)

        sorted_indices = numpy.argsort(eigen_values, kind='mergesort')
        self.eigen_values = eigen_values[sorted_indices]
        self.eigen_vectors = eigen_vectors[:, sorted_indices]

        # Calculate the propagation strength index by summing all eigenvectors
        propagation_strength_all = numpy.abs(numpy.sum(self.eigen_vectors, axis=1))
        propagation_strength_all /= numpy.max(propagation_strength_all)

        eigen_vectors_number = self._ensure_eigen_vectors_number(eigen_vectors_number, self.eigen_values,
                                                                 model_configuration.E_values,
                                                                 model_configuration.x0_values)

        if eigen_vectors_number == disease_hypothesis.get_number_of_regions():
            lsa_propagation_strength = propagation_strength_all

        else:
            sorted_indices = max(eigen_vectors_number, 1)
            # Calculate the propagation strength index by summing the first n eigenvectors (minimum 1)
            lsa_propagation_strength = numpy.abs(numpy.sum(self.eigen_vectors[:, :sorted_indices], axis=1))
            lsa_propagation_strength /= numpy.max(lsa_propagation_strength)


        propagation_strength_elbow = self.get_curve_elbow_point(lsa_propagation_strength)
        propagation_indices = lsa_propagation_strength.argsort()[-propagation_strength_elbow:]

        return DiseaseHypothesis(disease_hypothesis.connectivity, disease_hypothesis.disease_values,
                                 disease_hypothesis.x0_indices, disease_hypothesis.e_indices, propagation_indices,
                                 lsa_propagation_strength, disease_hypothesis.type,
                                 "LSA_" + disease_hypothesis.name)
