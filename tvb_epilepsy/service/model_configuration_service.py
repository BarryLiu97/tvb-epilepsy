# coding=utf-8
"""
Service to do X0/e_values Hypothesis configuration.

NOTES:
In the future all the related to model configuration parameters might be part of the disease hypothesis:
yc=YC_DEF, Iext1=I_EXT1_DEF, K=K_DEF, a=A_DEF, b=B_DEF
For now, we assume default values, or externally set
"""
import numpy as np
from tvb_epilepsy.base.model.model_configuration import ModelConfiguration
from tvb_epilepsy.base.utils.log_error_utils import warning # initialize_logger
from tvb_epilepsy.base.utils.data_structures_utils import formal_repr, ensure_list
from tvb_epilepsy.base.computations.calculations_utils import calc_x0cr_r, calc_coupling, calc_x0, \
    calc_x0_val_to_model_x0, calc_model_x0_to_x0_val
from tvb_epilepsy.base.computations.equilibrium_computation import calc_eq_z, eq_x1_hypo_x0_linTaylor, \
    eq_x1_hypo_x0_optimize
from tvb_epilepsy.base.constants.model_constants import X1_EQ_CR_DEF, E_DEF, X0_DEF, K_DEF, YC_DEF, I_EXT1_DEF, \
    I_EXT2_DEF, A_DEF, B_DEF, D_DEF, SLOPE_DEF, S_DEF, GAMMA_DEF


class ModelConfigurationService(object):
    x1EQcr = X1_EQ_CR_DEF

    def __init__(self, number_of_regions=1, x0_values=X0_DEF, e_values=E_DEF, yc=YC_DEF, Iext1=I_EXT1_DEF,
                 Iext2=I_EXT2_DEF, K=K_DEF, a=A_DEF, b=B_DEF, d=D_DEF, slope=SLOPE_DEF, s=S_DEF, gamma=GAMMA_DEF,
                 zmode=np.array("lin"), x1eq_mode="optimize"):
        self.number_of_regions = number_of_regions
        self.x0_values = x0_values * np.ones((self.number_of_regions,), dtype=np.float32)
        self.yc = yc
        self.Iext1 = Iext1
        self.Iext2 = Iext2
        self.a = a
        self.b = b
        self.d = d
        self.slope = slope
        self.s = s
        self.gamma = gamma
        self.zmode = zmode
        self.x1eq_mode = x1eq_mode
        if len(ensure_list(K)) == 1:
            self.K_unscaled = np.array(K) * np.ones((self.number_of_regions,), dtype=np.float32)
        elif len(ensure_list(K)) == self.number_of_regions:
            self.K_unscaled = np.array(K)
        else:
            warning("The length of input global coupling K is neither 1 nor equal to the number of regions!" +
                    "\nSetting model_configuration_service.K_unscaled = K_DEF for all regions")
        self.K = None
        self._normalize_global_coupling()
        self.e_values = e_values * np.ones((self.number_of_regions,), dtype=np.float32)
        self.x0cr = 0.0
        self.rx0 = 0.0
        self._compute_critical_x0_scaling()

    def __repr__(self):
        d = {"01. Number of regions": self.number_of_regions,
             "02. x0_values": self.x0_values,
             "03. e_values": self.e_values,
             "04. K_unscaled": self.K_unscaled,
             "05. K": self.K,
             "06. yc": self.yc,
             "07. Iext1": self.Iext1,
             "08. Iext2": self.Iext2,
             "09. K": self.K,
             "10. a": self.a,
             "11. b": self.b,
             "12. d": self.d,
             "13. s": self.s,
             "14. slope": self.slope,
             "15. gamma": self.gamma,
             "16. zmode": self.zmode,
             "07. x1eq_mode": self.x1eq_mode
             }
        return formal_repr(self, d)

    def __str__(self):
        return self.__repr__()

    def set_attribute(self, attr_name, data):
        setattr(self, attr_name, data)

    def _compute_model_x0(self, x0_values):
        return calc_x0_val_to_model_x0(x0_values, self.yc, self.Iext1, self.a, self.b, self.d, self.zmode)

    def _ensure_equilibrum(self, x1EQ, zEQ):
        temp = x1EQ > self.x1EQcr - 10 ** (-3)
        if temp.any():
            x1EQ[temp] = self.x1EQcr - 10 ** (-3)
            zEQ = self._compute_z_equilibrium(x1EQ)

        return x1EQ, zEQ

    def _compute_x1_equilibrium_from_E(self, e_values):
        array_ones = np.ones((self.number_of_regions,), dtype=np.float32)
        return ((e_values - 5.0) / 3.0) * array_ones

    def _compute_z_equilibrium(self, x1EQ):
        return calc_eq_z(x1EQ, self.yc, self.Iext1, "2d", slope=self.slope, a=self.a, b=self.b, d=self.d)

    def _compute_critical_x0_scaling(self):
        (self.x0cr, self.rx0) = calc_x0cr_r(self.yc, self.Iext1, a=self.a, b=self.b, d=self.d, zmode=self.zmode)

    def _compute_coupling_at_equilibrium(self, x1EQ, model_connectivity):
        return calc_coupling(x1EQ, self.K, model_connectivity)

    def _compute_x0_values_from_x0_model(self, x0):
        return calc_model_x0_to_x0_val(x0, self.yc, self.Iext1, self.a, self.b, self.d, self.zmode)

    def _compute_x0_values(self, x1EQ, zEQ, model_connectivity):
        x0 = calc_x0(x1EQ, zEQ, self.K, model_connectivity)
        return self._compute_x0_values_from_x0_model(x0)

    def _compute_e_values(self, x1EQ):
        return 3.0 * x1EQ + 5.0

    def _compute_params_after_equilibration(self, x1EQ, zEQ, model_connectivity):
        self._compute_critical_x0_scaling()
        Ceq = self._compute_coupling_at_equilibrium(x1EQ, model_connectivity)
        x0_values = self._compute_x0_values(x1EQ, zEQ, model_connectivity)
        e_values = self._compute_e_values(x1EQ)
        x0 = self._compute_model_x0(x0_values)
        return x0, Ceq, x0_values, e_values

    def _compute_x1_and_z_equilibrium_from_E(self, e_values):
        x1EQ = self._compute_x1_equilibrium_from_E(e_values)
        zEQ = self._compute_z_equilibrium(x1EQ)
        return x1EQ, zEQ

    def _compute_x1_equilibrium(self, e_indices, x1EQ, zEQ, x0_values, model_connectivity):
        self._compute_critical_x0_scaling()
        x0 = self._compute_model_x0(x0_values)
        x0_indices = np.delete(np.array(range(model_connectivity.shape[0])), e_indices)
        if self.x1eq_mode == "linTaylor":
            x1EQ = \
                eq_x1_hypo_x0_linTaylor(x0_indices, e_indices, x1EQ, zEQ, x0, self.K,
                                        model_connectivity, self.yc, self.Iext1, self.a, self.b, self.d)[0]
        else:
            x1EQ = \
                eq_x1_hypo_x0_optimize(x0_indices, e_indices, x1EQ, zEQ, x0, self.K,
                                       model_connectivity, self.yc, self.Iext1, self.a, self.b, self.d)[0]
        return x1EQ

    def _normalize_global_coupling(self):
        self.K = 10.0 * self.K_unscaled / self.number_of_regions

    def configure_model_from_equilibrium(self, x1EQ, zEQ, model_connectivity):
        # x1EQ, zEQ = self._ensure_equilibrum(x1EQ, zEQ) # We don't this by default anymore
        x0, Ceq, x0_values, e_values = self._compute_params_after_equilibration(x1EQ, zEQ, model_connectivity)
        return ModelConfiguration(self.yc, self.Iext1, self.Iext2, self.K, self.a, self.b, self.d,
                                  self.slope, self.s, self.gamma, x1EQ, zEQ, Ceq, x0, x0_values,
                                  e_values, self.zmode, model_connectivity)

    def configure_model_from_E_hypothesis(self, disease_hypothesis, model_connectivity):
        # Always normalize K first
        self._normalize_global_coupling()

        # Then apply connectivity disease hypothesis scaling if any:
        if len(disease_hypothesis.w_indices) > 0:
            model_connectivity *= disease_hypothesis.get_connectivity_disease()

        # All nodes except for the diseased ones will get the default epileptogenicity:
        e_values = np.array(self.e_values)
        e_values[disease_hypothesis.e_indices] = disease_hypothesis.e_values

        # Compute equilibrium from epileptogenicity:
        x1EQ, zEQ = self._compute_x1_and_z_equilibrium_from_E(e_values)

        return self.configure_model_from_equilibrium(x1EQ, zEQ, model_connectivity)

    def configure_model_from_hypothesis(self, disease_hypothesis, model_connectivity):
        # Always normalize K first
        self._normalize_global_coupling()

        # Then apply connectivity disease hypothesis scaling if any:
        if len(disease_hypothesis.w_indices) > 0:
            model_connectivity *= disease_hypothesis.get_connectivity_disease()

        # We assume that all nodes have the default (healthy) excitability:
        x0_values = np.array(self.x0_values)
        # ...and some  excitability-diseased ones:
        x0_values[disease_hypothesis.x0_indices] = disease_hypothesis.x0_values
        # x0_values values must have size of len(x0_indices):
        x0_values = np.delete(x0_values, disease_hypothesis.e_indices)

        # There might be some epileptogenicity-diseased regions as well:
        # Initialize with the default e_values
        e_values = np.array(self.e_values)
        # and assign any diseased E_values if any
        e_values[disease_hypothesis.e_indices] = disease_hypothesis.e_values

        # Compute equilibrium from epileptogenicity:
        x1EQ_temp, zEQ_temp = self._compute_x1_and_z_equilibrium_from_E(e_values)

        # Now, solve the system in order to compute equilibrium:
        x1EQ = self._compute_x1_equilibrium(disease_hypothesis.e_indices, x1EQ_temp, zEQ_temp, x0_values,
                                            model_connectivity)
        zEQ = self._compute_z_equilibrium(x1EQ)

        return self.configure_model_from_equilibrium(x1EQ, zEQ, model_connectivity)

    def update_for_pse(self, values, paths, indices):
        for i, val in enumerate(paths):
            vals = val.split(".")
            if vals[0] == "model_configuration_service":
                getattr(self, vals[1])[indices[i]] = values[i]
