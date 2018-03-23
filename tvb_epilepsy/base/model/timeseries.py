import numpy
from copy import deepcopy
from collections import OrderedDict
from tvb_epilepsy.base.utils.log_error_utils import initialize_logger


class TimeseriesDimensions(object):
    TIME = "time"
    SPACE = "space"
    STATE_VARIABLES = "state_variables"
    SAMPLES = "samples"

    def getAll(self):
        return [self.TIME, self.SPACE, self.STATE_VARIABLES, self.SAMPLES]


class Timeseries(object):
    logger = initialize_logger(__name__)

    dimensions = TimeseriesDimensions().getAll()

    # dimension_labels = {"space": [], "state_variables": []}

    def __init__(self, data, dimension_labels, time_start, time_step, time_unit="ms"):
        self.data = self.prepare_4D(data)
        self.dimension_labels = dimension_labels
        self.time_start = time_start
        self.time_step = time_step
        self.time_unit = time_unit

    def prepare_4D(self, data):
        if data.ndim < 2:
            self.logger.error("The data array is expected to be at least 2D!")
            raise ValueError
        if data.ndim < 4:
            if data.ndim == 2:
                data = numpy.expand_dims(data, 2)
            data = numpy.expand_dims(data, 3)
        return data

    def get_end_time(self):
        return self.time_start + (self.data.shape[0] - 1) * self.time_step

    def get_time_line(self):
        return numpy.arange(self.time_start, self.get_end_time() + self.time_step, self.time_step)

    def get_squeezed_data(self):
        pass

    def _get_index_of_state_variable(self, sv_label):
        try:
            sv_index = self.dimension_labels[TimeseriesDimensions.STATE_VARIABLES].index(sv_label)
        except KeyError:
            self.logger.error("There are no state variables defined for this instance. Its shape is: %s",
                              self.data.shape)
            raise
        except ValueError:
            self.logger.error("Cannot access index of state variable label: %s. Existing state variables: %s" % (
                sv_label, self.dimension_labels[TimeseriesDimensions.STATE_VARIABLES]))
            raise
        return sv_index

    # TODO: have possibility to access this by Signal.sv_name
    def get_state_variable(self, sv_label):
        sv_data = self.data[:, :, self._get_index_of_state_variable(sv_label), :]
        return Timeseries(numpy.expand_dims(sv_data, 2),
                          OrderedDict({TimeseriesDimensions.SPACE: self.dimension_labels[TimeseriesDimensions.SPACE]}),
                          self.time_start, self.time_step, self.time_unit)

    def get_lfp(self):
        # compute if not exists
        pass

    def _get_indices_for_labels(self, list_of_labels):
        list_of_indices_for_labels = []
        for label in list_of_labels:
            try:
                space_index = self.dimension_labels[TimeseriesDimensions.SPACE].index(label)
            except ValueError:
                self.logger.error("Cannot access index of space label: %s. Existing space labels: %s" % (
                    label, self.dimension_labels[TimeseriesDimensions.SPACE]))
                raise
            list_of_indices_for_labels.append(space_index)
        return list_of_indices_for_labels

    def get_subspace_by_labels(self, list_of_labels):
        list_of_indices_for_labels = self._get_indices_for_labels(list_of_labels)
        subspace_data = self.data[:, list_of_indices_for_labels, :, :]
        subspace_dimension_labels = deepcopy(self.dimension_labels)
        subspace_dimension_labels[TimeseriesDimensions.SPACE] = list_of_labels
        if subspace_data.ndim == 3:
            subspace_data = numpy.expand_dims(subspace_data, 1)
        return Timeseries(subspace_data, subspace_dimension_labels, self.time_start, self.time_step, self.time_unit)

    def _check_space_indices(self, list_of_index):
        for index in list_of_index:
            if index < 0 or index > self.data.shape[1]:
                self.logger.error("Some of the given indices are out of region range: [0, %s]", self.data.shape[1])
                raise IndexError

    def get_subspace_by_index(self, list_of_index):
        self._check_space_indices(list_of_index)
        subspace_data = self.data[:, list_of_index, :, :]
        subspace_dimension_labels = deepcopy(self.dimension_labels)
        subspace_dimension_labels[TimeseriesDimensions.SPACE] = numpy.array(self.dimension_labels[
                                                                                TimeseriesDimensions.SPACE])[
            list_of_index]
        if subspace_data.ndim == 3:
            subspace_data = numpy.expand_dims(subspace_data, 1)
        return Timeseries(subspace_data, subspace_dimension_labels, self.time_start, self.time_step, self.time_unit)

    def _get_time_unit_for_index(self, time_index):
        return self.time_start + time_index * self.time_step

    def get_time_window(self, index_start, index_end):
        if index_start < 0 or index_end > self.data.shape[0] - 1:
            self.logger.error("The time indices are outside time series interval: [%s, %s]" % (0, self.data.shape[0]))
            raise IndexError
        subtime_data = self.data[index_start:index_end, :, :, :]
        if subtime_data.ndim == 3:
            subtime_data = numpy.expand_dims(subtime_data, 0)
        return Timeseries(subtime_data, self.dimension_labels,
                          self._get_time_unit_for_index(index_start), self.time_step, self.time_unit)

    def _get_index_for_time_unit(self, time_unit):
        return int((time_unit - self.time_start) / self.time_step)

    def get_time_window_by_units(self, unit_start, unit_end):
        end_time = self.get_end_time()
        if unit_start < self.time_start or unit_end > end_time:
            self.logger.error("The time units are outside time series interval: [%s, %s]" % (self.time_start, end_time))
            raise ValueError
        index_start = self._get_index_for_time_unit(unit_start)
        index_end = self._get_index_for_time_unit(unit_end)
        return self.get_time_window(index_start, index_end)

    def decimate_time(self, time_step):
        pass

    def get_sample_window(self, index_start, index_end):
        subsample_data = self.data[:, :, :, index_start:index_end]
        if subsample_data.ndim == 3:
            subsample_data = numpy.expand_dims(subsample_data, 3)
        return Timeseries(subsample_data, self.dimension_labels, self.time_start, self.time_step, self.time_unit)

    def get_sample_window_by_percentile(self, percentile_start, percentile_end):
        pass
