"""
Read VEP related entities from custom format and data-structures
"""

import os
import h5py
from tvb_epilepsy.base.model_vep import Connectivity, Surface, Sensors, Head
from tvb_epilepsy.base.readers import ABCReader
from tvb_epilepsy.base.utils import calculate_projection, initialize_logger


class CustomReader(ABCReader):
    LOG = initialize_logger(__name__)

    def read_connectivity(self, h5_path):
        """
        :param h5_path: Path towards a custom Connectivity H5 file
        :return: Weights, Tracts, Region centers
        """
        self.LOG.info("Reading a Connectivity from: " + h5_path)
        h5_file = h5py.File(h5_path, 'r', libver='latest')

        self.LOG.debug("Structures: " + str(h5_file["/"].keys()))
        self.LOG.debug("Weights shape:" + str(h5_file['/weights'].shape))

        weights = h5_file['/weights'][()]
        tract_lengths = h5_file['/tract_lengths'][()]
        # TODO: should change to English centers than French centres!
        region_centers = h5_file['/centres'][()]
        region_labels = h5_file['/region_labels'][()]
        orientations = h5_file['/orientations'][()]
        hemispheres = h5_file['/hemispheres'][()]

        h5_file.close()
        return Connectivity(h5_path, weights, tract_lengths, region_labels, region_centers, hemispheres, orientations)

    def read_cortical_surface(self, h5_path):
        self.LOG.info("Reading Surface from " + h5_path)
        h5_file = h5py.File(h5_path, 'r', libver='latest')
        vertices = h5_file['/vertices'][()]
        triangles = h5_file['/triangles'][()]
        vertex_normals = h5_file['/vertex_normals'][()]
        h5_file.close()
        return Surface(vertices, triangles, vertex_normals)

    def _read_data_field(self, h5_path):
        self.LOG.info("Reading 'data' from H5 " + h5_path)
        h5_file = h5py.File(h5_path, 'r', libver='latest')
        data = h5_file['/data'][()]
        h5_file.close()
        return data

    def read_region_mapping(self, h5_path):
        return self._read_data_field(h5_path)

    def read_volume_mapping(self, h5_path):
        return self._read_data_field(h5_path)

    def read_t1(self, h5_path):
        return self._read_data_field(h5_path)

    def read_sensors(self, h5_path, s_type):
        self.LOG.info("Reading Sensors from: " + h5_path)
        h5_file = h5py.File(h5_path, 'r', libver='latest')

        labels = h5_file['/labels'][()]
        locations = h5_file['/locations'][()]

        h5_file.close()
        return Sensors(labels, locations, s_type=s_type)

    def read_projection(self, path, s_type):
        raise NotImplementedError()

    def read_head(self, root_folder, name=''):
        conn = self.read_connectivity(os.path.join(root_folder, "Connectivity.h5"))
        srf = self.read_cortical_surface(os.path.join(root_folder, "CorticalSurface.h5"))
        rm = self.read_region_mapping(os.path.join(root_folder, "RegionMapping.h5"))
        vm = self.read_volume_mapping(os.path.join(root_folder, "VolumeMapping.h5"))
        t1 = self.read_volume_mapping(os.path.join(root_folder, "StructuralMRI.h5"))

        s_114 = self.read_sensors(os.path.join(root_folder, "SensorsSEEG_114.h5"), Sensors.TYPE_SEEG)
        s_125 = self.read_sensors(os.path.join(root_folder, "SensorsSEEG_125.h5"), Sensors.TYPE_SEEG)
        seeg_sensors_dict = {s_114: calculate_projection(s_114, conn),
                             s_125: calculate_projection(s_125, conn)}
        eeg_sensors_dict = {}
        meg_sensors_dict = {}

        return Head(conn, srf, rm, vm, t1, name, eeg_sensors_dict, meg_sensors_dict, seeg_sensors_dict)

    def read_epileptogenicity(self, root_folder, name="ep"):
        """
        :param
            root_folder: Path towards a valid custom Epileptogenicity H5 file
            name: the name of the hypothesis
        :return: Timeseries in a numpy array
        """
        path = os.path.join(root_folder, name, name + ".h5")

        print "Reading Epileptogenicity from:", path
        h5_file = h5py.File(path, 'r', libver='latest')

        print "Structures:", h5_file["/"].keys()
        print "Values expected shape:", h5_file['/values'].shape

        values = h5_file['/values'][()]
        print "Actual values shape", values.shape

        h5_file.close()
        return values
