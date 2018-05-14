import numpy as np
from tvb_epilepsy.service.model_inversion.epileptor_params_factory import generate_negative_lognormal_parameter
from tvb_epilepsy.plot.plotter import Plotter
from tvb_epilepsy.tests.base import BaseTest


if __name__ == "__main__":

    x0 = generate_negative_lognormal_parameter("x0", -2.5 * np.ones(2,), -4.0, 1.0,
                                               sigma=None, sigma_scale=3,
                                               p_shape=(2,), use="scipy")

    Plotter(BaseTest.config).plot_probabilistic_parameter(x0, figure_name="test_transformed_probabilistic_parameter")
    Plotter(BaseTest.config).plot_probabilistic_parameter(x0.star, figure_name="test_transformed_probabilistic_parameter_star")
    print(x0)
    print("Done")