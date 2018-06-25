from collections import OrderedDict

from tvb_infer.base.config import CalculusConfig
from tvb_infer.base.utils.log_error_utils import raise_value_error
from tvb_infer.base.utils.data_structures_utils import formal_repr, sort_dict


class Parameter(object):

    def __init__(self, name="Parameter", low=CalculusConfig.MIN_SINGLE_VALUE, high=CalculusConfig.MAX_SINGLE_VALUE,
                 p_shape=()):
        if isinstance(name, basestring):
            self.name = name
        else:
            raise_value_error("Parameter type " + str(name) + " is not a string!")
        if low < high:
            self.low = low
            self.high = high
        else:
            raise_value_error("low (" + str(low) + ") is not smaller than high(" + str(high) + ")!")
        if isinstance(p_shape, tuple):
            self.__p_shape = p_shape
        else:
            raise_value_error("Parameter's " + str(self.name) + " p_shape="
                              + str(p_shape) + " is not a shape tuple!")

    @property
    def p_shape(self):
        return self.__p_shape

    def _repr(self,  d=OrderedDict()):
        for ikey, key in enumerate(["name", "low", "high", "p_shape"]):
            d.update({key: getattr(self, key)})
        return d

    def __repr__(self,  d=OrderedDict()):
        return formal_repr(self, self._repr(d))

    def __str__(self):
        return self.__repr__()
