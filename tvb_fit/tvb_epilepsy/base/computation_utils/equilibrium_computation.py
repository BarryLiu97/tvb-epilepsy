"""
Module to compute the resting equilibrium point of a Virtual Epileptic Patient module
"""

import numpy
from tvb_fit.base.utils.log_error_utils import raise_not_implemented_error
from tvb_fit.tvb_epilepsy.base.constants.config import CalculusConfig
from tvb_fit.tvb_epilepsy.base.computation_utils.calculations_utils import *

logger = initialize_logger(__name__)


if CalculusConfig.SYMBOLIC_CALCULATIONS_FLAG:

    try:
        from sympy import solve, solve_poly_system, solveset, S, lambdify
        from mpmath import re, im
        from tvb_fit.tvb_epilepsy.base.computation_utils.symbolic_utils import symbol_vars, symbol_eqtn_fx1z, symbol_eqtn_fx2y2, \
                                                                  symbol_eqtn_fx1z_diff

    except:
        logger.warning("Unable to load sympy. Turning to scipy.optimization.")
        CalculusConfig.SYMBOLIC_CALCULATIONS_FLAG = False


def def_x1eq(X1_DEF, X1_EQ_CR_DEF, n_regions):
    #The default initial condition for x1 equilibrium search
    return (X1_EQ_CR_DEF + X1_DEF) / 2.0 * numpy.ones((1,n_regions), dtype='float32')


def def_x1lin(X1_DEF, X1_EQ_CR_DEF, n_regions):
    # The point of the linear Taylor expansion
    return (X1_EQ_CR_DEF + X1_DEF) / 2.0 * numpy.ones((1,n_regions), dtype='float32')


def calc_eq_x1(yc, Iext1, x0, K, w, a=A_DEF, b=B_DEF, d=D_DEF, zmode=numpy.array([ZMODE_DEF]), model="6d"):
    x0, K, yc, Iext1, a, b, d = assert_arrays([x0, K, yc, Iext1, a, b, d])
    n = x0.size
    shape = x0.shape
    x0, K, yc, Iext1, a, b, d = assert_arrays([x0, K, yc, Iext1, a, b, d], (n,))
    w = assert_arrays([w], (n, n))
    # if CalculusConfig.SYMBOLIC_CALCULATIONS_FLAG:
    #
    #     fx1z, v = symbol_eqtn_fx1z(n, model, zmode)[1:]  # , x1_neg=True, z_pos=True
    #     fx1z = fx1z.tolist()
    #
    #     for iv in range(n):
    #         fx1z[iv] = fx1z[iv].subs([(v["x0_values"][iv], x0_values[iv]), (v["K"][iv], K[iv]), (v["y1"][iv], yc[iv]),
    #                                       (v["Iext1"][iv], Iext1[iv]), (v["a"][iv], a[iv]), (v["b"][iv], b[iv]),
    #                                       (v["d"][iv], d[iv]), (v["tau1"][iv], 1.0), (v["tau0"][iv], 1.0)])
    #         for jv in range(n):
    #             fx1z[iv] = fx1z[iv].subs(v["w"][iv, jv], w[iv, jv])
    #
    #     # TODO: solve symbolically if possible...
    #     # xeq = list(solve(fx1z, v["x1"].tolist()))
    #
    # else:
    fx1z = lambda x1: calc_fx1z(x1, x0, K, w, yc, Iext1, a=a, b=b, d=d, tau1=1.0, tau0=1.0, model=model, zmode=zmode,
                                shape=(Iext1.size, ))
    jac = lambda x1: calc_fx1z_diff(x1, K, w, a, b, d, tau1=1.0, tau0=1.0, model=model, zmode=zmode)
    sol = root(fx1z, -1.5*numpy.ones((Iext1.size, )), jac=jac, method='lm', tol=10 ** (-12), callback=None, options=None)
    #args=(y2eq[ii], zeq[ii], g_eq[ii], Iext2[ii], s, tau1, tau2, x2_neg)  method='hybr'
    if sol.success:
        if numpy.any([numpy.any(numpy.isnan(sol.x)), numpy.any(numpy.isinf(sol.x))]):
            raise_value_error("nan or inf values in solution x\n" + sol.message)
        x1eq = sol.x
    else:
        raise_value_error(sol.message)
    x1eq = numpy.reshape(x1eq, shape)
    if numpy.any(x1eq > 0.0):
        raise_value_error("At least one x1eq is > 0.0!")
    return x1eq


def calc_eq_z(x1eq, y1c, Iext1, model, x2=0.0, slope=SLOPE_DEF, a=A_DEF, b=B_DEF, d=D_DEF, x1_neg=True):
    return calc_fx1(x1eq, z=0.0, y1=y1c, Iext1=Iext1, slope=slope, a=a, b=b, d=d, tau1=1.0, x2=x2, model=model,
                    x1_neg=x1_neg)


def calc_eq_y1(x1eq, yc, d=D_DEF):
    return calc_fy1(x1eq, yc, y1=0, d=d, tau1=1.0)


def calc_eq_y2(x2eq, s=S_DEF, x2_neg=False):
    x2eq = assert_arrays([x2eq])
    return numpy.where(x2_neg, numpy.zeros(x2eq.shape), s * (x2eq + 0.25))


def calc_eq_g(x1eq, gamma=GAMMA_DEF):
    return calc_fg(x1eq, 0.0, gamma, tau1=1.0)


def calc_eq_x2(Iext2, y2eq=None, zeq=None, geq=None, x1eq=None, s=S_DEF, x2_neg=True):
    if geq is None:
        geq = calc_eq_g(x1eq)
    zeq, geq, Iext2, s = assert_arrays([zeq, geq, Iext2, s])
    shape = zeq.shape
    n = zeq.size
    zeq, geq, Iext2, s = assert_arrays([zeq, geq, Iext2, s], (n,))
    if CalculusConfig.SYMBOLIC_CALCULATIONS_FLAG:
        fx2y2, v = symbol_eqtn_fx2y2(n, x2_neg)[1:]
        fx2y2 = fx2y2.tolist()
        x2eq = []
        for iv in range(n):
            fx2y2[iv] = fx2y2[iv].subs([(v["z"][iv], zeq[iv]), (v["g"][iv], geq[iv]), (v["Iext2"][iv], Iext2[iv]),
                                      (v["s"][iv], s[iv]), (v["tau1"][iv], 1.0)])
            fx2y2[iv] = list(solveset(fx2y2[iv], v["x2"][iv], S.Reals))
            x2eq.append(numpy.min(numpy.array(fx2y2[iv], dtype=zeq.dtype)))
    else:
        # fx2 = tau1 * (-y2 + Iext2 + 2 * g - x2 ** 3 + x2 - 0.3 * z + 1.05)
        # if x2_neg = True, so that y2eq = 0.0:
        #   fx2 = tau1 * (Iext2 + 2 * g - x2 ** 3 + x2 - 0.3 * z + 1.05) =>
        #     0 = x2eq ** 3 - x2eq - (Iext2 + 2 * geq -0.3 * zeq + 1.05)
        # if x2_neg = False , so that y2eq = s*(x2+0.25):
        #   fx2 = tau1 * (-s * (x2 + 0.25) + Iext2 + 2 * g - x2 ** 3 + x2 - 0.3 * z + 1.05) =>
        #   fx2 = tau1 * (-0.25 * s  + Iext2 + 2 * g - x2 ** 3 + (1 - s) * x2 - 0.3 * z + 1.05 =>
        #     0 = x2eq ** 3 + (s - 1) * x2eq - (Iext2 + 2 * geq -0.3 * zeq - 0.25 * s + 1.05)
        # According to http://mathworld.wolfram.com/CubicFormula.html
        # and given that there is no square term (x2eq^2; "depressed cubic"), we write the equation in the form:
        # x^3 + 3 * Q * x -2 * R = 0
        Q = (-numpy.ones((n, ))/3.0)
        R = ((Iext2 + 2.0 * geq - 0.3 * zeq + 1.05) / 2)
        if y2eq is None:
            ss = numpy.where(x2_neg, 0.0, s)
            Q += ss / 3
            R -= 0.25 * ss / 2
        else:
            y2eq = (assert_arrays([y2eq], (n, )))
            R += y2eq / 2
        # Then the determinant is :
        # delta = Q^3 + R^2 =>
        delta = Q ** 3 + R ** 2
        # and S = cubic_root(R+sqrt(D), T = cubic_root(R-sqrt(D)
        delta_sq = numpy.sqrt(delta.astype("complex")).astype("complex")
        ST = [R + delta_sq, R - delta_sq]
        for ii in range(2):
            for iv in range(n):
                if numpy.imag(ST[ii][iv]) == 0.0:
                    ST[ii][iv] = numpy.sign(ST[ii][iv]) * numpy.power(numpy.abs(ST[ii][iv]), 1.0/3)
                else:
                    ST[ii][iv] = numpy.power(ST[ii][iv], 1.0 / 3)
        # and B = S+T, A = S-T
        B = ST[0]+ST[1]
        A = ST[0]-ST[1]
        # The roots then are:
        # x1 = -1/3 * a2 + B
        # x21 = -1/3 * a2 - 1/2 * B + 1/2 * sqrt(3) * A * j
        # x22 = -1/3 * a2 - 1/2 * B - 1/2 * sqrt(3) * A * j
        # where j = sqrt(-1)
        # But, in our case a2 = 0.0, so that:
        B2 = - 0.5 *B
        AA = (0.5 * numpy.sqrt(3.0) * A * 1j)
        sol = numpy.concatenate([[B.flatten()], [B2 + AA], [B2 - AA]]).T
        x2eq = []
        for ii in range(delta.size):
            temp = sol[ii, numpy.abs(numpy.imag(sol[ii])) < 10 ** (-6)]
            if temp.size == 0:
                raise_value_error("No real roots for x2eq_" + str(ii))
            else:
                x2eq.append(numpy.min(numpy.real(temp)))
        # zeq = zeq.flatten()
        # geq = geq.flatten()
        # Iext2 = Iext2.flatten()
        # x2eq = []
        # for ii in range(n):
        #
        #     if y2eq is None:
        #
        #         fx2 = lambda x2: calc_fx2(x2, y2=calc_eq_y2(x2, x2_neg=x2_neg), z=zeq[ii], g=geq[ii],
        #                                   Iext2=Iext2[ii], tau1=1.0)
        #
        #         jac = lambda x2: -3 * x2 ** 2 + 1.0 - numpy.where(x2_neg, 0.0, -s)
        #
        #     else:
        #
        #         fx2 = lambda x2: calc_fx2(x2, y2=0.0, z=zeq[ii], g=geq[ii], Iext2=Iext2[ii], tau1=1.0)
        #         jac = lambda x2: -3 * x2 ** 2 + 1.0
        #
        #     sol = root(fx2, -0.5, method='lm', jac=jac, tol=10 ** (-6), callback=None, options=None)
        #
        #     if sol.success:
        #
        #         if numpy.any([numpy.any(numpy.isnan(sol.x)), numpy.any(numpy.isinf(sol.x))]):
        #             raise_value_error("nan or inf values in solution x\n" + sol.message)
        #
        #         x2eq.append(numpy.min(numpy.real(numpy.array(sol.x))))
        #
        #     else:
        #         raise_value_error(sol.message)
    if numpy.array(x2_neg).size == 1:
        x2_neg = numpy.tile(x2_neg, (n, ))
    for iv in range(n):
        if x2_neg[iv] == False and x2eq[iv] < -0.25:
            logger.warning("\nx2eq["+str(iv)+"] = " + str(x2eq[iv]) + " < -0.25, although x2_neg[" + str(iv)+"] = False!" +
                    "\n" + "Rerunning with x2_neg[" + str(iv)+"] = True...")
            temp, _ = calc_eq_x2(Iext2[iv], zeq=zeq[iv], geq=geq[iv], s=s[iv], x2_neg=True)
            if temp < -0.25:
                x2eq[iv] = temp
                x2_neg[iv] = True
            else:
                logger.warning("\nThe value of x2eq returned after rerunning with x2_neg[" + str(iv)+"] = True, " +
                        "is " + str(temp) + ">= -0.25!" +
                        "\n" + "We will use the original x2eq!")
        if x2_neg[iv] == True and x2eq[iv] > -0.25:
            logger.warning("\nx2eq["+str(iv)+"] = " + str(x2eq[iv]) + " > -0.25, although x2_neg[" + str(iv)+"] = True!" +
                    "\n" + "Rerunning with x2_neg[" + str(iv)+"] = False...")
            temp, _ = calc_eq_x2(Iext2[iv], zeq=zeq[iv], geq=geq[iv], s=s[iv], x2_neg=False)
            if temp > -0.25:
                x2eq[iv] = temp
                x2_neg[iv] = True
            else:
                logger.warning("\nThe value of x2eq returned after rerunning with x2_neg[" + str(iv)+"] = False, " +
                        "is " + str(temp) + "=< -0.25!" +
                        "\n" + "We will use the original x2eq!")
    x2eq = numpy.reshape(x2eq, shape)
    return x2eq, x2_neg


def calc_eq_pop2(Iext2, y2eq=None, zeq=None, geq=None, x1eq=None, s=S_DEF, x2_neg=True):
    x2eq, x2_neg = calc_eq_x2(Iext2, y2eq, zeq, geq, x1eq, s, x2_neg)
    y2eq = calc_eq_y2(x2eq, s, x2_neg)
    return x2eq, y2eq


def eq_x1_hypo_x0_optimize_fun(x, ix0, iE, x1eq, zeq, x0, K, w, yc, Iext1, a=A_DEF, b=B_DEF, d=D_DEF, slope=SLOPE_DEF):
    x1_type = x1eq.dtype
    Iext1, slope, a, b, d = assert_arrays([Iext1, slope, a, b, d])
    # Construct the x1 and z equilibria vectors, comprising of the current x1eq, zeq values for i_e regions,
    # and the unknown equilibria x1 and respective z values for the i_x0 regions
    x1eq[ix0] = numpy.array(x[ix0])
    zeq[ix0] = numpy.array(calc_eq_z(x1eq[ix0], yc[ix0], Iext1[ix0], "2d", slope=slope[ix0], a=a[ix0], b=b[ix0],
                                     d=d[ix0]))
    # Construct the x0_values vector, comprising of the current x0_values values for i_x0 regions,
    # and the unknown x0_values values for the i_e regions
    x0_dummy = numpy.array(x0)
    x0 = numpy.empty_like(x1eq)
    x0[iE] = numpy.array(x[iE])
    x0[ix0] = numpy.array(x0_dummy)
    del x0_dummy
    fun = calc_fz(x1eq, zeq, x0, K, w, tau1=1.0, tau0=1.0, zmode=numpy.array([ZMODE_DEF]), z_pos=True, ).astype(x1_type)
    # if numpy.any([numpy.any(numpy.isnan(x)), numpy.any(numpy.isinf(x)),
    #               numpy.any(numpy.isnan(fun)), numpy.any(numpy.isinf(fun))]):
    #     raise_value_error("nan or inf values in x or fun")
    return fun


def eq_x1_hypo_x0_optimize_jac(x, ix0, iE, x1eq, zeq, x0, K, w, yc, Iext1,a=A_DEF, b=B_DEF, d=D_DEF, slope=SLOPE_DEF):
    Iext1, slope, a, b, d, slope = assert_arrays([Iext1, slope, a, b, d, slope])
    # Construct the x1 and z equilibria vectors, comprising of the current x1eq, zeq values for i_e regions,
    # and the unknown equilibria x1 and respective z values for the i_x0 regions
    x1eq[ix0] = numpy.array(x[ix0])
    zeq[ix0] = numpy.array(calc_eq_z(x1eq[ix0], yc[ix0], Iext1[ix0], "2d", slope=slope[ix0], a=a[ix0], b=b[ix0],
                                     d=d[ix0]))
    # Construct the x0_values vector, comprising of the current x0_values values for i_x0 regions,
    # and the unknown x0_values values for the i_e regions
    x0_dummy = numpy.array(x0)
    x0 = numpy.empty_like(x1eq)
    x0[iE] = numpy.array(x[iE])
    x0[ix0] = numpy.array(x0_dummy)
    del x0_dummy
    return calc_fx1z_2d_x1neg_zpos_jac(x1eq, zeq, x0, yc, Iext1,  K, w, ix0, iE, a=a, b=b, d=d, tau1=1.0, tau0=1.0)


def eq_x1_hypo_x0_optimize(ix0, iE, x1eq, zeq, x0, K, w, yc, Iext1, a=A_DEF, b=B_DEF, d=D_DEF, slope=SLOPE_DEF):
    x1eq, zeq, yc, Iext1, K, a, b, d, slope = assert_arrays([x1eq, zeq, yc, Iext1, K, a, b, d, slope], (x1eq.size, ))
    x0 = assert_arrays([x0],  (len(ix0, )))
    w = assert_arrays([w], (x1eq.size, x1eq.size))
    xinit = numpy.zeros(x1eq.shape, dtype=x1eq.dtype)
    #Set initial conditions for the optimization algorithm, by ignoring coupling (=0)
    # fz = 4 * (x1 - x0_values) - z -coupling = 0
    #x0init = x1 - z/4
    xinit[iE] = calc_x0(x1eq[iE], zeq[iE], K=0.0, w=0.0, zmode=numpy.array([ZMODE_DEF]), z_pos=True, shape=None)
    #x1eqinit = x0 + z / 4
    xinit[ix0] = x0 + zeq[ix0] / 4.0
    #Solve:
    sol = root(eq_x1_hypo_x0_optimize_fun, xinit,
               args=(ix0, iE, x1eq, zeq, x0, K, w, yc, Iext1, a, b, d, slope),
               method='lm', jac=eq_x1_hypo_x0_optimize_jac, tol=10**(-12), callback=None, options=None) #method='hybr'
    if sol.success:
        x1eq[ix0] = sol.x[ix0]
        x0sol = sol.x[iE]
        if numpy.any([numpy.any(numpy.isnan(sol.x)), numpy.any(numpy.isinf(sol.x))]):
            raise_value_error("nan or inf values in solution x\n" + sol.message)
        else:
            return x1eq, x0sol
    else:
        raise_value_error(sol.message)


def eq_x1_hypo_x0_linTaylor(ix0, iE, x1eq, zeq, x0, K, w, yc, Iext1, a=A_DEF, b=B_DEF, d=D_DEF):
    x1eq, zeq, yc, Iext1, K, a, b, d = assert_arrays([x1eq, zeq, yc, Iext1, K, a, b, d], (1, x1eq.size))
    x0 = assert_arrays([x0], (1, len(ix0)))
    w = assert_arrays([w], (x1eq.size, x1eq.size))
    no_x0 = len(ix0)
    no_e = len(iE)
    n_regions = no_e + no_x0
    # The equilibria of the nodes of fixed epileptogenicity
    x1_eq = x1eq[:, iE]
    z_eq = zeq[:, iE]
    #Prepare linear system to solve:
    x1_type = x1eq.dtype
    #The point of the linear Taylor expansion
    x1LIN = def_x1lin(X1_DEF, X1EQ_CR_DEF, n_regions).astype(x1_type)
    # For regions of fixed equilibria:
    ii_e = numpy.ones((1, no_e), dtype=x1_type)
    we_to_e = numpy.expand_dims(numpy.sum(w[iE][:, iE] * (numpy.dot(ii_e.T, x1_eq) -
                                                          numpy.dot(x1_eq.T, ii_e)), axis=1), 1).T.astype(x1_type)
    wx0_to_e = x1_eq * numpy.expand_dims(numpy.sum(w[ix0][:, iE], axis=0), 0).astype(x1_type)
    be = 4.0 * x1_eq - z_eq - K[:, iE] * (we_to_e - wx0_to_e)
    # For regions of fixed x0_values:
    ii_x0 = numpy.ones((1, no_x0), dtype=x1_type)
    we_to_x0 = numpy.expand_dims(numpy.sum(w[ix0][:, iE] * numpy.dot(ii_x0.T, x1_eq), axis=1), 1).T.astype(x1_type)
    bx0 = - 4.0 * x0 - yc[:, ix0] - Iext1[:, ix0] - 2.0 * x1LIN[:, ix0] ** 3 - 2.0 * x1LIN[:, ix0] ** 2 \
          - K[:, ix0] * we_to_x0
    # Concatenate B vector:
    b = -numpy.concatenate((be, bx0), axis=1).T.astype(x1_type)
    # From-to Epileptogenicity-fixed regions
    # ae_to_e = -4 * numpy.eye( no_e, dtype=numpy.float32 )
    ae_to_e = -4 * numpy.diag(numpy.ones((no_e,))).astype(x1_type)
    # From x0_values-fixed regions to Epileptogenicity-fixed regions
    ax0_to_e = -numpy.dot(K[:, iE].T, ii_x0) * w[iE][:, ix0]
    # From Epileptogenicity-fixed regions to x0_values-fixed regions
    ae_to_x0 = numpy.zeros((no_x0, no_e), dtype=x1_type)
    # From-to x0_values-fixed regions
    ax0_to_x0 = numpy.diag( (4.0 + 3.0 * x1LIN[:, ix0] ** 2 + 4.0 * x1LIN[:, ix0] +
                K[0, ix0] * numpy.expand_dims(numpy.sum(w[ix0][:, ix0], axis=0), 0)).T[:, 0]) - \
                numpy.dot(K[:, ix0].T, ii_x0) * w[ix0][:, ix0]
    # Concatenate A matrix
    a = numpy.concatenate((numpy.concatenate((ae_to_e, ax0_to_e), axis=1),
                           numpy.concatenate((ae_to_x0, ax0_to_x0), axis=1)), axis=0).astype(x1_type)
    # Solve the system
    x = numpy.dot(numpy.linalg.inv(a), b).T
    if numpy.any([numpy.any(numpy.isnan(x)), numpy.any(numpy.isnan(x))]):
        raise_value_error("nan or inf values in solution x")
    # Unpack solution:
    # The equilibria of the regions with fixed e_values have not changed:
    # The equilibria of the regions with fixed x0_values:
    x1eq[0, ix0] = x[0, no_e:]
    #Return also the solution of x0s for the regions of fixed e_values (equilibria):
    return x1eq.flatten(), x[0, :no_e].flatten()


def assert_equilibrium_point(model_config, epileptor_model, weights, equilibrium_point):
    n_dim = equilibrium_point.shape[0]
    if model_config.model_name == "EpileptorDP2D":
        dfun2 = calc_dfun(equilibrium_point[0].flatten(), equilibrium_point[1].flatten(),
                          model_config.yc.flatten(), model_config.Iext1.flatten(), model_config.x0.flatten(),
                          model_config.K.flatten(), weights, model_vars=n_dim, zmode=model_config.zmode,
                          slope=model_config.slope.flatten(), a=model_config.a.flatten(),
                          b=model_config.b.flatten(), d=model_config.d.flatten(),
                          tau1=model_config.tau1, tau0=model_config.tau0, output_mode="array")
    elif model_config.model_name == "EpileptorDP":
        #dfun_max_cr[2] = 10 ** -3
        dfun2 = calc_dfun(equilibrium_point[0].flatten(), equilibrium_point[2].flatten(),
                          model_config.yc.flatten(), model_config.Iext1.flatten(), model_config.x0.flatten(),
                          model_config.K.flatten(), weights, model_vars=n_dim, zmode=model_config.zmode,
                          y1=equilibrium_point[1].flatten(), x2=equilibrium_point[3].flatten(),
                          y2=equilibrium_point[4].flatten(), g=equilibrium_point[5].flatten(),
                          slope=model_config.slope.flatten(), a=model_config.a.flatten(),
                          b=model_config.b.flatten(), d=model_config.d.flatten(), s=model_config.s.flatten(),
                          Iext2=model_config.Iext2.flatten(), gamma=model_config.gamma.flatten(),
                          tau1=model_config.tau1, tau0=model_config.tau0, tau2=model_config.tau2,
                          output_mode="array")
    elif model_config.model_name == "EpileptorDPrealistic":
        #dfun_max_cr[2] = 10 ** -3
        dfun2 = calc_dfun(equilibrium_point[0].flatten(), equilibrium_point[2].flatten(),
                          model_config.yc.flatten(), model_config.Iext1.flatten(), model_config.x0.flatten(),
                          model_config.K.flatten(), weights, model_vars=n_dim,
                          zmode=model_config.zmode, pmode=model_config.pmode,
                          y1=equilibrium_point[1].flatten(), x2=equilibrium_point[3].flatten(),
                          y2=equilibrium_point[4].flatten(), g=equilibrium_point[5].flatten(),
                          x0_var=equilibrium_point[6].flatten(), slope_var=equilibrium_point[7].flatten(),
                          Iext1_var=equilibrium_point[8].flatten(), Iext2_var=equilibrium_point[9].flatten(),
                          K_var=equilibrium_point[10].flatten(),
                          slope=model_config.slope.flatten(), a=model_config.a.flatten(),
                          b=model_config.b.flatten(), d=model_config.d.flatten(), s=model_config.s.flatten(),
                          Iext2=model_config.Iext2.flatten(), gamma=model_config.gamma.flatten(),
                          tau1=model_config.tau1, tau0=model_config.tau0, tau2=model_config.tau2,
                          output_mode="array")
    else:
        # all 6D models (tvb, java)
        # dfun_max_cr[2] = 10 ** -3
        dfun2 = calc_dfun(equilibrium_point[0].flatten(), equilibrium_point[2].flatten(),
                          model_config.c, model_config.Iext, model_config.x0,
                          model_config.K, weights, model_vars=n_dim,
                          y1=equilibrium_point[1].flatten(), x2=equilibrium_point[3].flatten(),
                          y2=equilibrium_point[4].flatten(), g=equilibrium_point[5].flatten(),
                          slope=model_config.slope, a=model_config.a, b=model_config.b,
                          d=model_config.d, s=model_config.aa, Iext2=model_config.Iext2,
                          tau1=model_config.tt, tau0=1.0 / model_config.r, tau2=model_config.tau,
                          output_mode="array")

    # We use the opposite sign for K with respect to all epileptor models
    coupl = calc_coupling(equilibrium_point[0], -model_config.K, weights)
    coupl = numpy.expand_dims((numpy.c_[coupl, 0.0 * coupl]).T, 2)
    dfun = epileptor_model.dfun(numpy.expand_dims(equilibrium_point, 2).astype('float32'), coupl)
    dfun_max = numpy.max(numpy.abs(dfun.flatten()))
    dfun_max_cr = 10 ** -5 * numpy.ones(dfun_max.shape)
    max_dfun_diff = numpy.max(numpy.abs(dfun2.flatten() - dfun.flatten()))
    if numpy.any(max_dfun_diff > dfun_max_cr):
        logger.warning("\nmodel dfun and calc_dfun functions do not return the same results!\n"
                       + "maximum difference = " + str(max_dfun_diff))
        # + "\n" + "model dfun = " + str(dfun) + "\n"
        # + "calc_dfun = " + str(dfun2))
    else:
        dfun_max = numpy.max(numpy.abs(dfun2.flatten()))
        dfun_max_cr = 10 ** -5 * numpy.ones(dfun_max.shape)
    if numpy.any(dfun_max > dfun_max_cr):
        # raise_value_error("Equilibrium point for initial condition not accurate enough!\n" \
        #                  + "max(dfun) = " + str(dfun_max))
        ##                  + "\n" + "model dfun = " + str(dfun))
        logger.warning("\nEquilibrium point for initial condition not accurate enough!\n"
                       + "max(dfun) = " + str(dfun_max))
        #        + "\n" + "model dfun = " + str(dfun))


def calc_eq_6d(x0, K, w, yc, Iext1, Iext2, x1eq=None, a=A_DEF, b=B_DEF, d=D_DEF, s=S_DEF, gamma=GAMMA_DEF,
               zmode=numpy.array([ZMODE_DEF])):
    if x1eq is None:
        x1eq = calc_eq_x1(yc, Iext1, x0, K, w, a, b, d, zmode=zmode, model="6d")
    y1eq = calc_eq_y1(x1eq, yc, d)
    zeq = calc_eq_z(x1eq, y1eq, Iext1, "6d", x2=0.0, a=a, b=b, d=d)
    geq = calc_eq_g(x1eq, gamma)
    x2eq, y2eq = calc_eq_pop2(Iext2, y2eq=None, zeq=zeq, geq=geq, x1eq=x1eq, s=s, x2_neg=True)
    equilibrium_point = numpy.c_[x1eq, y1eq, zeq, x2eq, y2eq, geq].T
    return equilibrium_point


def calc_eq_11d(x0, K, w, yc, Iext1, Iext2, slope, fun_slope_Iext2, x1eq=None, a=A_DEF, b=B_DEF, d=D_DEF, s=S_DEF,
                gamma=GAMMA_DEF, zmode=numpy.array([ZMODE_DEF]), pmode=numpy.array([PMODE_DEF])):
    if x1eq is None:
        x1eq = calc_eq_x1(yc, Iext1, x0, K, w, a, b, d, zmode=zmode, model="11d")
    y1eq = calc_eq_y1(x1eq, yc, d)
    zeq = calc_eq_z(x1eq, y1eq, Iext1, "6d", x2=0.0, a=a, b=b, d=d)
    geq = calc_eq_g(x1eq, gamma)
    slope_eq, Iext2_eq = fun_slope_Iext2(zeq, geq, pmode, slope, Iext2)
    x2eq, y2eq = calc_eq_pop2(Iext2, y2eq=None, zeq=zeq, geq=geq, x1eq=x1eq, s=s, x2_neg=True)
    equilibrium_point = numpy.c_[x1eq, y1eq, zeq, x2eq, y2eq, geq,
                                 x0, slope_eq, Iext1*numpy.ones(x1eq.shape), Iext2_eq, K].T
    return equilibrium_point, slope_eq, Iext2_eq


def calc_equilibrium_point(model_config, weights, epileptor_model=None):

    # Update zeq given the specific model, and assuming the model_config x1eq for the moment in the context of a 2d model:
    # It is assumed that the model.x0_values has been adjusted already at the phase of model creation
    if model_config.model_name == "EpileptorDP2D":
        x1eq = model_config.x1eq
        zeq = model_config.zeq
        equilibrium_point = numpy.c_[x1eq, zeq].T
    elif model_config.model_name == "EpileptorDP":
        #EpileptorDP
        equilibrium_point = calc_eq_6d(model_config.x0, model_config.K, weights,
                                       model_config.yc, model_config.Iext1, model_config.Iext2,
                                       model_config.x1eq, model_config.a, model_config.b,
                                       model_config.d, model_config.s, model_config.gamma,
                                       zmode=model_config.zmode)
    elif model_config.model_name == "EpileptorDPrealistic":
        if epileptor_model is None:
            from tvb_fit.tvb_epilepsy.service.simulator.epileptor_model_factory \
                import build_EpileptorDPrealistic_from_model_config
            fun_slope_Iext2 = build_EpileptorDPrealistic_from_model_config(model_config).fun_slope_Iext2
        else:
            fun_slope_Iext2 = epileptor_model.fun_slope_Iext2
        equilibrium_point = calc_eq_11d(model_config.x0, model_config.K, weights,
                                        model_config.yc, model_config.Iext1, model_config.Iext2,
                                        model_config.slope, fun_slope_Iext2,
                                        model_config.x1eq, model_config.a, model_config.b,
                                        model_config.d, model_config.s,
                                        model_config.gamma, zmode=model_config.zmode,
                                        pmode=model_config.pmode)[0]
    else:
        # all 6D models (tvb, java)
        equilibrium_point = calc_eq_6d(model_config.x0, model_config.Ks, weights,
                                       model_config.c, model_config.Iext, model_config.Iext2,
                                       model_config.x1eq, model_config.a, model_config.b,
                                       model_config.d, model_config.aa, gamma=GAMMA_DEF, zmode=numpy.array([ZMODE_DEF]))
    if epileptor_model is not None:
        assert_equilibrium_point(model_config, epileptor_model, weights, equilibrium_point)
    return equilibrium_point


def compute_initial_conditions_from_eq_point(model_config, history_length=1, simulation_shape=False,
                                             epileptor_model=None):
    # Set default initial conditions right on the resting equilibrium point of the model...
    # ...after computing the equilibrium point (and correct it for zeql for a >=6D model
    initial_conditions = calc_equilibrium_point(model_config, model_config.connectivity, epileptor_model)
    # -------------------The lines below are for a specific "realistic" demo simulation:---------------------------------
    if (model_config.nvar > 6):
        shape = initial_conditions[5].shape
        n_regions = max(shape)
        type = initial_conditions[5].dtype
        initial_conditions[6] = 0.0 ** np.ones(shape, dtype=type)  # hypothesis.x0_values.T
        initial_conditions[7] = 1.0 * np.ones(
            (1, n_regions))  # model.slope * np.ones((hypothesis.number_of_regions,1))
        initial_conditions[9] = 0.0 * np.ones(
            (1, n_regions))  # model.Iext2.T * np.ones((hypothesis.number_of_regions,1))
    # ------------------------------------------------------------------------------------------------------------------
    if simulation_shape:
        initial_conditions = np.expand_dims(initial_conditions, 2)
        initial_conditions = np.tile(initial_conditions, (history_length, 1, 1, 1))
    return initial_conditions
