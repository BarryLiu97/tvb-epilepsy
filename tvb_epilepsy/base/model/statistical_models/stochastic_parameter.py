import importlib

import numpy as np

from tvb_epilepsy.base.constants import MAX_SINGLE_VALUE
from tvb_epilepsy.base.configurations import VERY_LARGE_SIZE
from tvb_epilepsy.base.utils.data_structures_utils import formal_repr, sort_dict, isequal_string, shape_to_ndim, \
                                                                                                            ensure_list
from tvb_epilepsy.base.model.parameter import Parameter


def generate_stochastic_parameter(name="Parameter", low=-MAX_SINGLE_VALUE, high=MAX_SINGLE_VALUE, shape=(1,),
                                  probability_distribution="uniform", **kwargs):
    pdf_module = importlib.import_module("tvb_epilepsy.base.model.statistical_models.probability_distributions." +
                                  probability_distribution.lower() + "_distribution")
    ProbabilityDistribution = eval("pdf_module." + probability_distribution.title() + "Distribution")

    class StochasticParameter(Parameter, ProbabilityDistribution):

        def __init__(self, name="Parameter", low=-MAX_SINGLE_VALUE, high=MAX_SINGLE_VALUE, shape=(1,), **kwargs):
            Parameter.__init__(self, name, low, high, shape)
            ProbabilityDistribution.__init__(self, **kwargs)

        def __repr__(self):
            d = {"1. type": self.name,
                 "2. low": self.low,
                 "3. high": self.high,
                 "4. probability distribution": self.probability_distribution,
                 "5. p_shape": self.shape}
            return formal_repr(self, sort_dict(d))

        def __str__(self):
            return self.__repr__()

        def _prepare_for_h5(self):
            return Parameter._prepare_for_h5(self)

        def write_to_h5(self, folder, filename=""):
            Parameter.write_to_h5(self)

    #     def plot(self, **kwargs):
    #         mode = ensure_list(kwargs.get("mode", "pdf"))
    #         output = []
    #         if "pdf" in mode:
    #             pdf_fig, pdf_ax = self.plot_pdf(**kwargs)
    #             output = [pdf_fig, pdf_ax]
    #         if len(mode) > 0 or not (isequal_string(mode[0], "pdf")):
    #             stats_fig, stats_ax = self.plot_stats(**kwargs.get("stats", {}))
    #             return tuple(output + [stats_fig, stats_ax])
    #         else:
    #             return tuple(output)
    #     #
    #     # def plot_stats(self, **kwargs):
    # #     raise_not_implemented_error()
    # #
    # def plot_pdf(self, **kwargs):
    #     ndim = shape_to_ndim(self.p_shape)
    #     low = kwargs.get("low", -np.inf)
    #     high = kwargs.get("high", np.inf)
    #     ax = kwargs.get("ax", None)
    #     fig = kwargs.get("fig")
    #     if ax is None:
    #         pdf_size2 = np.sqrt(self.p_size)
    #         n_rows = np.int(np.ceil(pdf_size2))
    #         n_cols = np.int(np.floor(pdf_size2))
    #         if fig is None:
    #             fig, axes = pl.subplot(n_rows, n_cols, title=kwargs.get("title", self.name + " pdf",
    #                                                                     figsize=kwargs.get("figsize", VERY_LARGE_SIZE)))
    #         else:
    #             axes = fig.add_subplot(n_rows, n_cols, title=kwargs.get("title", self.name + " pdf",
    #                                                                     figsize=kwargs.get("figsize", VERY_LARGE_SIZE)))


    return StochasticParameter(name, low, high, shape, **kwargs)