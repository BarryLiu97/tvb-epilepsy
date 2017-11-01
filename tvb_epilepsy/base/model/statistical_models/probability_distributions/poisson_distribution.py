
import numpy as np
import scipy.stats as ss

from tvb_epilepsy.base.utils.log_error_utils import warning, raise_value_error
from tvb_epilepsy.base.utils.data_structures_utils import isequal_string
from tvb_epilepsy.base.model.statistical_models.probability_distributions.discrete_probability_distribution  \
                                                                                  import DiscreteProbabilityDistribution


class PoissoniDistribution(DiscreteProbabilityDistribution):

    def __init__(self, lamda=0.5):
        self.name = "poisson"
        self.scipy_name = "poisson"
        self.params = {"lamda": np.float(lamda)}
        self.n_params = len(self.params)
        self.constraint_string = "0 < lamda < 1"
        if not(self.constraint()):
            raise_value_error("Constraint for " + self.name + " distribution " + self.constraint_string +
                              "\nwith parameters " + str(self.params) + " is not satisfied!")
        self.mu = self.calc_mu()
        self.median = None
        self.mode = self.calc_mode()
        self.var = self.calc_var()
        self.std = self.calc_std()
        self.skew = self.calc_skew()
        self.exkurt = self.calc_exkurt()

    def constraint(self):
        return self.params["lamda"] > 0.0

    def scipy(self, loc=0.0, scale=1.0):
        return getattr(ss, self.scipy_name)(self.params["lamda"], loc=loc, scale=scale)

    def calc_mu(self, use="scipy"):
        if isequal_string(use, "scipy"):
            return self.scipy().stats(moments="m")
        else:
            return self.params["lamda"]

    def calc_median(self, use="scipy"):
        if isequal_string(use, "scipy"):
            return self.scipy().median()
        else:
            warning("Approximate calculation for median of poisson distribution!")
            return np.int(np.round(self.params["lamda"] + 1.0/3 - 0.02 / self.params["lamda"]))

    def calc_mode(self):
        if self.params["p"] < 0.5:
            return 0.0
        elif self.params["p"] > 0.5:
            return 1.0
        else:
            warning("The mode of poisson distribution for p=0.5 consists of two values (lamda-1 and lamda)!")
            lamda = np.int(np.round(self.params["lamda"]))
            return lamda - 1, lamda

    def calc_var(self, use="scipy"):
        if isequal_string(use, "scipy"):
            return self.scipy().var()
        else:
            return self.params["lamda"]

    def calc_std(self, use="scipy"):
        if isequal_string(use, "scipy"):
            return self.scipy().std()
        else:
            return np.sqrt(self.calc_var(use=use))

    def calc_skew(self, use="scipy"):
        if isequal_string(use, "scipy"):
            return self.scipy().stats(moments="s")
        else:
            return 1.0 / self.calc_std(use=use)

    def calc_exkurt(self, use="scipy"):
        if isequal_string(use, "scipy"):
            return self.scipy().stats(moments="k")
        else:
            var = self.calc_var(use=use)
            return 1.0 / self.params["lamda"]
