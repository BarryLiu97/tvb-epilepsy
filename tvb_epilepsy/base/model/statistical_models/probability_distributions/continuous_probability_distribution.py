
from abc import ABCMeta

import numpy as np

from tvb_epilepsy.base.model.statistical_models.probability_distributions.probability_distribution \
                                                                                          import ProbabilityDistribution


class ContinuousProbabilityDistribution(ProbabilityDistribution):

    __metaclass__ = ABCMeta

    def scipy_pdf(self, x=None, q=[0.01, 0.99], loc=0.0, scale=1.0):
        if x is None:
            x = np.linspace(np.min(self.scipy(loc, scale).ppf(q[0])),
                            np.min(self.scipy(loc, scale).ppf(q[1])), 101)
        return self.scipy(loc, scale).pdf(x), x
