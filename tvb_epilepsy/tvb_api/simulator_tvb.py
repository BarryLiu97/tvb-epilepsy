"""
Mechanism for launching TVB simulations.
"""

import sys
import time
import warnings
import numpy
from tvb.datatypes import connectivity, equations
from tvb.simulator import coupling, integrators, monitors, noise, simulator
from tvb_epilepsy.base.constants import *
from tvb_epilepsy.base.simulators import ABCSimulator, SimulationSettings
from tvb_epilepsy.base.calculations import calc_dfun, calc_coupling
from tvb_epilepsy.base.equilibrium_computation import calc_equilibrium_point, calc_eq_6d, calc_eq_z_2d
from tvb_epilepsy.tvb_api.epileptor_models import *


class SimulatorTVB(ABCSimulator):

    def __init__(self, model_instance):
        self.model = model_instance

    @staticmethod
    def _vep2tvb_connectivity(vep_conn):
        return connectivity.Connectivity(use_storage=False, weights=vep_conn.normalized_weights,
                                         tract_lengths=vep_conn.tract_lengths, region_labels=vep_conn.region_labels,
                                         centres=vep_conn.centers, hemispheres=vep_conn.hemispheres,
                                         orientations=vep_conn.orientations, areas=vep_conn.areas)

    def config_simulation(self, hypothesis, head_connectivity, settings=SimulationSettings()):

        tvb_conn = self._vep2tvb_connectivity(head_connectivity)
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
                                               random_stream=numpy.random.RandomState(seed=settings.noise_seed))
                    settings.noise_type = "Additive"
                    integrator = integrators.HeunStochastic(dt=settings.integration_step, noise=thisNoise)
            else:
                integrator = integrators.HeunDeterministic(dt=settings.integration_step)
                settings.noise_type = "None"

        #Set monitors:

        what_to_watch = []
        if isinstance(settings.monitors_preconfig, monitors.Monitor):
            what_to_watch = (settings.monitors_preconfig,)
        elif isinstance(settings.monitors_preconfig, tuple) or isinstance(settings.monitors_preconfig, list):
            for monitor in settings.monitors_preconfig:
                if isinstance(monitor, monitors.Monitor):
                    what_to_watch.append(monitor)
                what_to_watch = tuple(what_to_watch)

        # TODO: Find a better way to define monitor expressions without the need to modify the model...
        if settings.monitor_expressions is not None:
            self.model.variables_of_interest = settings.monitor_expressions

        #Create and configure TVB simulator object
        sim = simulator.Simulator(model=self.model, connectivity=tvb_conn, coupling=coupl, integrator=integrator,
                                  monitors=what_to_watch, simulation_length=settings.simulated_period)
        sim.configure()
        sim.initial_conditions = self.prepare_initial_conditions(hypothesis, sim.good_history_shape[0])

        #Update simulation settings
        settings.integration_step = integrator.dt
        settings.simulated_period = sim.simulation_length
        settings.integrator_type = integrator._ui_name
        settings.noise_ntau = integrator.noise.ntau
        settings.noise_intensity = numpy.array(settings.noise_intensity)
        settings.monitor_type = what_to_watch[0]._ui_name
        # TODO: find a way to store more than one monitors settings
        settings.monitor_sampling_period = what_to_watch[0].period
        settings.monitor_expressions = self.model.variables_of_interest
        settings.initial_conditions = sim.initial_conditions

        return sim, settings


    def launch_simulation(self, sim,  hypothesis, n_report_blocks=1):
        sim._configure_history(initial_conditions=sim.initial_conditions)
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

            try:
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
            except:
                print "WTF went wrong with this simulation?"

            return numpy.array(tavg_time), numpy.array(tavg_data)


    def launch_pse(self, hypothesis, head, settings=SimulationSettings()):
        raise NotImplementedError()


###
# A helper function to make good choices for simulation settings, noise and monitors
###

def setup_simulation(model_name, hypothesis, dt, sim_length, monitor_period, zmode=numpy.array("lin"), scale_time=1,
                     noise_instance=None, noise_intensity=None,
                     monitor_expressions=None, monitors_instance=None, variables_names=None):

    model = model_build_dict[model_name](hypothesis, scale_time, zmode=zmode)

    if isinstance(model, EpileptorDP):
        #                                               history
        simulator_instance = SimulatorTVB(model)
        model.tau1 *= scale_time
        if variables_names is None:
            variables_names = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'lfp']
    elif isinstance(model, EpileptorDP2D):
        model.tau1 *= scale_time
        simulator_instance = SimulatorTVB(model)
        if variables_names is None:
            variables_names = ['x1', 'z']
    elif isinstance(model, EpileptorDPrealistic):
        model.tau1 *= scale_time  # default = 0.25
        model.slope = 0.25
        model.pmode = numpy.array("z")  #
        simulator_instance = SimulatorTVB(model)
        if variables_names is None:
            variables_names = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'x0ts', 'slopeTS', 'Iext1ts', 'Iext2ts', 'Kts', 'lfp']
    elif isinstance(model, Epileptor):
        model.tt *= scale_time * 0.25
        # model.r = 1.0/2857.0  # default = 1.0 / 2857.0
        simulator_instance = SimulatorTVB(model)
        if variables_names is None:
            variables_names = ['x1', 'y1', 'z', 'x2', 'y2', 'g', 'lfp']

    if monitor_expressions is None:
        monitor_expressions = []
        for i in range(model._nvar):
            monitor_expressions.append("y" + str(i))
        # Monitor adjusted to the model
        if not(isinstance(model,EpileptorDP2D)):
            monitor_expressions.append("y3 - y0")

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
            eq = equations.Linear(parameters={"a": 1.0, "b": 0.0})  #  a*y+b, default = (1.0, 1.0)
            noise_instance = noise.Multiplicative(ntau=10, nsig=noise_intensity, b=eq,
                                                  random_stream=numpy.random.RandomState(seed=NOISE_SEED))
            noise_type = "Multiplicative"
            noise_shape = noise_instance.nsig.shape
            noise_instance.configure_coloured(dt=dt, shape=noise_shape)
        else:
            # White noise as a default choice:
            noise_instance = noise.Additive(nsig=noise_intensity,
                                            random_stream=numpy.random.RandomState(seed=NOISE_SEED))
            noise_instance.configure_white(dt=dt)
            noise_type = "Additive"
    else:
        if noise_intensity is not None:
            noise_instance.nsig = noise_intensity

    settings = SimulationSettings(simulated_period=sim_length, integration_step=dt,
                                  scale_time=scale_time,
                                  noise_preconfig=noise_instance, noise_type=noise_type,
                                  noise_intensity=noise_intensity, noise_ntau=noise_instance.ntau,
                                  noise_seed=NOISE_SEED,
                                  monitors_preconfig=monitors_instance, monitor_type=monitors_instance._ui_name,
                                  monitor_sampling_period=monitor_period, monitor_expressions=monitor_expressions,
                                  variables_names=variables_names)

    return simulator_instance, settings, variables_names, model
