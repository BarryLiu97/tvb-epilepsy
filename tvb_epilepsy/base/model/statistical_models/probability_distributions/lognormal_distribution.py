
import numpy as np
import scipy.stats as ss

from tvb_epilepsy.base.model.statistical_models.probability_distributions.continuous_probability_distribution  \
                                                                                import ContinuousProbabilityDistribution


class LognormalDistribution(ContinuousProbabilityDistribution):

    def __init__(self, mu=0.0, sigma=1.0):
        self.name = "lognormal"
        self.scipy_name = "lognorm"
        self.params = {"mu": np.float(mu), "sigma": np.float(sigma)}
        self.constraint_string = "sigma > 0"
        self.__update_params__(**self.params)

    def update_params(self, **params):
        self.__update_params__(**self.params)

    def constraint(self):
        return self.params["sigma"] > 0.0

    def scipy(self, loc=0.0, scale=1.0):
        return getattr(ss, self.scipy_name)(self.params["sigma"], loc=loc, scale=np.exp(self.params["mu"]))

    def calc_mu_manual(self):
        return np.exp(self.params["mu"] + self.params["sigma"] ** 2 / 2.0)

    def calc_median_manual(self):
        return np.exp(self.params["mu"])

    def calc_mode_manual(self):
        return np.exp(self.params["mu"] - self.params["sigma"] ** 2)

    def calc_var_manual(self):
        sigma2 = self.params["sigma"] ** 2
        return (np.exp(sigma2) - 1.0) * np.exp(2.0 * self.params["mu"] + self.params["sigma"] ** 2)

    def calc_std_manual(self):
        return np.sqrt(self.calc_var_manual())

    def calc_skew_manual(self):
        sigma2exp = np.exp(self.params["sigma"] ** 2)
        return (sigma2exp + 2.0) * np.sqrt(sigma2exp - 1.0)

    def calc_exkurt_manual(self):
        sigma2 = self.params["sigma"] ** 2
        return np.exp(4.0 * sigma2) + 2.0 * np.exp(3.0 * sigma2) + 3.0 * np.exp(2.0 * sigma2) - 6.0
