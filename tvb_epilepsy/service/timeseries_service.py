
import numpy as np
from scipy.signal import decimate, convolve
from scipy.stats import zscore

from tvb_epilepsy.base.utils.log_error_utils import raise_value_error, initialize_logger
from tvb_epilepsy.base.utils.data_structures_utils import isequal_string
from tvb_epilepsy.base.model.timeseries import Timeseries, TimeseriesDimensions


def decimate_signals(signals, time, decim_ratio):
    signals = decimate(signals, decim_ratio, axis=0, zero_phase=True)
    time = decimate(time, decim_ratio, zero_phase=True)
    dt = np.mean(np.diff(time))
    (n_times, n_signals) = signals.shape
    return signals, time, dt, n_times


def cut_signals_tails(signals, time, cut_tails):
    signals = signals[cut_tails[0]:-cut_tails[-1]]
    time = time[cut_tails[0]:-cut_tails[-1]]
    (n_times, n_signals) = signals.shape
    return signals, time, n_times


def normalize_signals(signals, normalization=None):
    if isinstance(normalization, basestring):
        if isequal_string(normalization, "zscore"):
            signals = zscore(signals, axis=None) / 3.0
        elif isequal_string(normalization, "minmax"):
            signals -= signals.min()
            signals /= signals.max()
        elif isequal_string(normalization, "baseline-amplitude"):
            signals -= np.percentile(signals, 5, 0)
            signals /= np.percentile(signals, 95)
        else:
            raise_value_error("Ignoring signals' normalization " + normalization +
                             ",\nwhich is not one of the currently available 'zscore' and 'minmax'!")

    return signals

#TODO: Decide upon this commented method
# def compute_envelope(data, time, samp_rate, hp_freq=5.0, lp_freq=0.1, benv_cut=100, cut_tails=None, order=3):
#     if cut_tails is not None:
#         start = cut_tails[0]
#         stop = cut_tails[1]
#     else:
#         start = int(samp_rate / lp_freq)
#         skip = int(samp_rate / (lp_freq * 3))
#     data = filter_data(data, samp_rate, 'highpass', lowcut=lp_freq, order=order)
#     data = filter_data(np.abs(data), samp_rate, 'lowpass', highcut=hp_freq, order=order)
#     data = data[:, start::skip]
#     fm = benv > 100  # bipolar 100, otherwise 300 (roughly)
#     incl_names = "HH1-2 HH2-3".split()
#     incl_idx = np.array([i for i, (name, *_) in enumerate(contacts_bip) if name in incl_names])
#     incl = np.setxor1d(
#         np.unique(np.r_[
#                       incl_idx,
#                       np.r_[:len(fm)][fm.any(axis=1)]
#                   ])
#         , afc_idx)
#     isort = incl[np.argsort([te[fm[i]].mean() for i in incl])]
#     iother = np.setxor1d(np.r_[:len(benv)], isort)
#     lbenv = np.log(np.clip(benv[isort], benv[benv > 0].min(), None))
#     lbenv_all = np.log(np.clip(benv, benv[benv > 0].min(), None))
#     return te, isort, iother, lbenv, lbenv_all


class TimeSeriesService(object):

    logger = initialize_logger(__name__)

    def __init__(self, logger=initialize_logger(__name__)):

        self.logger = logger

    def decimate(self, time_series, decim_ratio):
        decim_data, decim_time, decim_dt, decim_n_times = decimate_signals(time_series[:],
                                                                           time_series.time_line, decim_ratio)
        return Timeseries(decim_data, {TimeseriesDimensions.SPACE.value: time_series.space_labels},
                          decim_time[0], decim_dt, time_series.time_unit)

    def convolve(self, time_series, win_len=None, kernel=None):
        if kernel is None:
            kernel = np.ones((np.int(np.round(win_len), )))
        kernel_shape = tuple([len(kernel)] + list(time_series.shape[1:]))
        kernel = np.broadcast_to(kernel, kernel_shape)
        convolved_data = convolve(time_series[:], kernel, mode='same')
        return Timeseries(convolved_data, {TimeseriesDimensions.SPACE.value: time_series.space_labels},
                          time_series.time_start, time_series.time_step, time_series.time_unit)