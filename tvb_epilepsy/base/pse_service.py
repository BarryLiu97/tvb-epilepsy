"""
Mechanism for parameter search exploration for LSA and simulations (it will have TVB or custom implementations)
"""

import subprocess
import warnings
import numpy as np
from copy import deepcopy
from tvb_epilepsy.base.constants import EIGENVECTORS_NUMBER_SELECTION, K_DEF, YC_DEF, I_EXT1_DEF, A_DEF, B_DEF
from tvb_epilepsy.base.simulators import ABCSimulator
from tvb_epilepsy.base.disease_hypothesis import DiseaseHypothesis
from tvb_epilepsy.base.model_configuration import ModelConfiguration
from tvb_epilepsy.base.model_configuration_service import ModelConfigurationService
from tvb_epilepsy.base.lsa_service import LSAService
from tvb_epilepsy.base.epileptor_model_factory import model_build_dict
from tvb_epilepsy.tvb_api.simulator_tvb import SimulatorTVB
from tvb_epilepsy.custom.simulator_custom import SimulatorCustom, custom_model_builder
from tvb_epilepsy.custom.read_write import read_ts


def set_object_attribute_recursively(object, path, values, indices):

    # Convert the parameter's path to a list of strings separated by "."
    path = path.split(".")

    # If there is more than one levels...
    if len(path) > 1:
        #...call the function recursively
        set_object_attribute_recursively(getattr(object, path[0]), ".".join(path[1:]), values, indices)

    else:
        # ...else, set the parameter values for the specified indices
        temp = getattr(object, path[0])
        if len(indices) > 0:
            temp[indices] = values #index has to be linear... i.e., 1D...
        else:
            temp = values
        setattr(object, path[0], temp)


def pop_object_parameters(object_type, params_paths, params_values, params_indices):

    object_params_paths = []
    object_params_values = []
    object_params_indices = []
    items_to_delete = []
    for ip in range(len(params_paths)):
        if params_paths[ip].split(".")[0] == object_type:
            object_params_paths.append(params_paths[ip].split(".")[1])
            object_params_values.append(params_values[ip])
            object_params_indices.append(params_indices[ip])
            items_to_delete.append(ip)

    params_paths = np.delete(params_paths, items_to_delete)
    params_values = np.delete(params_values, items_to_delete)
    params_indices = np.delete(params_indices, items_to_delete)

    return object_params_paths, object_params_values, object_params_indices, params_paths, params_values, params_indices


def update_object(object, object_type, params_paths, params_values, params_indices):
    update_flag = False
    object_params_paths, object_params_values, object_params_indices, params_paths, params_values, params_indices = \
        pop_object_parameters(object_type, params_paths, params_values, params_indices)
    for ip in range(len(object_params_paths)):
        set_object_attribute_recursively(object, object_params_paths[ip], object_params_values[ip],
                                         object_params_indices[ip])
        update_flag = True
    return object, params_paths, params_values, params_indices, update_flag


def update_hypothesis(hypothesis_input, params_paths, params_values, params_indices,
                      model_configuration_service_input=None,
                      yc=YC_DEF, Iext1=I_EXT1_DEF, K=K_DEF, a=A_DEF, b=B_DEF, x1eq_mode="optimize"):

    # Assign possible hypothesis parameters on a new hypothesis object:
    hypothesis = deepcopy(hypothesis_input)
    hypothesis, params_paths, params_values, params_indices = \
        update_object(hypothesis, "hypothesis", params_paths, params_values, params_indices)[:4]
    hypothesis.update(name=hypothesis.name)

    # ...create/update a model configuration service:
    if isinstance(model_configuration_service_input, ModelConfigurationService):
        model_configuration_service = deepcopy(model_configuration_service_input)
    else:
        model_configuration_service = ModelConfigurationService(yc=yc, Iext1=Iext1, K=K, a=a, b=b, x1eq_mode=x1eq_mode)

    # ...modify possible related parameters:
    model_configuration_service, params_paths, params_values, params_indices = \
        update_object(model_configuration_service, "model_configuration_service", params_paths, params_values,
                      params_indices)[:4]

    # ...and compute a new model_configuration:
    if hypothesis.type == "Epileptogenicity":
        model_configuration = model_configuration_service.configure_model_from_E_hypothesis(hypothesis)
    else:
        model_configuration = model_configuration_service.configure_model_from_hypothesis(hypothesis)

    return hypothesis, model_configuration, params_paths, params_values, params_indices


def lsa_out_fun(hypothesis, model_configuration=None, **kwargs):
    if isinstance(model_configuration, ModelConfiguration):
        return {"propagation_strengths": hypothesis.propagation_strenghts, "x0_values": model_configuration.x0_values,
                "E_values": model_configuration.E_values, "x1EQ": model_configuration.x1EQ,
                "zEQ": model_configuration.zEQ, "Ceq": model_configuration.Ceq}
    else:
        hypothesis.propagation_strenghts


def lsa_run_fun(hypothesis_input, params_paths, params_values, params_indices, out_fun=lsa_out_fun,
                model_configuration_service_input=None,
                yc=YC_DEF, Iext1=I_EXT1_DEF, K=K_DEF, a=A_DEF, b=B_DEF, x1eq_mode="optimize",
                lsa_service_input=None,
                n_eigenvectors=EIGENVECTORS_NUMBER_SELECTION, weighted_eigenvector_sum=True):

    try:
        # Update hypothesis and create a new model_configuration:
        hypothesis, model_configuration, params_paths, params_values, params_indices\
            = update_hypothesis(hypothesis_input, params_paths, params_values, params_indices,
                                model_configuration_service_input, yc, Iext1, K, a, b, x1eq_mode)

        # ...create/update lsa service:
        if isinstance(lsa_service_input, LSAService):
            lsa_service = deepcopy(lsa_service_input)
        else:
            lsa_service = LSAService(n_eigenvectors=n_eigenvectors, weighted_eigenvector_sum=weighted_eigenvector_sum)

        # ...and modify possible related parameters:
        lsa_service = \
            update_object(lsa_service, "lsa_service", params_paths, params_values, params_indices)[0]

        # Run LSA:
        lsa_hypothesis = lsa_service.run_lsa(hypothesis, model_configuration)

        if callable(out_fun):
            output = out_fun(lsa_hypothesis, model_configuration=model_configuration)
        else:
            output = lsa_hypothesis

        return True, output

    except:

        return False, None


def sim_out_fun(simulator, time, data, **kwargs):

    if data is None:
        time, data = read_ts(simulator.results_path, data="data")

    return {"time": time, "data": data}


def sim_run_fun(simulator_input, params_paths, params_values, params_indices, out_fun=sim_out_fun, hypothesis_input=None,
                model_configuration_service_input=None,
                yc=YC_DEF, Iext1=I_EXT1_DEF, K=K_DEF, a=A_DEF, b=B_DEF, x1eq_mode="optimize",
                update_initial_conditions=True):

    # Create new objects from the input simulator
    simulator = deepcopy(simulator_input)
    model_configuration = deepcopy(simulator_input.model_configuration)
    model = deepcopy(simulator_input.model)

    try:

        # First try to update model_configuration via an input hypothesis...:
        if isinstance(hypothesis_input, DiseaseHypothesis):
            hypothesis, model_configuration, params_paths, params_values, params_indices = \
                update_hypothesis(hypothesis_input, params_paths, params_values, params_indices,
                                  model_configuration_service_input, yc, Iext1, K, a, b, x1eq_mode)
            # Update model configuration:
            simulator.model_configuration = model_configuration
            # ...in which case a model has to be regenerated:
            if isinstance(simulator, SimulatorTVB):
                model = model_build_dict[model._ui_name](model_configuration, zmode=model.zmode)
            else:
                model = custom_model_builder(model_configuration)

        # Now (further) update model if needed:
        model, params_paths, params_values, params_indices = \
            update_object(model, "model", params_paths, params_values, params_indices)
        simulator.model = model

        # Now, update other possible remaining parameters, i.e., concerning the integrator, noise etc...
        for ip in range(len(params_paths)):
            set_object_attribute_recursively(simulator, params_paths[ip], params_values[ip], params_indices[ip])

        # Now, recalculate the default initial conditions...
        # If initial conditions were parameters, then, this flag can be set to False
        if update_initial_conditions:
            simulator.configure_initial_conditions()

        time, data, status = simulator.launch()

        if status:
            output = out_fun(time, data, simulator)

        return True, output

    except:

        return False, None


class PSE_service(object):

    def __init__(self, task, hypothesis=None, simulator=None, params_pse=None, run_fun=None, out_fun=None):

        if task not in ["LSA", "SIMULATION"]:
            raise ValueError("\ntask = " + str(task) + " is not a valid pse task." +
                             "\nSelect one of 'LSA', or 'SIMULATION' to perform parameter search exploration of " +
                             "\n hypothesis Linear Stability Analysis, or simulation, " + "respectively")

        self.task = task

        if task == "LSA":

            # TODO: this will not work anymore
            if isinstance(hypothesis, DiseaseHypothesis):
                self.pse_object = hypothesis

            else:
                raise ValueError("\ntask = LSA" + str(task) + " but hypothesis is not a Hypothesis object!")

            def_run_fun = lsa_run_fun
            def_out_fun = lsa_out_fun

        else:

            if isinstance(simulator, ABCSimulator):
                self.pse_object = simulator

            else:
                raise ValueError("\ntask = 'SIMULATION'" + str(task) + " but simulator is not an object of" +
                                 " one of the available simulator classes!")

            def_run_fun = sim_run_fun
            def_out_fun = sim_out_fun

        if not (callable(run_fun)):
            warnings.warn("\nUser defined run_fun is not callable. Using default one for task " + str(task) +"!")
            self.run_fun = def_run_fun
        else:
            self.run_fun = run_fun

        if not (callable(out_fun)):
            warnings.warn("\nUser defined out_fun is not callable. Using default one for task " + str(task) +"!")
            self.out_fun = def_out_fun
        else:
            self.out_fun = out_fun

        if isinstance(params_pse, list):

            self.params_paths = []
            self.n_params_vals = []
            self.params_indices = []
            temp = []
            for param in params_pse:
                # parameter path:
                self.params_paths.append(param["path"])
                # parameter values/samples:
                temp2 = param["samples"].flatten()
                temp.append(temp2)
                self.n_params_vals.append(temp2.size)
                # parameter indices:
                self.params_indices.append(param.get("indices", []))

            self.n_params_vals = np.array(self.n_params_vals)
            self.n_params = len(self.params_paths)

            if not(np.all(self.n_params_vals == self.n_params_vals[0])):
                raise ValueError("\nNot all parameters have the same number of samples!: " +
                                     "\n" + str(self.params_paths) + " = " + str( self.n_params_vals))
            else:
                self.n_params_vals = self.n_params_vals[0]

            self.pse_params = np.vstack(temp).T
            self.params_paths = np.array(self.params_paths)
            self.params_indices = np.array(self.params_indices)
            self.n_loops = self.pse_params.shape[0]

            print "\nGenerated a parameter search exploration for " + str(task) + ","
            print "with " + str(self.n_params) + " parameters of " + str(self.n_params_vals) + " values each,"
            print "leading to " + str(self.n_loops) + " total execution loops"

        else:
            raise ValueError("\nparams_pse is not a list of tuples!")

    def run_pse(self, grid_mode=False, **kwargs):

        results = []
        execution_status = []

        for iloop in range(self.n_loops):

            params = self.pse_params[iloop, :]

            print "\nExecuting loop " + str(iloop) + " of " + str(self.n_loops)
            # print "\nParameters:"
            # for ii in range(len(params)):
            #      print self.params_paths[ii] + "[" + str(self.params_indices[ii]) + "] = " + str(params[ii])

            status = False
            output = None

            try:
                status, output = self.run_fun(self.pse_object, self.params_paths, params, self.params_indices,
                                              self.out_fun, **kwargs)

            except:
                pass

            if not status:
                warnings.warn("\nExecution of loop " + str(iloop) + "failed!")

            results.append(output)
            execution_status.append(status)

        if grid_mode:
            results = np.reshape(np.array(results, dtype="O"), tuple(self.n_params_vals))
            execution_status = np.reshape(np.array(execution_status), tuple(self.n_params_vals))

        return results, execution_status

    def run_pse_parallel(self, grid_mode=False):
        # TODO: start each loop on a separate process, gather results and return them
        raise NotImplementedError


# Test and example functions:

# This function is a helper function to run parameter search exploration (pse)
# for Linear Stability Analysis (LSA).

def pse_from_hypothesis(hypothesis, n_samples, half_range=0.1, global_coupling=[],
                                             healthy_regions_parameters=[], model_configuration=None,
                                             model_configuration_service=None, lsa_service=None, **kwargs):

    from tvb_epilepsy.base.constants import MAX_DISEASE_VALUE
    from tvb_epilepsy.base.utils import linear_index_to_coordinate_tuples, dicts_of_lists_to_lists_of_dicts
    from tvb_epilepsy.base.sample_service import StochasticSampleService

    all_regions_indices = range(hypothesis.get_number_of_regions())
    disease_indices = hypothesis.get_regions_disease_indices()
    healthy_indices = np.delete(all_regions_indices, disease_indices).tolist()

    pse_params = {"path": [], "indices": [], "name": [], "samples": []}

    # First build from the hypothesis the input parameters of the parameter search exploration.
    # These can be either originating from excitability, epileptogenicity or connectivity hypotheses,
    # or they can relate to the global coupling scaling (parameter K of the model configuration)
    for ii in range(len(hypothesis.x0_values)):
        pse_params["indices"].append([ii])
        pse_params["path"].append("hypothesis.x0_values")
        pse_params["name"].append(str(hypothesis.connectivity.region_labels[hypothesis.x0_indices[ii]]) +
                                  " Excitability")

        # Now generate samples using a truncated uniform distribution
        sampler = StochasticSampleService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                          random_seed=kwargs.get("random_seed", None),
                                          trunc_limits={"high": MAX_DISEASE_VALUE},
                                          sampler="uniform",
                                          loc=hypothesis.x0_values[ii] - half_range, scale=2 * half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    for ii in range(len(hypothesis.e_values)):
        pse_params["indices"].append([ii])
        pse_params["path"].append("hypothesis.e_values")
        pse_params["name"].append(str(hypothesis.connectivity.region_labels[hypothesis.x0_indices[ii]]) +
                                  " Epileptogenicity")

        # Now generate samples using a truncated uniform distribution
        sampler = StochasticSampleService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                          random_seed=kwargs.get("random_seed", None),
                                          trunc_limits={"high": MAX_DISEASE_VALUE},
                                          sampler="uniform",
                                          loc=hypothesis.e_values[ii] - half_range, scale=2 * half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    for ii in range(len(hypothesis.w_values)):
        pse_params["indices"].append([ii])
        pse_params["path"].append("hypothesis.w_values")
        inds = linear_index_to_coordinate_tuples(hypothesis.w_indices[ii], hypothesis.connectivity.weights.shape)
        if len(inds) == 1:
            pse_params["name"].append(str(hypothesis.connectivity.region_labels[inds[0][0]]) + "-" +
                                str(hypothesis.connectivity.region_labels[inds[0][0]]) + " Connectivity")
        else:
            pse_params["name"].append("Connectivity[" + str(inds), + "]")

        # Now generate samples using a truncated normal distribution
        sampler = StochasticSampleService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                          random_seed=kwargs.get("random_seed", None),
                                          trunc_limits={"high": MAX_DISEASE_VALUE},
                                          sampler="norm", loc=hypothesis.w_values[ii], scale=half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    if model_configuration_service is None:
        kloc = K_DEF
    else:
        kloc = model_configuration_service.K_unscaled[0]
    for val in global_coupling:
        pse_params["path"].append("model.configuration.service.K_unscaled")
        inds = val.get("indices", all_regions_indices)
        if np.all(inds == all_regions_indices):
            pse_params["name"].append("Global coupling")
        else:
            pse_params["name"].append("Afferent coupling[" + str(inds) + "]")
        pse_params["indices"].append(inds)

        # Now generate samples susing a truncated normal distribution
        sampler = StochasticSampleService(n_samples=n_samples, n_outputs=1, sampling_module="scipy",
                                          random_seed=kwargs.get("random_seed", None),
                                          trunc_limits={"low": 0.0}, sampler="norm", loc=kloc, scale=30*half_range)
        pse_params["samples"].append(sampler.generate_samples(**kwargs))

    pse_params_list = dicts_of_lists_to_lists_of_dicts(pse_params)

    # Add a random jitter to the healthy regions if required...:
    for val in healthy_regions_parameters:
        inds = val.get("indices", healthy_indices)
        name = val.get("name", "x0")
        n_params = len(inds)
        sampler = StochasticSampleService(n_samples=n_samples, n_outputs=n_params, sampler="uniform",
                                          trunc_limits={"low": 0.0}, sampling_module="scipy",
                                          random_seed=kwargs.get("random_seed", None),
                                          loc=kwargs.get("loc", 0.0), scale=kwargs.get("scale", 2*half_range))

        samples = sampler.generate_samples(**kwargs)
        for ii in range(n_params):
            pse_params_list.append({"path": "model_configuration_service." + name, "samples": samples[ii],
                                    "indices": [inds[ii]], "name": name})

    # Now run pse service to generate output samples:

    pse = PSE_service("LSA", hypothesis=hypothesis, params_pse=pse_params_list)
    pse_results, execution_status = pse.run_pse(grid_mode=False, lsa_service_input=lsa_service,
                                                model_configuration_service_input=model_configuration_service)

    pse_results = list_of_dicts_to_dicts_of_ndarrays(pse_results)

    return pse_results, pse_params_list

if __name__ == "__main__":

    import os
    from tvb_epilepsy.base.constants import DATA_CUSTOM, FOLDER_RES
    from tvb_epilepsy.base.utils import list_of_dicts_to_dicts_of_ndarrays
    from tvb_epilepsy.custom.readers_custom import CustomReader as Reader
    from tvb_epilepsy.custom.read_write import write_h5_model
    from tvb_epilepsy.base.h5_model import prepare_for_h5
    from tvb_epilepsy.base.sample_service import DeterministicSampleService, StochasticSampleService
    from tvb_epilepsy.base.plot_tools import plot_lsa_pse

    # -------------------------------Reading data-----------------------------------

    data_folder = os.path.join(DATA_CUSTOM, 'Head')

    reader = Reader()

    head = reader.read_head(data_folder)

    # --------------------------Hypothesis definition-----------------------------------

    n_samples = 100

    # Sampling of the global coupling parameter
    stoch_sampler = StochasticSampleService(n_samples=n_samples, n_outputs=1, sampler="norm", trunc_limits={"low": 0.0},
                                            random_seed=1000, loc=10.0, scale=3.0)
    K_samples, K_sample_stats = stoch_sampler.generate_samples(stats=True)

    #
    # Manual definition of hypothesis...:
    x0_indices = [20]
    x0_values = [0.9]
    e_indices = [70]
    e_values = [0.9]
    disease_indices = x0_indices + e_indices
    n_disease = len(disease_indices)

    n_x0 = len(x0_indices)
    n_e = len(e_indices)
    all_regions_indices = np.array(range(head.number_of_regions))
    healthy_indices = np.delete(all_regions_indices, disease_indices).tolist()
    n_healthy = len(healthy_indices)
    # This is an example of x0 mixed Excitability and Epileptogenicity Hypothesis:
    hyp_x0_E = DiseaseHypothesis(head.connectivity, excitability_hypothesis={tuple(x0_indices): x0_values},
                                 epileptogenicity_hypothesis={tuple(e_indices): e_values},
                                 connectivity_hypothesis={})

    print "Running hypothesis: " + hyp_x0_E.name

    print "creating model configuration..."
    model_configuration_service = ModelConfigurationService(hyp_x0_E.get_number_of_regions())
    model_configuration = model_configuration_service.configure_model_from_hypothesis(hyp_x0_E)

    print "running LSA..."
    lsa_service = LSAService(eigen_vectors_number=None, weighted_eigenvector_sum=True)
    lsa_hypothesis = lsa_service.run_lsa(hyp_x0_E, model_configuration)

    print "running PSE LSA..."
    pse_results = pse_from_hypothesis(lsa_hypothesis, n_samples, half_range=0.1,
                                      global_coupling=[{"indices": all_regions_indices}],
                                      healthy_regions_parameters=[{"name": "x0", "indices": healthy_indices}],
                                      model_configuration=model_configuration,
                                      model_configuration_service=model_configuration_service,
                                      lsa_service=lsa_service)[0]

    plot_lsa_pse(lsa_hypothesis, model_configuration, pse_results,
                 weighted_eigenvector_sum=lsa_service.weighted_eigenvector_sum,
                 n_eig=lsa_service.eigen_vectors_number)
    # , show_flag=True, save_flag=False

    write_h5_model(prepare_for_h5(pse_results), FOLDER_RES, "PSE_LSA_results_" + lsa_hypothesis.name + ".h5")




