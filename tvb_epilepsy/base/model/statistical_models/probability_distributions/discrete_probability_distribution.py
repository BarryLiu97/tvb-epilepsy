
from abc import ABCMeta, abstractmethod

import numpy as np

from tvb_epilepsy.base.model.statistical_models.probability_distributions.probability_distribution \
                                                                                          import ProbabilityDistribution


class DiscreteProbabilityDistribution(ProbabilityDistribution):

    __metaclass__ = ABCMeta

    def scipy_pdf(self, x=None, q=[0.01, 0.99], loc=0.0, scale=1.0):
        if x is None:
            x = np.linspace(np.min(self.scipy(loc, scale).ppf(q[0])),
                            np.min(self.scipy(loc, scale).ppf(q[1])), 101)
        return self.scipy(loc, scale).pmf(x), x

    @abstractmethod
    def constraint(self):
        pass

    @abstractmethod
    def scipy(self, loc=0.0, scale=1.0):
        pass

    @abstractmethod
    def calc_mean(self, use="scipy"):
        pass

    @abstractmethod
    def calc_median(self, use="scipy"):
        pass

    @abstractmethod
    def calc_mode(self):
        pass

    @abstractmethod
    def calc_var(self, use="scipy"):
        pass

    @abstractmethod
    def calc_std(self, use="scipy"):
        pass

    @abstractmethod
    def calc_skew(self, use="scipy"):
        pass

    @abstractmethod
    def calc_kurt(self, use="scipy"):
        pass