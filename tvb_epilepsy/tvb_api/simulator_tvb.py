"""
Mechanism for launching TVB simulations.
"""

import sys
import time
import numpy
from tvb.datatypes import connectivity, equations
from tvb.simulator import coupling, integrators, monitors, noise, simulator
from tvb_epilepsy.base.constants import *
from tvb_epilepsy.base.simulators import ABCSimulator, SimulationSettings
from tvb_epilepsy.base.equilibrium_computation import y1eq_calc, pop2eq_calc, geq_calc, \
                                                      calc_equilibrium_point, assert_equilibrium_point
from tvb_epilepsy.tvb_api.epileptor_models import *


class SimulatorTVB(ABCSimulator):

    def __init__(self, model_instance, builder_initial_conditions):
        self.model = model_instance
        self.builder_initial_conditions = builder_initial_conditions

    @staticmethod
    def _vep2tvb_connectivity(vep_conn):
        return connectivity.Connectivity(use_storage=False, weights=vep_conn.normalized_weights,
                                         tract_lengths=vep_conn.tract_lengths, region_labels=vep_conn.region_labels,
                                         centres=vep_conn.centers, hemispheres=vep_conn.hemispheres,
                                         orientations=vep_conn.orientations, areas=vep_conn.areas)

    def config_simulation(self, head, settings=SimulationSettings()):

        tvb_conn = self._vep2tvb_connectivity(head.connectivity)
        coupl = coupling.Difference(a=1.)

        # Set noise:

        if isinstance(settings.noise_preconfig,noise.Noise):
            integrator = integrators.HeunStochastic(dt=settings.integration_step, noise=settings.noise_preconfig)
        else:
            settings.noise_intensity = numpy.array(settings.noise_intensity)
            if settings.noise_intensity.size == 1:
                settings.noise_intensity = numpy.repeat(numpy.squeeze(settings.noise_intensity),self.model.nvar)
            if numpy.min(settings.noise_intensity) > 0:
                    thisNoise = noise.Additive(nsig=settings.noise_intensity,
                                               random_stream=numpy.random.RandomState(seed=settings.integration_noise_seed))
                    integrator = integrators.HeunStochastic(dt=settings.integration_step, noise=thisNoise)
            else:
                integrator = integrators.HeunDeterministic(dt=settings.integration_step)

        #Set monitors:

        what_to_watch = []
        if isinstance(settings.monitors_preconfig, monitors.Monitor):
            what_to_watch = (settings.monitors_preconfig,)
        elif isinstance(settings.monitors_preconfig, tuple) or isinstance(settings.monitors_preconfig, list):
            for monitor in settings.monitors_preconfig:
                if isinstance(monitor, monitors.Monitor):
                    what_to_watch.append(monitor)
                what_to_watch = tuple(what_to_watch)
        if len(what_to_watch) == 0:
            what_to_watch = monitors.TemporalAverage(period=settings.monitor_sampling_period)

        # TODO: Find a better way to define monitor expressions without the need to modify the model...
        if settings.monitor_expr is not None:
            self.model.variables_of_interest = settings.monitor_expr

        sim = simulator.Simulator(model=self.model, connectivity=tvb_conn, coupling=coupl, integrator=integrator,
                                  monitors=what_to_watch, simulation_length=settings.simulated_period)
        return sim


    def launch_simulation(self, sim, hypothesis, n_report_blocks=1):
        sim.configure()
        self.initial_conditions = self.builder_initial_conditions(hypothesis, self.model, sim.good_history_shape[0])
        sim._configure_history(initial_conditions=self.initial_conditions)
        if n_report_blocks<2:
            tavg_time, tavg_data = sim.run()[0]
            return tavg_time, tavg_data
        else:
            sim_length = sim.simulation_length / sim.monitors[0].period
            block_length = sim_length / n_report_blocks
            curr_time_step = 0.0
            curr_block = 1.0

            # Perform the simulation
            tavg_data, tavg_time = [], []

            start = time.time()

            for tavg in sim():

                curr_time_step += 1.0

                if not tavg is None:
                    tavg_time.append(tavg[0][0])
                    tavg_data.append(tavg[0][1])

                if curr_time_step >= curr_block * block_length:
                    end_block = time.time()
                    print_this = "\r" + "..." + str(100 * curr_time_step / sim_length) + "% done in " +\
                                 str(end_block-start) + " secs"
                    sys.stdout.write(print_this)
                    sys.stdout.flush()
                    curr_block += 1.0

            return numpy.array(tavg_time), numpy.array(tavg_data)


    def launch_pse(self, hypothesis, head, settings=SimulationSettings()):
        raise NotImplementedError()



###
# Prepare for TVB configuration
###

def calc_tvb_equilibrium_point(epileptor_model, hypothesis):
    y1eq = y1eq_calc(hypothesis.x1EQ, epileptor_model.c.T)
    zeq = zeq_6d_calc(hypothesis.x1EQ, epileptor_model.c.T, epileptor_model.Iext.T)
    if epileptor_model.Iext2.size == 1:
        epileptor_model.Iext2 = epileptor_model.Iext2[0] * numpy.ones((hypothesis.n_regions, 1))
    (x2eq, y2eq) = pop2eq_calc(hypothesis.x1EQ, zeq, epileptor_model.Iext2.T)
    geq = geq_calc(hypothesis.x1EQ)

    equilibrium_point = numpy.r_[hypothesis.x1EQ, y1eq, zeq, x2eq, y2eq, geq].astype('float32')

    assert_equilibrium_point(epileptor_model, hypothesis, equilibrium_point)

    return hypothesis.x1EQ, y1eq, zeq, x2eq, y2eq, geq

def prepare_for_tvb_model(hypothesis, model, history_length):
    #Set default initial conditions right on the resting equilibrium point of the model...
    #...after computing the equilibrium point
    (x1EQ, y1EQ, zEQ, x2EQ, y2EQ, gEQ) = calc_tvb_equilibrium_point(model, hypothesis)
    initial_conditions = numpy.expand_dims(numpy.r_[x1EQ, y1EQ, zEQ, x2EQ, y2EQ, gEQ],2)
    initial_conditions = numpy.tile(initial_conditions, (history_length, 1, 1, 1))
    return initial_conditions


###
# Prepare for tvb-epilepsy epileptor_models
###

def prepare_initial_conditionsl(hypothesis, model, history_length):
    # Set default initial conditions right on the resting equilibrium point of the model...
    # ...after computing the equilibrium point (and correct it for zeql for a >=6D model
    initial_conditions = calc_equilibrium_point(model, hypothesis)
    #-------------------The lines below are for a specific "realistic" demo simulation:---------------------------------
    #if isinstance(mode,EpileptorDPrealistic):
    #   shape = initial_conditions[6].shape
    #   type = initial_conditions[6].dtype
    #   initial_conditions[6] = 0.0** numpy.ones(shape,dtype=type) # hypothesis.x0.T
    #   initial_conditions[7] = 1.0 * numpy.ones((1,hypothesis.n_regions))#model.slope * numpy.ones((hypothesis.n_regions,1))
    #   initial_conditions[9] = 0.0 * numpy.ones((1,hypothesis.n_regions))#model.Iext2.T * numpy.ones((hypothesis.n_regions,1))
    # ------------------------------------------------------------------------------------------------------------------
    initial_conditions = numpy.expand_dims(initial_conditions, 2)
    initial_conditions = numpy.tile(initial_conditions, (history_length, 1, 1, 1))
    return initial_conditions


###
# A helper function to make good choices for simulation settings, noise and monitors
###

def setup_simulation(model, dt, sim_length, monitor_period, monitor_expr=None, monitors_instance=None,
                     noise_instance=None, noise_intensity=None, variables_names=None):

    if isinstance(model,EpileptorDP):
        #                                               history
        simulator_instance = SimulatorTVB(model, prepare_initial_conditionsl)
        if variables_names is None:
            variables_names = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'lfp']
    elif isinstance(model,EpileptorDP2D):
        simulator_instance = SimulatorTVB(model, prepare_initial_conditionsl)
        if variables_names is None:
            variables_names = ['x1', 'z']
    elif isinstance(model,EpileptorDPrealistic):
        simulator_instance = SimulatorTVB(model, prepare_initial_conditionsl)
        if variables_names is None:
            variables_names = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'x0ts', 'slopeTS', 'Iext1ts', 'Iext2ts', 'Kts', 'lfp']
    elif isinstance(model,Epileptor):
        simulator_instance = SimulatorTVB(model, prepare_for_tvb_model)
        if variables_names is None:
            variables_names = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'lfp']

    if monitor_expr is None:
        monitor_expr = []
        for i in range(model._nvar):
            monitor_expr.append("y" + str(i))
        # Monitor adjusted to the model
        if not(isinstance(model,EpileptorDP2D)):
            monitor_expr.append("y3-y0")

    if monitors_instance is None:
        monitors_instance = monitors.TemporalAverage(period=monitor_period)
    else:
        if monitor_period is not None:
            monitors_instance.period = monitor_period

    if noise_instance is None:
        if noise_intensity is None:
            if numpy.all(noise_intensity is None):
                # Noise configuration
                if isinstance(model,EpileptorDPrealistic):
                    #                             x1  y1   z     x2   y2    g   x0   slope  Iext1 Iext2 K
                    noise_intensity = numpy.array([0., 0., 1e-7, 0.0, 1e-7, 0., 1e-8, 1e-3, 1e-8, 1e-3, 1e-9])
                elif isinstance(model,EpileptorDP2D):
                    #                              x1   z
                    noise_intensity = numpy.array([0., 5e-5])
                else:
                    #                              x1  y1   z     x2   y2   g
                    noise_intensity = numpy.array([0., 0., 5e-6, 0.0, 5e-6, 0.])

        # Preconfigured noise
        if isinstance(model,EpileptorDPrealistic):
            # Colored noise for realistic simulations
            eq = equations.Linear(parameters={"a": 0.0, "b": 1.0})  # default = a*y+b
            noise_instance = noise.Multiplicative(ntau=10, nsig=noise_intensity, b=eq,
                                                  random_stream=numpy.random.RandomState(seed=NOISE_SEED))
            noise_shape = noise_instance.nsig.shape
            noise_instance.configure_coloured(dt=dt, shape=noise_shape)
        else:
            # White noise as a default choice:
            noise_instance = noise.Additive(nsig=noise_intensity,
                                            random_stream=numpy.random.RandomState(seed=NOISE_SEED))
            noise_instance.configure_white(dt=dt)
    else:
        if noise_intensity is not None:
            noise_instance.nsig = noise_intensity

    settings = SimulationSettings(simulated_period=sim_length, integration_step=dt,
                                  noise_preconfig=noise_instance, noise_intensity=noise_intensity,
                                  integration_noise_seed=NOISE_SEED,
                                  monitors_preconfig=monitors_instance,
                                  monitor_sampling_period=monitor_period, monitor_expr=monitor_expr)

    return simulator_instance, settings, variables_names
