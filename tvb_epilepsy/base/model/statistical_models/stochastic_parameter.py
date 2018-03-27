from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import numpy as np
from tvb_epilepsy.base.constants.config import CalculusConfig
from tvb_epilepsy.base.utils.log_error_utils import raise_value_error
from tvb_epilepsy.base.utils.data_structures_utils import formal_repr, sort_dict, make_float
from tvb_epilepsy.base.utils.data_structures_utils import get_val_key_for_first_keymatch_in_dict
from tvb_epilepsy.base.model.parameter import Parameter
from tvb_epilepsy.base.computations.probability_distributions.probability_distribution import ProbabilityDistribution


class StochasticParameterBase(Parameter, ProbabilityDistribution):
    __metaclass__ = ABCMeta

    def __init__(self, name="Parameter", low=CalculusConfig.MIN_SINGLE_VALUE, high=CalculusConfig.MAX_SINGLE_VALUE,
                 loc=0.0, scale=1.0, p_shape=()):
        Parameter.__init__(self, name, low, high, p_shape)
        self.loc = loc
        self.scale = scale

    def __str__(self):
        return Parameter.__str__(self) + "\n" \
               + "\n".join(ProbabilityDistribution.__str__(self).splitlines()[1:])

    def calc_mean(self, use="scipy"):
        return self._calc_mean(self.loc, self.scale, use)

    def calc_median(self, use="scipy"):
        return self._calc_median(self.loc, self.scale, use)

    def calc_mode(self):
        return self._calc_mode(self.loc, self.scale)

    def calc_std(self, use="scipy"):
        return self._calc_std(self.loc, self.scale, use)

    def calc_var(self, use="scipy"):
        return self._calc_var(self.loc, self.scale, use)

    def calc_skew(self, use="scipy"):
        return self._calc_skew(self.loc, self.scale, use)

    def calc_kurt(self, use="scipy"):
        return self._calc_kurt(self.loc, self.scale, use)

    def scipy(self):
        return self._scipy(self.loc, self.scale)

    def scipy_method(self, method, *args, **kwargs):
        return self._scipy_method(method, self.loc, self.scale, *args, **kwargs)

    def numpy(self):
        return self._numpy(self.loc, self.scale)

    def _update_params(self, use="scipy", **params):
        self.loc = make_float(params.pop("loc", self.loc))
        self.scale = make_float(params.pop("scale", self.scale))
        self.update_params(self.loc, self.scale, use=use, **params)
        return self

    def _confirm_support(self):
        p_star = (self.low - self.loc) / self.scale
        p_star_cdf = self.scipy().cdf(p_star)
        if np.any(p_star_cdf + np.finfo(np.float).eps <= 0.0):  #
            raise_value_error("Lower limit of " + self.name + " base distribution outside support!: " +
                              "\n(self.low-self.loc)/self.scale) = " + str(p_star) +
                              "\ncdf(self.low-self.loc)/self.scale) = " + str(p_star_cdf))
        p_star = (self.high - self.loc) / self.scale
        p_star_cdf = self.scipy().cdf(p_star)
        if np.any(p_star_cdf - np.finfo(np.float).eps) >= 1.0:
            self.logger.warning("Upper limit of base " + self.name + "  distribution outside support!: " +
                                "\n(self.high-self.loc)/self.scale) = " + str(p_star) +
                                "\ncdf(self.high-self.loc)/self.scale) = " + str(p_star_cdf))

    def update_loc_scale(self, use="scipy", **target_stats):
        param_m = self._calc_mean(use=use)
        target_m = self._calc_mean(use=use)
        param_s = self._calc_std(use=use)
        target_s = self._calc_std(use=use)
        if len(target_stats) > 0:
            m_fun = lambda scale: self._calc_mean(scale=scale, use=use)
            m, pkey = get_val_key_for_first_keymatch_in_dict(self.name,
                                                             ["def", "median", "med", "mode", "mod", "mean", "mu", "m"],
                                                             **target_stats)
            if m is not None:
                target_m = m
                if pkey in ["median", "med"]:
                    m_fun = lambda scale: self._calc_median(scale=scale, use=use)
                elif pkey in ["mode", "mod"]:
                    m_fun = lambda scale: self._calc_mode(scale=scale)
            s, pkey = get_val_key_for_first_keymatch_in_dict(self.name, ["var", "v", "std", "sig", "sigma", "s"],
                                                             **target_stats)
            if s is not None:
                target_s = s
                if pkey in ["var", "v"]:
                    target_s = np.sqrt(target_s)
        if np.any(param_m != target_m) or np.any(param_s != target_s):
            self.scale = target_s / param_s
            temp_m = m_fun(scale=self.scale)
            self.loc = target_m - temp_m
            self._confirm_support()
            self._update_params(use=use)
        return self

# TODO: this should move to examples
# if __name__ == "__main__":
#     sp = generate_stochastic_parameter("test", probability_distribution="gamma", optimize=False, shape=1.0, scale=2.0)
#     initialize_logger(__name__).info(sp)

TransformedStochasticParameterBaseAttributes = ["name", "type", "low", "high", "mean", "median", "mode",
                                                "var", "std", "skew", "kurt", "star"]

TransformedStochasticParameterBaseStarAttributes = ["star_low", "star_high", "star_mean", "star_median", "star_mode",
                                                    "star_var", "star_std", "star_skew", "star_kurt"]

class TransformedStochasticParameterBase(object):
    __metaclass__ = ABCMeta

    name = ""
    type = ""
    star = None

    def __init__(self, name, type, star_parameter):
        self.name = name.split("_star")[0]
        self.type = type
        self.star = star_parameter
        self.star.name = self.star.name.split("_star")[0] + "_star"

    def __getattr__(self, attr):
        if attr in TransformedStochasticParameterBaseAttributes:
            return super(TransformedStochasticParameterBase, self).__getattr__(attr)
        elif attr.find("star_") == 0:
            return getattr(self.star, attr.split("star_")[1])
        else:
            return getattr(self.star, attr)

    def __setattr__(self, attr, value):
        if attr in ["name", "type", "star"]:
            super(TransformedStochasticParameterBase, self).__setattr__(attr, value)
            return self
        else:
            setattr(self.star, attr, value)
            return self

    def __repr__(self,  d=OrderedDict()):
        nKeys = len(d)
        for ikey, key in enumerate(TransformedStochasticParameterBaseAttributes[:-1]):
            d.update({str(nKeys+ikey) + ". " + key: str(getattr(self, key))})
        nKeys = len(d)
        for ikey, key in enumerate(TransformedStochasticParameterBaseStarAttributes):
            d.update({str(nKeys+ikey) + ". " + key: str(getattr(self, key))})
        d.update({str(len(d)) + ". star parameter": str(self.star)})
        return d

    def __str__(self):
        return formal_repr(self, self.__repr__())

    @property
    @abstractmethod
    def low(self):
        pass

    @property
    @abstractmethod
    def high(self):
        pass

    @property
    @abstractmethod
    def mean(self):
        pass

    @property
    @abstractmethod
    def median(self):
        pass

    @property
    @abstractmethod
    def mode(self):
        pass

    @property
    @abstractmethod
    def var(self):
        pass

    @property
    @abstractmethod
    def std(self):
        pass

    @property
    @abstractmethod
    def skew(self):
        pass

    @property
    @abstractmethod
    def kurt(self):
        pass

    @abstractmethod
    def _scipy_method(self, method, loc=0.0, scale=1.0, *args, **kwargs):
        pass

    def scipy_method(self, method, *args, **kwargs):
        return self._scipy_method(method, self.star.loc, self.star.scale, *args, **kwargs)

    @abstractmethod
    def numpy(self):
        pass
