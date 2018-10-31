from enum import Enum

import numpy as np

from tvb_fit.tvb_epilepsy.base.constants.model_constants import X1_DEF, X1EQ_CR_DEF

# Model inversion constants


class XModes(Enum):
    X0MODE = "x0"
    X1EQMODE = "x1eq"

X1_REST = X1_DEF
X1EQ_CR = X1EQ_CR_DEF
X1EQ_MIN = -2.0
X1EQ_MAX = 0.0 # -1.0  # X1EQ_CR_DEF
X1EQ_DEF = X1_DEF
X1EQ_SCALE = 3.0
SIGMA_EQ_DEF = 0.25*(X1EQ_MAX - X1EQ_MIN)

X0_MIN = -7.5
X0_MAX = 2.5
X0_DEF = -2.5
X0_SCALE = 3.0
SIGMA_X0_DEF = 0.25*(X0_MAX - X0_MIN)

TAU1_DEF = 0.5
TAU1_MIN = 0.25  # from 0.1
TAU1_MAX = 1.0
TAU1_SCALE = 10.0  # from 5.0

TAU0_DEF = 30.0
TAU0_MIN = 10.0
TAU0_MAX = 100.0
TAU0_SCALE = 2.0

K_DEF = 3.0
K_MIN = 0.0
K_MAX = 15.0
K_SCALE = 3.0

MC_MIN = 0.0
MC_MAX = 2.0
MC_MAX_MIN_RATIO = 1000.0
MC_SCALE = 6.0

# ODE model inversion constants
X1_MIN = -2.0
X1_MAX = 2.0
Z_MIN = 2.0
Z_MAX = 6.0
X1_INIT_MIN = -2.0
X1_INIT_MAX = 0.0
Z_INIT_MIN = 2.5
Z_INIT_MAX = 5.0


def compute_seizure_length(tau0):
    return int(np.ceil(64 * (1 + 2*np.log10(tau0 / 30.0))))


def compute_dt(tau1,):
    return (1000.0 / 2048.0) * (0.5 / tau1)


def compute_upsample(seizure_length, default_seizure_length=None, tau0=None):
    if default_seizure_length is None:
        default_seizure_length = compute_seizure_length(tau0)
    return np.maximum(int(np.round(1.0*default_seizure_length / seizure_length)), 1)


SEIZURE_LENGTH = compute_seizure_length(TAU0_DEF)
DT_DEF = compute_dt(TAU1_DEF)
UPSAMPLE = compute_upsample(SEIZURE_LENGTH, default_seizure_length=SEIZURE_LENGTH, tau0=TAU0_DEF)

SIGMA_INIT_DEF = 0.1*SIGMA_EQ_DEF
EPSILON_DEF = 0.1

SCALE_DEF = 1.0
SCALE_SCALE_DEF = 30.0  # from 10.0
OFFSET_DEF = 0.0
OFFSET_SCALE_DEF = 10.0

class OBSERVATION_MODELS(Enum):
    SEEG_LOGPOWER = 0
    SEEG_POWER = 1
    SOURCE_POWER = 2
    SEEG = [SEEG_LOGPOWER, SEEG_POWER]


OBSERVATION_MODEL_DEF = "seeg_logpower"


# SDE model inversion constants
class SDE_MODES(Enum):
    CENTERED = "centered"
    NONCENTERED = "noncentered"

SIGMA_DEF = 0.05  # from 0.1
SIGMA_SCALE = 5.0  # from 2.0
SIGMA_MAX = 0.15  # from 0.5
SIGMA_MIN = 0.01  # from 0.05

X1_LOGSIGMA_DEF = 0.14
X1_LOGMU_DEF = np.log(0.58)
X1_LOGLOC_DEF = 0.28
X1_LOGSIGMA_ACTIVE = 0.70
X1_LOGMU_ACTIVE = np.log(0.79)
X1_LOGLOC_ACTIVE = 0.23

WIN_LEN_RATIO = 10.0
LOW_HPF = 10.0
HIGH_HPF = 256.0
LOW_LPF = 1.0
HIGH_LPF = 10.0
BIPOLAR = False

TARGET_DATA_PREPROCESSING = ["filter", "abs", "convolve", "log"]
