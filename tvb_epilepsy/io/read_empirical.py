"""
    Python Demo for reading and writing custom entities
"""

import os

import numpy
from scipy.io import loadmat

from tvb_epilepsy.base.model.vep.sensors import Sensors
from tvb_epilepsy.custom.read_write import write_ts, write_ts_seeg_epi, PATIENT_VIRTUAL_HEAD
from tvb_epilepsy.io.h5_reader import H5Reader
from tvb_epilepsy.io.h5_writer import H5Writer


def correlate_sensors(empirical_file="/Users/lia.domide/Downloads/TRECempirical/110223B-EEX_0004.EEG.mat",
                      existing_ep_file="/WORK/episense/episense-root/trunk/demo-data/SensorsSEEG_125.h5"):
    data = loadmat(empirical_file)
    desired_labels = [str(i).strip().lower() for i in data["channel_names"]]
    reader = H5Reader()
    labels, locations = reader.read_sensors_of_type(existing_ep_file, "SEEG")
    new_labels = []
    new_locations = []
    ignored_indices = []
    for i, label in enumerate(desired_labels):
        if label not in labels:
            print "Ignored channel", label
            ignored_indices.append(i)
            continue
        idx = numpy.where(labels == label)
        new_labels.append(label)
        new_locations.append(locations[idx])
    H5Writer().write_sensors(Sensors(new_labels, new_locations),
                             os.path.join(os.path.dirname(PATIENT_VIRTUAL_HEAD),
                                                "SensorsSEEG_" + str(len(labels)) + ".h5"))
    return ignored_indices


def import_seeg(empirical_file="/Users/lia.domide/Downloads/TRECempirical/110223B-EEX_0004.EEG.mat",
                ignored_indices=[], ts_path=os.path.join(PATIENT_VIRTUAL_HEAD, "ep", "ts_empirical.h5")):
    data = loadmat(empirical_file)
    sampling_period = 1000 / data["sampling_rate_hz"][0]
    seeg_data = data['data']
    print "Ignoring ", ignored_indices
    seeg_data = numpy.delete(seeg_data, ignored_indices, axis=0)
    seeg_data = seeg_data.transpose()
    print seeg_data.min(), seeg_data.max()
    raw_data = numpy.zeros((1000, 88, 3))
    write_ts(raw_data, sampling_period, ts_path)
    (folder_path, filename) = os.path.split(ts_path)
    write_ts_seeg_epi(seeg_data, sampling_period, folder=folder_path, filename=filename)


if __name__ == "__main__":
    ignored_indices = correlate_sensors()
    print "Ignored indices ", ignored_indices
    print "-----------------"
    import_seeg(ignored_indices=ignored_indices)
