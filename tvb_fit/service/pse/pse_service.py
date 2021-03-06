
from abc import abstractmethod, ABCMeta

import numpy as np

from tvb_fit.base.utils.log_error_utils import initialize_logger, raise_value_error


class ABCPSEService(object):
    __metaclass__ = ABCMeta

    logger = initialize_logger(__name__)

    def __init__(self):
        self.params_vals = []
        self.params_paths = []
        self.params_indices = []
        self.params_names = []
        self.n_params_vals = []
        self.n_params = 0

    def run_pse(self, conn_matrix, grid_mode=False, *kwargs):
        results = []
        execution_status = []
        loop_tenth = 1
        for iloop in range(self.n_loops):
            params = self.params_vals[iloop]
            if iloop == 0 or iloop + 1 >= loop_tenth * self.n_loops / 10.0:
                print "\nExecuting loop " + str(iloop + 1) + " of " + str(self.n_loops)
                if iloop > 0:
                    loop_tenth += 1

            status = False
            output = None
            # try:
            status, output = self.run(params, conn_matrix, *kwargs)
            # except:
            #     pass
            # if not status:
            #     self.logger.warning("\nExecution of loop " + str(iloop) + " failed!")
            results.append(output)
            execution_status.append(status)
        if grid_mode:
            results = np.reshape(np.array(results, dtype="O"), tuple(self.n_params_vals))
            execution_status = np.reshape(np.array(execution_status), tuple(self.n_params_vals))
        return results, execution_status

    @abstractmethod
    def run_pse_parallel(self):
        # TODO: start each loop on a separate process, gather results and return them
        pass

    @abstractmethod
    def run(self, *kwargs):
        pass

    @abstractmethod
    def prepare_run_results(self, *kwargs):
        pass

    def prepare_params(self, params_pse):
        if isinstance(params_pse, list):
            temp = []
            for param in params_pse:
                self.params_paths.append(param["path"])
                temp2 = param["samples"].flatten()
                temp.append(temp2)
                self.n_params_vals.append(temp2.size)
                indices = param.get("indices", [])
                self.params_indices.append(indices)
                self.params_names.append(param.get("name", param["path"].rsplit('.', 1)[-1] + str(indices)))
            self.n_params_vals = np.array(self.n_params_vals)
            self.n_params = len(self.params_paths)
            if not (np.all(self.n_params_vals == self.n_params_vals[0])):
                raise_value_error("\nNot all parameters have the same number of samples!: " +
                                  "\n" + str(self.params_paths) + " = " + str(self.n_params_vals))
            else:
                self.n_params_vals = self.n_params_vals[0]
            self.params_vals = np.vstack(temp).T
            self.params_paths = np.array(self.params_paths)
            self.params_indices = np.array(self.params_indices)
            self.n_loops = self.params_vals.shape[0]
            print "\nGenerated a parameter search exploration for " + str("lsa/sim task") + ","
            print "with " + str(self.n_params) + " parameters of " + str(self.n_params_vals) + " values each,"
            print "leading to " + str(self.n_loops) + " total execution loops"
        else:
            self.logger.warning("\nparams_pse is not a list of tuples!")

    @abstractmethod
    def update_model_config(self, params, conn_matrix=None, model_config_builder_input=None, **kwargs):
            #return model_config,  # i.e., a tuple
      pass

    def set_object_attribute_recursively(self, object, values, path, indices):
        # If there is more than one levels...
        if len(path) > 1:
            # ...call the function recursively
            self.set_object_attribute_recursively(getattr(object, path[0]), values, path[1:], indices)
        else:
            # ...else, set the parameter values for the specified indices
            temp = getattr(object, path[0])
            if len(indices) > 0:
                temp[indices] = values  # index has to be linear... i.e., 1D...
            else:
                temp = values
            setattr(object, path[0], temp)

    def update_object(self, object, params, object_type=None):
        if not(isinstance(object_type, basestring)):
            object_type = object.__class__.__name__
        for i, path in enumerate(self.params_paths):
            path = path.split(".")
            if path[0] == object_type:
                self.set_object_attribute_recursively(object, params[i], path[1:], self.params_indices[i])