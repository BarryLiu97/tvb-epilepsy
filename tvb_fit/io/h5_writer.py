# -*- coding: utf-8 -*-

import os
import h5py
import numpy
from tvb_fit.base.utils.log_error_utils import raise_value_error
from tvb_fit.base.utils.file_utils import change_filename_or_overwrite, write_metadata
from tvb_fit.base.model.virtual_patient.connectivity import ConnectivityH5Field
from tvb_fit.base.model.virtual_patient.sensors import SensorsH5Field
from tvb_fit.base.model.virtual_patient.surface import SurfaceH5Field
from tvb_fit.base.model.timeseries import Timeseries
from tvb_fit.io.h5_writer_base import H5WriterBase

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


class H5Writer(H5WriterBase):

    # TODO: write variants.
    def write_connectivity(self, connectivity, path):
        """
        :param connectivity: Connectivity object to be written in H5
        :param path: H5 path to be written
        """
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')

        h5_file.create_dataset(ConnectivityH5Field.WEIGHTS, data=connectivity.weights)
        h5_file.create_dataset(ConnectivityH5Field.TRACTS, data=connectivity.tract_lengths)
        h5_file.create_dataset(ConnectivityH5Field.CENTERS, data=connectivity.centres)
        h5_file.create_dataset(ConnectivityH5Field.REGION_LABELS, data=connectivity.region_labels)
        h5_file.create_dataset(ConnectivityH5Field.ORIENTATIONS, data=connectivity.orientations)
        h5_file.create_dataset(ConnectivityH5Field.HEMISPHERES, data=connectivity.hemispheres)

        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "Connectivity")
        h5_file.attrs.create("Number_of_regions", str(connectivity.number_of_regions))

        if connectivity.normalized_weights.size > 0:
            dataset = h5_file.create_dataset("normalized_weights/" + ConnectivityH5Field.WEIGHTS,
                                             data=connectivity.normalized_weights)
            dataset.attrs.create("Operations", "Removing diagonal, normalizing with 95th percentile, and ceiling to it")

        self.logger.info("Connectivity has been written to file: %s" % path)
        h5_file.close()

    def write_sensors(self, sensors, path):
        """
        :param sensors: Sensors object to write in H5
        :param path: H5 path to be written
        """
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')

        h5_file.create_dataset(SensorsH5Field.LABELS, data=sensors.labels)
        h5_file.create_dataset(SensorsH5Field.LOCATIONS, data=sensors.locations)
        h5_file.create_dataset(SensorsH5Field.NEEDLES, data=sensors.needles)

        gain_dataset = h5_file.create_dataset(SensorsH5Field.GAIN_MATRIX, data=sensors.gain_matrix)
        gain_dataset.attrs.create("Max", str(sensors.gain_matrix.max()))
        gain_dataset.attrs.create("Min", str(sensors.gain_matrix.min()))

        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "Sensors")
        h5_file.attrs.create("Number_of_sensors", str(sensors.number_of_sensors))
        h5_file.attrs.create("Sensors_subtype", sensors.s_type)

        self.logger.info("Sensors have been written to file: %s" % path)
        h5_file.close()

    def write_surface(self, surface, path):
        """
        :param surface: Surface object to write in H5
        :param path: H5 path to be written
        """
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')

        h5_file.create_dataset(SurfaceH5Field.VERTICES, data=surface.vertices)
        h5_file.create_dataset(SurfaceH5Field.TRIANGLES, data=surface.triangles)
        h5_file.create_dataset(SurfaceH5Field.VERTEX_NORMALS, data=surface.vertex_normals)

        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "Surface")
        h5_file.attrs.create("Surface_subtype", surface.surface_subtype.upper())
        h5_file.attrs.create("Number_of_triangles", surface.triangles.shape[0])
        h5_file.attrs.create("Number_of_vertices", surface.vertices.shape[0])
        h5_file.attrs.create("Voxel_to_ras_matrix", str(surface.vox2ras.flatten().tolist())[1:-1].replace(",", ""))

        self.logger.info("Surface has been written to file: %s" % path)
        h5_file.close()

    def write_region_mapping(self, region_mapping, path, n_regions, subtype="Cortical"):
        """
            :param region_mapping: region_mapping array to write in H5
            :param path: H5 path to be written
        """
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')

        h5_file.create_dataset("data", data=region_mapping)

        data_length = len(region_mapping)
        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "RegionMapping")
        h5_file.attrs.create("Connectivity_parcel", "Connectivity-%d" % n_regions)
        h5_file.attrs.create("Surface_parcel", "Surface-%s-%d" % (subtype.capitalize(), data_length))
        h5_file.attrs.create("Length_data", data_length)

        self.logger.info("Region mapping has been written to file: %s" % path)
        h5_file.close()

    def write_volume(self, volume_data, path, type, n_regions):
        """
            :param t1: t1 array to write in H5
            :param path: H5 path to be written
        """
        shape = volume_data.shape
        if len(shape) < 3:
            shape = (0, 0, 0)
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')
        h5_file.create_dataset("data", data=volume_data)
        h5_file.attrs.create("Connectivity_parcel", "Connectivity-%d" % n_regions)
        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "VolumeData")
        h5_file.attrs.create("Length_x", str(shape[0]))
        h5_file.attrs.create("Length_y", str(shape[1]))
        h5_file.attrs.create("Length_z", str(shape[2]))
        h5_file.attrs.create("Type", type.upper())

        self.logger.info("%s volume has been written to file: %s" % (type, path))
        h5_file.close()

    def write_t1(self, t1_data, path, n_regions):
        self.write_volume(t1_data, path, "STRUCTURAL", n_regions)

    def write_volume_mapping(self, volume_mapping_data, path, n_regions):
        self.write_volume(volume_mapping_data, path, "MAPPING", n_regions)

    def write_head(self, head, path):
        """
        :param head: Head object to be written
        :param path: path to head folder
        """
        self.logger.info("Starting to write Head folder: %s" % path)

        if not (os.path.isdir(path)):
            os.mkdir(path)
        n_regions = head.connectivity.number_of_regions
        self.write_connectivity(head.connectivity, os.path.join(path, "Connectivity.h5"))
        self.write_surface(head.cortical_surface, os.path.join(path, "CorticalSurface.h5"))
        self.write_surface(head.subcortical_surface, os.path.join(path, "SubcorticalSurface.h5"))
        self.write_region_mapping(head.cortical_region_mapping, os.path.join(path, "CorticalRegionMapping.h5"),
                                  n_regions= head.connnectivity.number_of_regions, subtype="Cortical")
        self.write_region_mapping(head.subcortical_region_mapping, os.path.join(path, "SubcorticalRegionMapping.h5"),
                                  n_regions, "Subcortical")
        self.write_volume_mapping(self, head.volume_mapping, os.path.join(path, "VolumeMapping.h5"), n_regions)
        self.write_t1(self, head.t1_background, os.path.join(path, "StructuralMRI.h5"), n_regions)
        for sensor_list in (head.sensorsSEEG, head.sensorsEEG, head.sensorsMEG):
            for sensors in sensor_list:
                self.write_sensors(sensors, os.path.join(path, "Sensors%s_%s.h5" %
                                                         (sensors.s_type.value, sensors.number_of_sensors)))

        self.logger.info("Successfully wrote Head folder at: %s" % path)

    def write_model_configuration_builder(self, model_configuration_builder, path, nr_regions=None):
        """
        :param model_configuration_builder: ModelConfigurationService object to write in H5
        :param path: H5 path to be written
        """
        self.write_object_to_file(path, model_configuration_builder, "HypothesisModel", nr_regions)

    def write_model_configuration(self, model_configuration, path, nr_regions=None):
        """
        :param model_configuration: EpileptorModelConfiguration object to write in H5
        :param path: H5 path to be written
        """
        self.write_object_to_file(path, model_configuration, "HypothesisModel", nr_regions)

    # TODO: can this be visualized? should we keep groups?
    def write_simulation_settings(self, simulation_settings, path, nr_regions=None):
        """
        :param simulation_settings: SimulationSettings object to write in H5
        :param path: H5 path to be written
        """
        self.write_object_to_file(path, simulation_settings, "HypothesisModel", nr_regions)

    def write_simulator_model(self, simulator_model, path, nr_regions=None):
        # simulator_model.variables_of_interest = numpy.array(simulator_model.variables_of_interest)
        # simulator_model.state_variables = numpy.array(simulator_model.state_variables)
        self.write_object_to_file(path, simulator_model, "HypothesisModel", nr_regions)

    def write_pse_service(self, pse_service, path):
        """
        :param pse_service: PSEService object to write in H5
        :param path: H5 path to be written
        """
        if "params_vals" not in dir(pse_service):
            params_samples = pse_service.pse_params.T
        else:
            params_samples = pse_service.params_vals

        pse_dict = {"task": pse_service.task,
                    "params_names": pse_service.params_names,
                    "params_paths": pse_service.params_paths,
                    "params_indices": numpy.array([str(inds) for inds in pse_service.params_indices], dtype="S"),
                    "params_samples": params_samples}

        self.write_dictionary(pse_dict, path)

    def write_sensitivity_analysis_service(self, sensitivity_service, path):
        """
        :param sensitivity_service: SensitivityAnalysisService object to write in H5
        :param path: H5 path to be written
        """
        sensitivity_service_dict = {"method": sensitivity_service.method,
                                    "calc_second_order": sensitivity_service.calc_second_order,
                                    "conf_level": sensitivity_service.conf_level,
                                    "n_inputs": sensitivity_service.n_inputs,
                                    "n_outputs": sensitivity_service.n_outputs,
                                    "input_names": sensitivity_service.input_names,
                                    "output_names": sensitivity_service.output_names,
                                    "input_bounds": sensitivity_service.input_bounds,
                                    }

        self.write_dictionary(sensitivity_service_dict, path)

    def write_dictionary_to_group(self, dictionary, group):
        group.attrs.create(self.H5_TYPE_ATTRIBUTE, "HypothesisModel")
        group.attrs.create(self.H5_SUBTYPE_ATTRIBUTE, dictionary.__class__.__name__)
        for key, value in dictionary.items():
            try:
                if isinstance(value, numpy.ndarray) and value.size > 0:
                    group.create_dataset(key, data=value)
                else:
                    if isinstance(value, list) and len(value) > 0:
                        group.create_dataset(key, data=value)
                    else:
                        group.attrs.create(key, value)
            except:
                self.logger.warning("Did not manage to write " + key + " to h5 file " + str(group) + " !")

    def write_dictionary(self, dictionary, path):
        """
        :param dictionary: dictionary to write in H5
        :param path: H5 path to be written
        """
        self.logger.info("Writing a dictionary at:\n" + path)
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')
        self.write_dictionary_to_group(dictionary, h5_file)
        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "HypothesisModel")
        h5_file.attrs.create(self.H5_SUBTYPE_ATTRIBUTE, dictionary.__class__.__name__)
        h5_file.close()

    def write_list_of_dictionaries(self, list_of_dicts, path):
        self.logger.info("Writing a list of dictionaries at:\n" + path)
        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')
        for idict, dictionary in enumerate(list_of_dicts):
            idict_str = str(idict)
            h5_file.create_group(idict_str)
            self.write_dictionary_to_group(dictionary, h5_file[idict_str])
        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "HypothesisModel")
        h5_file.attrs.create(self.H5_SUBTYPE_ATTRIBUTE, "list")
        h5_file.close()

    def write_ts(self, raw_data, sampling_period, path):
        path = change_filename_or_overwrite(path)

        self.logger.info("Writing a TS at:\n" + path)
        h5_file = h5py.File(path, 'a', libver='latest')
        write_metadata({KEY_TYPE: "TimeSeries"}, h5_file, KEY_DATE, KEY_VERSION)
        if isinstance(raw_data, dict):
            for data in raw_data:
                if len(raw_data[data].shape) == 2 and str(raw_data[data].dtype)[0] == "f":
                    h5_file.create_dataset("/" + data, data=raw_data[data])
                    write_metadata({KEY_MAX: raw_data[data].max(), KEY_MIN: raw_data[data].min(),
                                    KEY_STEPS: raw_data[data].shape[0], KEY_CHANNELS: raw_data[data].shape[1],
                                    KEY_SV: 1, KEY_SAMPLING: sampling_period, KEY_START: 0.0}, h5_file, KEY_DATE,
                                   KEY_VERSION, "/" + data)
                else:
                    raise_value_error("Invalid TS data. 2D (time, nodes) numpy.ndarray of floats expected")
        elif isinstance(raw_data, numpy.ndarray):
            if len(raw_data.shape) != 2 and str(raw_data.dtype)[0] != "f":
                h5_file.create_dataset("/data", data=raw_data)
                write_metadata({KEY_MAX: raw_data.max(), KEY_MIN: raw_data.min(), KEY_STEPS: raw_data.shape[0],
                                KEY_CHANNELS: raw_data.shape[1], KEY_SV: 1, KEY_SAMPLING: sampling_period,
                                KEY_START: 0.0}, h5_file, KEY_DATE, KEY_VERSION, "/data")
            else:
                raise_value_error("Invalid TS data. 2D (time, nodes) numpy.ndarray of floats expected")
        elif isinstance(raw_data, Timeseries):
            if len(raw_data.shape) == 4 and str(raw_data.data.dtype)[0] == "f":
                h5_file.create_dataset("/data", data=raw_data.data)
                h5_file.create_dataset("/time", data=raw_data.time_line)
                h5_file.create_dataset("/labels",
                                       data=numpy.array([numpy.string_(label) for label in raw_data.space_labels]))
                h5_file.create_dataset("/variables",
                                       data=numpy.array([numpy.string_(var) for var in raw_data.variables_labels]))
                h5_file.attrs.create("time_unit", raw_data.time_unit)
                write_metadata({KEY_MAX: raw_data.data.max(), KEY_MIN: raw_data.data.min(),
                                KEY_STEPS: raw_data.data.shape[0], KEY_CHANNELS: raw_data.data.shape[1],
                                KEY_SV: 1, KEY_SAMPLING: raw_data.time_step,
                                KEY_START: raw_data.time_start}, h5_file, KEY_DATE, KEY_VERSION, "/data")
            else:
                raise_value_error("Invalid TS data. 4D (time, nodes) numpy.ndarray of floats expected")
        else:
            raise_value_error("Invalid TS data. Dictionary or 2D (time, nodes) numpy.ndarray of floats expected")
        h5_file.close()

    def write_timeseries(self, timeseries, path):
        self.write_ts(timeseries, timeseries.time_step, path)

    def write_probabilistic_model(self, probabilistic_model, nr_regions, path):
        """
        :param object:
        :param path:H5 path to be written
        """

        def _set_parameter_to_group(parent_group, parameter, nr_regions, param_name=None):
            if param_name is None:
                this_param_group = parent_group.create_group(parameter.name)
            else:
                this_param_group = parent_group.create_group(param_name)
            this_param_group, parameter_subgroups = \
                self._prepare_object_for_group(this_param_group, parameter, nr_regions=nr_regions)
            for param_subgroup_key in parameter_subgroups:
                if param_subgroup_key.find("p_shape") >= 0:
                    this_param_group[param_subgroup_key] = numpy.array(getattr(param_value, param_subgroup_key))
                elif param_subgroup_key == "star":
                    this_param_group, parameter_subgroup = \
                        _set_parameter_to_group(this_param_group, parameter.star, nr_regions, "star")
                else:
                    parameter_subgroup = param_group.create_group(param_subgroup_key)
                    parameter_subgroup, _ = self._prepare_object_for_group(parameter_subgroup,
                                                                           getattr(param_value, param_subgroup_key),
                                                                           nr_regions)
            return parent_group, this_param_group

        h5_file = h5py.File(change_filename_or_overwrite(path), 'a', libver='latest')

        datasets_dict, metadata_dict, groups_keys = self._determine_datasets_and_attributes(probabilistic_model,
                                                                                            nr_regions)
        h5_file.attrs.create(self.H5_TYPE_ATTRIBUTE, "HypothesisModel")
        h5_file.attrs.create(self.H5_SUBTYPE_ATTRIBUTE, probabilistic_model.__class__.__name__)

        self._write_dicts_at_location(datasets_dict, metadata_dict, h5_file)

        for group_key in groups_keys:

            if group_key == "parameters":
                group = h5_file.create_group(group_key)
                group.attrs.create(self.H5_SUBTYPE_ATTRIBUTE, probabilistic_model.parameters.__class__.__name__)
                for param_key, param_value in probabilistic_model.parameters.items():
                    group, param_group = _set_parameter_to_group(group, param_value, nr_regions, param_key)

            else:
                group = h5_file.create_group(group_key)
                group.attrs.create(self.H5_SUBTYPE_ATTRIBUTE,
                                   getattr(probabilistic_model, group_key).__class__.__name__)
                group, _ = self._prepare_object_for_group(group, getattr(probabilistic_model, group_key), nr_regions)

        h5_file.close()
