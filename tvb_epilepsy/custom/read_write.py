"""
    Python Demo for reading and writing
"""

import os
import h5py
import numpy
import warnings
from tvb_epilepsy.base.utils import ensure_unique_file, change_filename_or_overwrite, \
                                    read_object_from_h5_file, print_metadata, write_metadata
# TODO: solve problems with setting up a logger
from tvb_epilepsy.base.utils import initialize_logger
from tvb_epilepsy.base.epileptor_model_factory import model_build_dict
from tvb_epilepsy.base.simulators import SimulationSettings

PATIENT_VIRTUAL_HEAD = "/WORK/episense/episense-root/trunk/demo-data/Head_TREC"

import ntpath

logger = initialize_logger("log_" + ntpath.split(PATIENT_VIRTUAL_HEAD)[1])

KEY_TYPE = "EPI_Type"
KEY_VERSION = "EPI_Version"
KEY_DATE = "EPI_Last_update"
KEY_NODES = "Number_of_nodes"
KEY_SENSORS = "Number_of_sensors"
KEY_MAX = "Max_value"
KEY_MIN = "Min_value"
KEY_CHANNELS = "Number_of_channels"
KEY_SV = "Number_of_state_variables"
KEY_STEPS = "Number_of_steps"
KEY_SAMPLING = "Sampling_period"
KEY_START = "Start_time"

# Attributes to be read or written for hypothesis object and files:
hyp_attributes_dict = {"Hypothesis name": "name", "Model Epileptogenicity": "E", "Pathological Excitability": "x0",
                       "LSA Propagation Strength": "lsa_ps", "x1 Equilibria": "x1EQ",
                       "z Equilibria": "zEQ", "Afferent coupling at equilibrium": "Ceq",
                       "Connectivity": "weights", "Permittivity Coupling": "K", "Iext1": "Iext1",
                       "yc": "yc", "Critical x0": "x0cr", "x0 scaling": "rx0", "EZ hypothesis": "seizure_indices",
                       "x1EQcr": "x1EQcr", "x1LIN": "x1LIN", "x1SQ": "x1SQ",
                       "lsa_eigvals": "lsa_eigvals", "lsa_eigvects": "lsa_eigvects", "lsa_ps_tot": "lsa_ps_tot"}

# Attributes to be read or written for Epileptor models object and files:
epileptor_attributes_dict = {"model.name": "_ui_name", "model.a": "a", "model.b": "b", "model.c": "c", "model.d": "d",
                             "model.r": "r", "model.s": "s", "model.x0": "x0", "model.Iext": "Iext",
                             "model.slope": "slope", "model.Iext2": "Iext2", "model.tau": "tau", "model.aa": "aa",
                             "model.Kvf": "Kvf", "model.Kf": "Kf", "model.Ks": "Ks", "model.tt": "tt"}

epileptorDP_attributes_dict = {"model.name": "_ui_name", "model.yc": "yc", "model.x0": "x0", "model.Iext1": "Iext1",
                               "model.slope": "slope", "model.Iext2": "Iext2",
                               "model.tau2": "tau2", "model.Kvf": "Kvf", "model.Kf": "Kf", "model.K": "K",
                               "model.tau1": "tau1", "model.zmode": "zmode"}

epileptorDPrealistic_attributes_dict = {"model.name": "_ui_name", "model.yc": "yc", "model.x0": "x0",
                                        "model.Iext1": "Iext1", "model.slope": "slope", "model.Iext2": "Iext2",
                                        "model.tau2": "tau2", "model.Kvf": "Kvf", "model.Kf": "Kf", "model.K": "K",
                                        "model.tau1": "tau1", "model.zmode": "zmode", "model.pmode": "pmode"}

epileptorDP2D_attributes_dict = {"model.name": "_ui_name", "model.yc": "yc", "model.x0": "x0", "model.x0cr": "x0cr",
                                 "model.r": "r", "model.Iext1": "Iext1", "model.slope": "slope", "model.Kvf": "Kvf",
                                 "model.K": "K", "model.tau1": "tau1", "model.zmode": "zmode"}

epileptor_model_attributes_dict = {"Epileptor": epileptor_attributes_dict, "CustomEpileptor": epileptor_attributes_dict,
                                   "EpileptorDP": epileptorDP_attributes_dict,
                                   "EpileptorDPrealistic": epileptorDPrealistic_attributes_dict,
                                   "EpileptorDP2D": epileptorDP2D_attributes_dict}

# Attributes to be read or written for noise object and files:
simulation_settings_attributes_dict = {"Simulated length (ms)": "simulated_period",
                                       "Integrator type": "integrator_type",
                                       "Integration time step (ms)": "integration_step", "Time scaling": "scale_time",
                                       "Noise type": "noise_type", "Noise time scale": "noise_ntau",
                                       "Noise intensity": "noise_intensity", "Noise random seed": "noise_seed",
                                       "Monitor type": "monitor_type", "Monitor period (ms)": "monitor_sampling_period",
                                       "Monitor expressions": "monitor_expressions",
                                       "Variables names": "variables_names",
                                       "Initial conditions": "initial_conditions"}


def generate_connectivity_variant(uq_name, new_weights, new_tracts, description, new_w=None,
                                  folder=os.path.join(PATIENT_VIRTUAL_HEAD), filename="Connectivity.h5"):
    """
    In existing Connectivity H5 define Weights and Tracts variants
    """
    path = os.path.join(folder, filename)
    print "Writing a Connectivity Variant in:", path
    h5_file = h5py.File(path, 'a', libver='latest')

    try:
        group = h5_file.create_group('/' + uq_name)
        # Array doesn't seem to work in Python 3
        # group.attrs["Operations"] = [description]
        group.attrs["Operations"] = description
        h5_file.create_dataset("/" + uq_name + "/weights", data=new_weights)
        if new_w is not None:
            h5_file.create_dataset("/" + uq_name + "/w", data=new_w)
        h5_file.create_dataset("/" + uq_name + "/tract_lengths", data=new_tracts)
        h5_file.close()
    except Exception, e:
        print e
        print "You should specify a unique group name %s" % uq_name


def read_epileptogenicity(path=os.path.join(PATIENT_VIRTUAL_HEAD, "ep", "ep.h5")):
    """
    :param path: Path towards an epileptogenicity H5 file
    :return: epileptogenicity in a numpy array
    """
    print "Reading Epileptogenicity from:", path
    h5_file = h5py.File(path, 'r', libver='latest')

    print_metadata(h5_file)
    print "Structures:", h5_file["/"].keys()
    print "Values expected shape:", h5_file['/values'].shape

    values = h5_file['/values'][()]
    print "Actual values shape", values.shape

    h5_file.close()
    return values


def write_epileptogenicity_hypothesis(ep_vector, folder_name=None, file_name=None):
    """
    Store X0 values to be used when launching simulations
    """

    if file_name is None:
        file_name = "ep"

    if folder_name is None:
        folder_name = file_name

    path, overwrite = change_filename_or_overwrite(os.path.join(PATIENT_VIRTUAL_HEAD, folder_name), file_name + ".h5")
    # path = os.path.join(PATIENT_VIRTUAL_HEAD, folder_name, file_name + ".h5")
    # if os.path.exists(path):
    #     print "Ep file %s already exists. Use a different name!" % path
    #     return
    if overwrite:
        try:
            os.remove(path)
        except:
            warnings.warn("\nFile to overwrite not found!")

    os.makedirs(os.path.dirname(path))

    print "Writing an Epileptogenicity at:", path
    h5_file = h5py.File(path, 'a', libver='latest')

    write_metadata({KEY_TYPE: "ModelEpileptogenicity", KEY_NODES: ep_vector.shape[0]}, h5_file, KEY_DATE, KEY_VERSION)
    h5_file.create_dataset("/values", data=ep_vector)
    h5_file.close()


def import_sensors(src_txt_file):
    labels = numpy.loadtxt(src_txt_file, dtype=numpy.str, usecols=[0])
    locations = numpy.loadtxt(src_txt_file, dtype=numpy.float32, usecols=[1, 2, 3])
    write_sensors(labels, locations)


def write_sensors(labels, locations, folder=os.path.dirname(PATIENT_VIRTUAL_HEAD), file_name=None):
    """
    Store Sensors in a file to be shared by multiple patient virtualizations (heads)
    """
    if file_name is None:
        file_name = "SensorsSEEG_" + str(len(labels)) + ".h5"

    path, overwrite = change_filename_or_overwrite(folder, file_name)
    # path = os.path.join(os.path.dirname(PATIENT_VIRTUAL_HEAD), file_name)
    # if os.path.exists(path):
    #     print "Sensors file %s already exists. Use a different name!" % path
    #     return

    if overwrite:
        try:
            os.remove(path)
        except:
            warnings.warn("\nFile to overwrite not found!")

    print "Writing Sensors at:", path
    h5_file = h5py.File(path, 'a', libver='latest')

    write_metadata({KEY_TYPE: "SeegSensors", KEY_SENSORS: len(labels)}, h5_file, KEY_DATE, KEY_VERSION)
    h5_file.create_dataset("/labels", data=labels)
    h5_file.create_dataset("/locations", data=locations)
    h5_file.close()


# TODO: use new hypothesis
def read_simulation_settings(path=os.path.join(PATIENT_VIRTUAL_HEAD, "ep", "sim_ep.h5"), output="object",
                             hypothesis=None):
    """
    :param path: Path towards an hypothesis H5 file
    :return: hypothesis object
    """

    print "Reading simulation settings from:", path
    h5_file = h5py.File(path, 'r', libver='latest')

    print_metadata(h5_file)

    if output == "dict": #or not (isinstance(hypothesis, Hypothesis)):
        model = dict()
        if hypothesis is not None:
            warnings.warn("hypothesis is not a Hypothesis object. Returning a dictionary for model.")
    else:
        if h5_file['/' + "model.name"][()] == "Epileptor":
            model = model_build_dict[h5_file['/' + "model.name"][()]](hypothesis)
        else:
            model = model_build_dict[h5_file['/' + "model.name"][()]](hypothesis,
                                                                      zmode=h5_file['/' + "model.zmode"][()])

    if h5_file['/' + "model.name"][()] != "Epileptor":
        overwrite_fields_dict = {"zmode": numpy.array(h5_file['/' + "model.zmode"][()])}
        if h5_file['/' + "model.name"][()] == "EpileptorDPrealistic":
            overwrite_fields_dict.update({"pmode": numpy.array(h5_file['/' + "model.pmode"][()])})

    read_object_from_h5_file(model, h5_file, epileptor_model_attributes_dict[h5_file['/' + "model.name"][()]],
                             add_overwrite_fields_dict=overwrite_fields_dict)

    if output == "dict":
        sim_settings = dict()
    else:
        sim_settings = SimulationSettings()

    # overwrite_fields_dict = {"monitor_expressions": h5_file['/' + "Monitor expressions"][()].tostring().split(","),
    #                          "variables_names": h5_file['/' + "Variables names"][()].tostring().split(",")}
    overwrite_fields_dict = {"monitor_expressions": h5_file['/' + "Monitor expressions"][()].tolist(),
                             "variables_names": h5_file['/' + "Variables names"][()].tolist()}

    read_object_from_h5_file(sim_settings, h5_file, simulation_settings_attributes_dict,
                             add_overwrite_fields_dict=overwrite_fields_dict)

    h5_file.close()

    return model, sim_settings


def read_ts(path=os.path.join(PATIENT_VIRTUAL_HEAD, "ep", "ts.h5"), data=None):
    """
    :param path: Path towards a valid TimeSeries H5 file
    :return: Timeseries in a numpy array
    """
    print "Reading TimeSeries from:", path
    h5_file = h5py.File(path, 'r', libver='latest')
    print_metadata(h5_file)
    print "Structures:", h5_file["/"].keys()

    if isinstance(data, dict):

        for key in data:
            print "Data expected shape:", h5_file['/' + key].shape
            data[key] = h5_file['/' + key][()]
            print "Actual Data shape", data[key].shape
            print "First Channel sv sum", numpy.sum(data[key][:, 0])

    else:

        print "Data expected shape:", h5_file['/data'].shape

        data = h5_file['/data'][()]
        print "Actual Data shape", data.shape
        print "First Channel sv sum", numpy.sum(data[:, 0])

    total_time = int(h5_file["/"].attrs["Simulated_period"][0])
    nr_of_steps = int(h5_file["/data"].attrs["Number_of_steps"][0])
    start_time = float(h5_file["/data"].attrs["Start_time"][0])

    time = numpy.linspace(start_time, total_time, nr_of_steps)

    h5_file.close()
    return time, data


def write_ts(raw_data, sampling_period, folder=os.path.join(PATIENT_VIRTUAL_HEAD, "ep"), filename="ts_from_python.h5"):

    path, overwrite = change_filename_or_overwrite(os.path.join(folder, filename))
    # if os.path.exists(path):
    #     print "TS file %s already exists. Use a different name!" % path
    #     return

    print "Writing a TS at:", path

    if overwrite:
        try:
            os.remove(path)
        except:
            warnings.warn("\nFile to overwrite not found!")

    h5_file = h5py.File(path, 'a', libver='latest')
    write_metadata({KEY_TYPE: "TimeSeries"}, h5_file, KEY_DATE, KEY_VERSION)

    if isinstance(raw_data, dict):
        for data in raw_data:
            print "Writing " + data
            if len(raw_data[data].shape) == 2 and str(raw_data[data].dtype)[0] == "f":
                h5_file.create_dataset("/" + data, data=raw_data[data])
                write_metadata({KEY_MAX: raw_data[data].max(), KEY_MIN: raw_data[data].min(),
                                KEY_STEPS: raw_data[data].shape[0], KEY_CHANNELS: raw_data[data].shape[1],
                                KEY_SV: 1,
                                KEY_SAMPLING: sampling_period, KEY_START: 0.0
                                }, h5_file, KEY_DATE, KEY_VERSION, "/" + data)
            else:
                raise ValueError("Invalid TS data. 2D (time, nodes) numpy.ndarray of floats expected")

    elif isinstance(raw_data, numpy.ndarray):
        if len(raw_data.shape) != 2 and str(raw_data.dtype)[0] != "f":
            h5_file.create_dataset("/data", data=raw_data)
            write_metadata({KEY_MAX: raw_data.max(), KEY_MIN: raw_data.min(),
                            KEY_STEPS: raw_data.shape[0], KEY_CHANNELS: raw_data.shape[1], KEY_SV: 1,
                            KEY_SAMPLING: sampling_period, KEY_START: 0.0
                            }, h5_file, KEY_DATE, KEY_VERSION, "/data")
        else:
            raise ValueError("Invalid TS data. 2D (time, nodes) numpy.ndarray of floats expected")

    else:
        raise ValueError("Invalid TS data. Dictionary or 2D (time, nodes) numpy.ndarray of floats expected")

    h5_file.close()


def read_ts_epi(path=os.path.join(PATIENT_VIRTUAL_HEAD, "ep", "ts.h5")):
    """
    :param path: Path towards a valid TimeSeries H5 file
    :return: Timeseries in a numpy array
    """
    print "Reading TimeSeries from:", path
    h5_file = h5py.File(path, 'r', libver='latest')

    print_metadata(h5_file)
    print "Structures:", h5_file["/"].keys()
    print "Data expected shape:", h5_file['/data'].shape

    data = h5_file['/data'][()]
    print "Actual Data shape", data.shape
    print "First Channel sv sum", numpy.sum(data[:, 0, :], axis=1)

    h5_file.close()
    return data


def write_ts_epi(raw_data, sampling_period, lfp_data=None, folder=os.path.join(PATIENT_VIRTUAL_HEAD, "ep"),
                 filename="ts_from_python.h5"):

    path, overwrite = change_filename_or_overwrite(folder, filename)
    # if os.path.exists(path):
    #     print "TS file %s already exists. Use a different name!" % path
    #     return

    if raw_data is None or len(raw_data.shape) != 3:
        print "Invalid TS data 3D (time, regions, sv) expected"
        return

    print "Writing a TS at:", path
    if type(lfp_data) == int:
        lfp_data = raw_data[:, :, lfp_data[1]]
        raw_data[:, :, lfp_data[1]] = []
    elif isinstance(lfp_data, list):
        lfp_data = raw_data[:, :, lfp_data[1]] - raw_data[:, :, lfp_data[0]]
    elif isinstance(lfp_data, numpy.ndarray):
        lfp_data = lfp_data.reshape((lfp_data.shape[0], lfp_data.shape[1], 1))
    else:
        print "Invalid lfp_data 3D (time, regions, sv) expected"

    if overwrite:
        try:
            os.remove(path)
        except:
            warnings.warn("\nFile to overwrite not found!")

    h5_file = h5py.File(path, 'a', libver='latest')
    h5_file.create_dataset("/data", data=raw_data)
    h5_file.create_dataset("/lfpdata", data=lfp_data)

    write_metadata({KEY_TYPE: "TimeSeries"}, h5_file, KEY_DATE, KEY_VERSION)
    write_metadata({KEY_MAX: raw_data.max(), KEY_MIN: raw_data.min(),
                    KEY_STEPS: raw_data.shape[0], KEY_CHANNELS: raw_data.shape[1], KEY_SV: raw_data.shape[2],
                    KEY_SAMPLING: sampling_period, KEY_START: 0.0
                    }, h5_file, KEY_DATE, KEY_VERSION, "/data")
    write_metadata({KEY_MAX: lfp_data.max(), KEY_MIN: lfp_data.min(),
                    KEY_STEPS: lfp_data.shape[0], KEY_CHANNELS: lfp_data.shape[1], KEY_SV: 1,
                    KEY_SAMPLING: sampling_period, KEY_START: 0.0
                    }, h5_file, KEY_DATE, KEY_VERSION, "/lfpdata")
    h5_file.close()


def write_ts_seeg_epi(seeg_data, sampling_period, folder=os.path.join(PATIENT_VIRTUAL_HEAD, "ep"),
                 filename="ts_from_python.h5"):

    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        print "TS file %s does not exist. First define the raw data!" % path
        return

    sensors_name = "SeegSensors-" + str(seeg_data.shape[1])
    print "Writing a TS at:", path, sensors_name

    try:
        h5_file = h5py.File(path, 'a', libver='latest')
        h5_file.create_dataset("/" + sensors_name, data=seeg_data)

        write_metadata({KEY_MAX: seeg_data.max(), KEY_MIN: seeg_data.min(),
                        KEY_STEPS: seeg_data.shape[0], KEY_CHANNELS: seeg_data.shape[1], KEY_SV: 1,
                        KEY_SAMPLING: sampling_period, KEY_START: 0.0
                        }, h5_file, KEY_DATE, KEY_VERSION, "/" + sensors_name)
        h5_file.close()
    except Exception, e:
        print e
        print "Seeg dataset already written %s" % sensors_name


if __name__ == "__main__":
    read_epileptogenicity()
    print "----------------"
    read_ts()
    print "----------------"

    # Simulating edit of a Connectivity.
    # It need to have the same number as the original connectivity, only weights and tracts changed.
    random_weights = numpy.random.random((88, 88))
    random_tracts = numpy.random.random((88, 88))
    generate_connectivity_variant('random3', random_weights, random_tracts, "Description of connectivity")
    print "----------------"

    # Define the X0 vector, that can be later used as input in a simulation from GUI
    random_x0 = numpy.random.random((88,))
    write_epileptogenicity_hypothesis("ep-random", random_x0)
    print "----------------"

    # Write TS
    random_ts = numpy.random.random((2000, 88, 3)).astype(numpy.float32)
    write_ts(random_ts, sampling_period=0.5)

    random_seeg = numpy.random.random((1000, 50)).astype(numpy.float32)
    write_ts_seeg_epi(random_seeg, 2.0)
    print "-----------------"

    # Import Sensors from TXT file
    src_sensors_file = "/Users/lia.domide/Downloads/Denis/sEEG_position.txt"
    import_sensors(src_sensors_file)
