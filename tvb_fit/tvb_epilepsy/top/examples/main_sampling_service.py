# -*- coding: utf-8 -*-

import numpy as np
from copy import deepcopy

from tvb_fit.tvb_epilepsy.base.constants.config import Config
from tvb_fit.base.model.probability_distributions import ProbabilityDistributionTypes
from tvb_fit.service.probabilistic_parameter_builder import set_parameter, set_parameter_defaults, \
    generate_probabilistic_parameter
from tvb_fit.samplers.deterministic_sampler import DeterministicSampler
from tvb_fit.samplers.salib_sampler_interface import SalibSamplerInterface
from tvb_fit.samplers.probabilistic_sampler import ProbabilisticSampler

from tvb_utils.log_error_utils import initialize_logger
from tvb_utils.data_structures_utils import isequal_string


def main_sampling_service(config=Config()):
    logger = initialize_logger(__name__, config.out.FOLDER_LOGS)

    n_samples = 100
    logger.info("\nDeterministic numpy.linspace sampling:")
    sampler = DeterministicSampler(n_samples=n_samples, grid_mode=True)
    samples, stats = sampler.generate_samples(low=1.0, high=2.0, shape=(2,), stats=True)
    for key, value in stats.items():
        logger.info("\n" + key + ": " + str(value))
    logger.info(sampler.__repr__())

    logger.info("\nStochastic uniform sampling with numpy:")
    sampler = ProbabilisticSampler(n_samples=n_samples, sampling_module="numpy")
    #                                      a (low), b (high)
    samples, stats = sampler.generate_samples(parameter=(1.0, 2.0),
                                              probability_distribution=ProbabilityDistributionTypes.UNIFORM, shape=(2,),
                                              stats=True)
    for key, value in stats.items():
        logger.info("\n" + key + ": " + str(value))

    logger.info(sampler.__repr__())

    logger.info("\nStochastic truncated normal sampling with scipy:")
    sampler = ProbabilisticSampler(n_samples=n_samples)
    #                                   loc (mean), scale (sigma)
    samples, stats = sampler.generate_samples(parameter=(1.5, 1.0), probability_distribution="norm", low=1, high=2,
                                              shape=(2,), stats=True)
    for key, value in stats.items():
        logger.info("\n" + key + ": " + str(value))
    logger.info(sampler.__repr__())

    logger.info("\nSensitivity analysis sampling:")
    sampler = SalibSamplerInterface(n_samples=n_samples, sampler="latin")
    samples, stats = sampler.generate_samples(low=1, high=2, shape=(2,), stats=True)
    for key, value in stats.items():
        logger.info("\n" + key + ": " + str(value))
    logger.info(sampler.__repr__())

    logger.info("\nTesting distribution class and conversions...")
    sampler = ProbabilisticSampler(n_samples=n_samples)
    for distrib_name in ProbabilityDistributionTypes.available_distributions:
        logger.info("\n" + distrib_name)
        logger.info("\nmode/mean, std to distribution " + distrib_name + ":")
        if np.in1d(distrib_name, [ProbabilityDistributionTypes.EXPONENTIAL, ProbabilityDistributionTypes.CHISQUARE]):
            target_stats = {"mean": 1.0}
            stats_m = "mean"
        elif np.in1d(distrib_name, [ProbabilityDistributionTypes.BERNOULLI, ProbabilityDistributionTypes.POISSON]):
            target_stats = {"mean": np.ones((2,))}
            stats_m = "mean"
        elif isequal_string(distrib_name, ProbabilityDistributionTypes.BINOMIAL):
            target_stats = {"mean": 1.0, "std": 2.0}
            stats_m = "mean"
        else:
            if isequal_string(distrib_name, ProbabilityDistributionTypes.UNIFORM):
                target_stats = {"mean": 1.0, "std": 2.0}
                stats_m = "mean"
            else:
                target_stats = {"mean": 1.0, "std": 2.0}
                stats_m = "mean"
        parameter1 = generate_probabilistic_parameter(name="test1_" + distrib_name, low=0.0, high=2.0, p_shape=(2, 2),
                                                      probability_distribution=distrib_name, optimize_pdf=True,
                                                      use="manual", **target_stats)
        name2 = "test2_" + distrib_name
        defaults = set_parameter_defaults(name2, _pdf=distrib_name, _shape=(2, 2), _lo=0.0, _hi=2.0,
                                          **(deepcopy(target_stats)))
        parameter2 = set_parameter(name=name2, use="manual", **defaults)
        for parameter in (parameter1, parameter2):
            logger.info(str(parameter))
            samples = sampler.generate_samples(parameter=parameter, stats=True)
            for key, value in stats.items():
                logger.info("\n" + key + ": " + str(value))
            diff = target_stats[stats_m] - stats[stats_m]
            if np.any(np.abs(diff.flatten()) > 0.001):
                logger.warning("Large difference between target and resulting samples' " + stats_m + "!: " + str(diff))
            del parameter


if __name__ == "__main__":
    main_sampling_service()
