from shutil import copyfile

from tvb_fit.plot.plotter import Plotter
from tvb_fit.samplers.stan.stan_interface import StanInterface
from tvb_fit.samplers.stan.stan_factory import *

from tvb_scripts.utils.log_error_utils import raise_value_error, warning
from tvb_scripts.utils.data_structures_utils import construct_import_path, ensure_list, isequal_string
from tvb_scripts.utils.command_line_utils import execute_command
from tvb_scripts.utils.file_utils import change_filename_or_overwrite_with_wildcard
from tvb_scripts.io.csv import parse_csv_in_cols



class CmdStanInterface(StanInterface):

    def __init__(self, model_name=None, model=None, model_code=None, model_dir="", model_code_path="", model_data_path="",
                 output_filepath=None, diagnostic_filepath=None, summary_filepath=None, command_filepath=None,
                 fitmethod="sample", random_seed=12345, init="random", config=None, **options):
        super(CmdStanInterface, self).__init__(model_name, model, model_code, model_dir, model_code_path,
                                               model_data_path, fitmethod, config)
        if not os.path.isfile(os.path.join(self.config.generic.CMDSTAN_PATH, 'runCmdStanTests.py')):
            raise_value_error('Please provide CmdStan path in config.generic.CMDSTAN_PATH!'
                              '\nCurrent config.generic.CMDSTAN_PATH is wrong!: %s' % self.config.generic.CMDSTAN_PATH)
        self.path = self.config.generic.CMDSTAN_PATH
        self.set_output_files(output_filepath, diagnostic_filepath, summary_filepath, command_filepath,
                              base_path=model_dir, check_files=False)
        self.assert_fitmethod()
        self.command = ""
        self.options = {"init": init, "random_seed": random_seed}
        self.options = self.set_options(**options)
        self.context_str = "from " + construct_import_path(__file__) + " import " + self.__class__.__name__
        self.create_str = self.__class__.__name__ + "()"

    def assert_fitmethod(self):
        if self.fitmethod.lower().find("sampl") >= 0:  # for sample or sampling
            self.fitmethod = "sample"
        elif self.fitmethod.lower().find("v") >= 0:  # for variational or vb or advi
            self.fitmethod = "variational"
        elif self.fitmethod.lower().find("opt") >= 0:  # for optimization or optimizing or optimize
            self.fitmethod = "optimize"
        elif self.fitmethod.lower().find("diag") >= 0:  # for diagnose or diagnosing
            self.fitmethod = "diagnose"
        else:
            raise_value_error(self.fitmethod + " does not correspond to one of the input methods:\n" +
                              "sample, variational, optimize, diagnose")

    def set_output_files(self, output_filepath=None, diagnostic_filepath=None, summary_filepath=None,
                         command_filepath=None, base_path="",  check_files=False, overwrite_output_files=False,
                         update=False):
        if not os.path.isdir(base_path):
            base_path = self.config.out.FOLDER_RES
        if output_filepath is None or update:
            output_filepath = os.path.join(base_path, STAN_OUTPUT_OPTIONS["file"])
        if diagnostic_filepath is None or update:
            diagnostic_filepath = os.path.join(base_path, STAN_OUTPUT_OPTIONS["diagnostic_file"])
        if summary_filepath is None or update:
            summary_filepath = os.path.join(base_path, "stan_summary.csv")
        if command_filepath is None or update:
            command_filepath = os.path.join(base_path, "command.txt")
        if check_files:
            output_filepath = change_filename_or_overwrite_with_wildcard(output_filepath.split(".csv")[0],
                                                                              overwrite_output_files) + ".csv"
            diagnostic_filepath = change_filename_or_overwrite_with_wildcard(diagnostic_filepath.split(".csv")[0],
                                                                             overwrite_output_files) + ".csv"
            summary_filepath = change_filename_or_overwrite_with_wildcard(summary_filepath.split(".csv")[0],
                                                                          overwrite_output_files) + ".csv"
            command_filepath = change_filename_or_overwrite_with_wildcard(command_filepath.split(".txt")[0],
                                                                          overwrite_output_files) + ".txt"
        self.output_filepath = output_filepath
        self.diagnostic_filepath = diagnostic_filepath
        self.summary_filepath = summary_filepath
        self.command_filepath = command_filepath

    def set_model_data(self, debug=0, simulate=0, **kwargs):
        model_data = super(CmdStanInterface, self).set_model_data(debug, simulate, **kwargs)
        model_data_path = self.model_data_path.split(".", -1)[0] + ".R"
        self.write_model_data_to_file(model_data, model_data_path=model_data_path)
        return model_data_path

    def set_options(self, **options):
        self.fitmethod = options.get("method", self.fitmethod)
        self.assert_fitmethod()
        self.options = generate_cmdstan_options(self.fitmethod, **options)

    def set_model_from_file(self, **kwargs):
        self.model_path = kwargs.pop("model_path", self.model_path)
        if not (os.path.exists(self.model_path)):
            raise_value_error("Failed to load the model from file: " + str(self.model_path) + " !")

    def compile_stan_model(self, save_model=True, **kwargs):
        self.model_code_path = kwargs.pop("model_code_path", self.model_code_path)
        self.logger.info("Compiling model...")
        mode_code_path = self.model_code_path.split(".stan", 1)[0]
        command = "make CC=" + self.config.generic.C_COMPILER + " " + mode_code_path + \
                  " && " + "chmod +x " + mode_code_path
        self.compilation_time = execute_command(command, cwd=self.path, shell=True)[1]
        self.logger.info(str(self.compilation_time) + ' sec required to compile')
        if save_model:
            self.model_path = kwargs.pop("model_path", self.model_path)
            if self.model_path != self.model_code_path.split(".stan", 1)[0]:
                copyfile(self.model_code_path.split(".stan", 1)[0], self.model_path)

    def read_output(self, output_filepath=None, **kwargs):
        if not isinstance(output_filepath, basestring):
            output_filepath = self.output_filepath
        samples = self.read_output_samples(output_filepath, add_wildcard=True, **kwargs)
        est = self.compute_estimates_from_samples(samples)
        summary = self.get_summary(output_filepath=output_filepath)
        return est, samples, summary

    def stan_summary(self, output_filepath=None, add_wildcard=True):
        if not isinstance(output_filepath, (list, tuple)):  # if not a list of files
            if not isinstance(output_filepath, basestring):  # if neither a path
                output_filepath = self.output_filepath       # set the default path
            if add_wildcard:  # add wildcard if flag
                if output_filepath.split(".csv")[0][-1] != "*":
                    output_filepath = output_filepath.replace(".csv", "*.csv")
        compute_stan_summary(output_filepath, self.summary_filepath, self.path)

    def get_summary(self, output_filepath=None):
        if os.path.isfile(self.summary_filepath):
            return parse_csv_in_cols(self.summary_filepath)
        else:
            warning("No summary csv file! Making an effort to compute summary!")
            try:
                self.stan_summary(output_filepath=output_filepath)
                return parse_csv_in_cols(self.summary_filepath)
            except:
                warning("Failed to compute summary!")
                return None

    def get_summary_stats(self, stats, summary=None,  output_filepath=None):
        if summary is None:
            summary = self.get_summary(output_filepath=output_filepath)
        if isinstance(summary, dict):
            out_stats = {}
            for stat in ensure_list(stats):
                out_stats[stat] = summary.get(stat, None)
            return out_stats
        else:
            return None

    def get_Rhat(self, summary=None, output_filepath=None):
        return self.get_summary_stats("Rhat", summary, output_filepath=output_filepath)

    def prepare_fit(self, debug=0, simulate=0, overwrite_output_files=False, **kwargs):
        # Confirm output files and check if overwriting is necessary
        self.set_output_files(kwargs.pop("output_filepath", self.output_filepath),
                              kwargs.pop("diagnostic_filepath", self.diagnostic_filepath),
                              kwargs.pop("summary_filepath", self.summary_filepath),
                              kwargs.pop("command_path", self.command_filepath),
                              kwargs.pop("output_path", ""), True, overwrite_output_files, True)
        self.model_path = kwargs.pop("model_path", self.model_path)
        self.fitmethod = kwargs.pop("fitmethod", self.fitmethod)
        self.fitmethod = kwargs.pop("method", self.fitmethod)
        self.set_options(**kwargs)
        self.command, self.output_filepath, self.diagnostic_filepath = \
            generate_cmdstan_fit_command(self.fitmethod, self.options, self.model_path,
                                         self.set_model_data(debug, simulate, **kwargs),
                                         self.output_filepath, self.diagnostic_filepath)
        self.logger.info("Model fitting with " + self.fitmethod +
                         " method of model: " + self.model_path + "...")
        with open(self.command_filepath, "w") as text_file:
            text_file.write(self.command)

    def fit(self, debug=0, simulate=0, return_output=True, plot_HMC=True, overwrite_output_files=False, plot_warmup=1,
            **kwargs):
        num_warmup = kwargs.get("num_warmup", 0)
        self.prepare_fit(debug, simulate, overwrite_output_files, **kwargs)
        self.fitting_time = execute_command(self.command.replace("\t", ""), shell=True)[1]
        self.logger.info(str(self.fitting_time) + ' sec required to ' + self.fitmethod + "!")
        self.logger.info("Computing stan summary...")
        self.stan_summary()
        if return_output:
            est, samples, summary = self.read_output(kwargs)
            if plot_HMC and self.fitmethod.find("sampl") >= 0 and \
                isequal_string(self.options.get("algorithm", "None"), "HMC"):
                Plotter(self.config).plot_HMC(samples, skip_samples=kwargs.pop("skip_samples", num_warmup *
                                                                                (1-kwargs.get("plot_warmup", True))))
            return est, samples, summary
        else:
            return None, None, None


def compute_stan_summary(output_filepath, summary_filepath, cwd_path, overwrite_summary_file=False):
    summary_filepath = change_filename_or_overwrite_with_wildcard(summary_filepath.split(".csv")[0],
                                                                  overwrite_summary_file) + ".csv"
    command = cwd_path + "/" + "bin/stansummary " + output_filepath + " --csv_file=" + summary_filepath
    execute_command(command, cwd=cwd_path, shell=True)

def stan_summary(output_filepath, summary_filepath, cwd_path):
    compute_stan_summary(output_filepath, summary_filepath, cwd_path)
    return parse_csv_in_cols(summary_filepath)