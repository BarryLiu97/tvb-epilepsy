
from tvb_epilepsy.base.utils.log_error_utils import raise_value_error
from tvb_epilepsy.base.utils.data_structures_utils import formal_repr, sort_dict, isequal_string
from tvb_epilepsy.base.h5_model import convert_to_h5_model



class StatisticalModel(object):

    def __init__(self, name, parameters, n_regions=0):
        self.n_regions = n_regions
        if isinstance(name, basestring):
            self.name = name
        else:
            raise_value_error("Statistical model's type " + str(name) + " is not a string!")
        # Parameter setting:
        self.parameters = parameters
        self.n_parameters = len(self.parameters)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        d = {"1. type": self.name,
             "2. number of regions": self.n_regions,
             "3. number of parameters": self.n_parameters,
             "4. parameters": self.parameters}
        return formal_repr(self, sort_dict(d))

    def _prepare_for_h5(self):
        h5_model = convert_to_h5_model(self)
        h5_model.add_or_update_metadata_attribute("EPI_Type", "StatisicalModel")
        return h5_model

    def write_to_h5(self, folder, filename=""):
        if filename == "":
            filename = self.name + ".h5"
        h5_model = self._prepare_for_h5()
        h5_model.write_to_h5(folder, filename)
