functions {

    real sample_lpdf(real x, int pdf, real[] shape) {
        if (pdf == 1) {
            // normal
            return normal_lpdf(x | shape[1], shape[2]);
        } else if (pdf == 2) {
            // gamma: convert to rate from scale!
            return gamma_lpdf(x | shape[1], 1.0 / shape[2]);
        } else if (pdf == 3) {
            // lognormal
            return lognormal_lpdf(x | shape[1], shape[2]);
        } else if (pdf == 4) {
            // exponential
            return exponential_lpdf(x | shape[1]);
        /* Beta not used for now...
        } else if (pdf == 5) {
            // beta
            return beta_lpdf(x | shape[1], shape[2]);
        */
        } else {
            // uniform
            return uniform_lpdf(x | shape[1], shape[2]);
        }
    }

    real sample_from_stdnormal_lpdf(real x, int pdf, real[] shape) {
        real n01;
        if (pdf == 1) {
            // Normal(mean, sigma**2) =  mean + sigma*Normal(0,1)
            n01 = normal_lpdf(x | 0.0, 1.0);
            return shape[1] + shape[2] * n01;
        } else if (pdf == 2) {
        // not possible! requires sum of INDEPENDENT Gamma random variables!
            return gamma_lpdf(x | shape[1], 1.0 / shape[2]);
        } else if (pdf == 3) {
            // lognormal(mean, sigma**2) = exp(Normal(mean, sigma**2)) = exp(mean + sigma*Normal(0,1))
            n01 = normal_lpdf(x | 0.0, 1.0);
            return exp(shape[1] + shape[2] * n01);
        } else if (pdf == 4) {
        // not possible! requires sum of INDEPENDENT Gamma random variables!
            return exponential_lpdf(x | shape[1]);
        /* Beta not used for now...
        } else if (pdf == 5) {
            // Beta(alpha, beta) = Gamma(alpha, c) / (Gamma(alpha, c) + Gamma(beta, c))
            return beta_lpdf(x | shape[1], shape[2]);
        */
        } else {
            // Not possible!
            return uniform_lpdf(x | shape[1], shape[2]);
        }
    }

    row_vector ode_step(int nx, row_vector x, row_vector df, real dt) {
        row_vector[nx] x_next = x + df * dt;
        return x_next;
    }

    row_vector sde_step(int nx, row_vector x, row_vector df, real dt, row_vector dWtsqrtdt) {
        row_vector[nx] x_next = x + df * dt + dWtsqrtdt;
        return x_next;
    }

    matrix vector_differencing(int ni, int nj, row_vector xi, row_vector xj) {
        matrix[nj, ni] Dji;
        for (j in 1:nj) {
            Dji[j] = xi - xj[j];
        }
        return Dji';
    }

    row_vector calc_coupling(int ni, int nj, row_vector xi, row_vector xj, matrix MC) {
        matrix[ni, nj] Dij = vector_differencing(ni, nj, xi, xj);
        row_vector[ni] coupling = to_row_vector(rows_dot_product(MC, Dij));
        return coupling;
    }

    row_vector EpileptorDP2D_fun_x1(int nn, row_vector x1, row_vector z, real yc, real Iext1,
                                    real a, real db, real d, real slope, real tau1) {
        row_vector[nn] constants = rep_row_vector(Iext1 + yc, nn);
        row_vector[nn] fx1;
        for (ii in 1:nn) {
            // population 1
            if (x1[ii] <= 0.0) {
                // if_ydot0 = a * x1 ** 2 + (d - b) * y[0],
                fx1[ii] = a * x1[ii] * x1[ii] + db * x1[ii];
            } else {
                // d * y[0] - 0.6 * (y[1] - 4.0) ** 2 - slope,
                fx1[ii] =  z[ii] - 4.0;
                fx1[ii] = d * x1[ii] - 0.6 * fx1[ii] * fx1[ii] - slope;
            }
        }
        // ydot[0] = tau1 * (yc - y[1] + Iext1 - where(y[0] < 0.0, if_ydot0, else_ydot0) * y[0])
        fx1 = tau1 * (constants - z - fx1 .* x1);
        return fx1;
    }

    row_vector EpileptorDP2D_fun_z_lin(int nn, row_vector x1, row_vector z, row_vector x0, row_vector coupling,
                                        real tau0, real tau1) {
        // slow energy variable with a linear form (original Epileptor)
        // ydot[1] = tau1 * (4 * (y[0] - x0) + where(y[1] < 0.0, if_ydot1, else_ydot1) - y[1] + K * c_pop1) / tau0
        row_vector[nn] fz = 4.0 * (x1 - x0) - z - coupling;
        for (ii in 1:nn) {
            if (z[ii] < 0.0) {
                // if_ydot1 = - 0.1 * y[1] ** 7
                fz[ii] = fz[ii] - 0.1 * z[ii] * z[ii] * z[ii] * z[ii] * z[ii] * z[ii] * z[ii];
            }
        }
        fz =  tau1 *  fz / tau0;
        return fz;
    }

}


data {

    int SIMULATE;
    int DEBUG;

    int n_regions;
    int n_times;
    int n_signals;
    int n_active_regions;
    int n_nonactive_regions;
    int n_connections;

    /* Integer flags and indices for (non)active regions */
    int active_regions[n_active_regions];
    int nonactive_regions[n_nonactive_regions];

    /* _lo stands for parameters' lower limits
       _hi stands for parameters' higher limits
       _pdf stands for an integer index of the distribution to be used for sampling, for the moment among:
            0. uniform
            1. normal
            2. lognormal
            3. gamma
            4. exponential
            5. beta
       _p[1] stands for a distribution's first parameter
       _p[2] stands for a distribution's second parameter, if any, otherwise, _p[2] = _p[1] */

    /* Generative model */
    /* Epileptor */
    // int zmode;
    real a;
    real b;
    real d;
    real yc;
    real Iext1;
    real slope;
    real x0cr;
    real rx0;
    // real x0_lo;
    // real x0_hi;
    /* x1eq parameter (only normal distribution, ignoring _pdf) */
    real x1eq_lo;
    real x1eq_hi;
    row_vector[n_regions] x1eq0;
    //real zeq_lo;
    //real zeq_hi;
    /* x1init parameter (only normal distribution, ignoring _pdf) */
    real x1init_lo;
    real x1init_hi;
    /* zinit parameter (only normal distribution, ignoring _pdf) */
    real zinit_lo;
    real zinit_hi;
    /* tau1 parameter (default: lognormal distribution) */
    real<lower=0.0> tau1_lo;
    real<lower=0.0> tau1_hi;
    real tau1_loc;
    real<lower=0.0> tau1_scale;
    real tau1_p[2];
    int<lower=0> tau1_pdf;
    /* tau0 parameter (default: lognormal distribution) */
    real<lower=0.0> tau0_lo;
    real<lower=0.0> tau0_hi;
    real tau0_loc;
    real<lower=0.0> tau0_scale;
    real tau0_p[2];
    int<lower=0> tau0_pdf;

    /* Coupling */
    /* K (global coupling) parameter (default: lognormal distribution) */
    real<lower=0.0> K_lo;
    real<lower=0.0> K_hi;
    real K_loc;
    real<lower=0.0> K_scale;
    real K_p[2];
    int<lower=0> K_pdf;
    /* SC symmetric connectivity data */
    matrix<lower=0.0>[n_regions, n_regions] SC;
    /* MC_split (model connectivity direction split) parameter (only normal distribution) */
    real<lower=0.0> MC_split_lo;
    real<lower=0.0> MC_split_hi;
    row_vector<lower=0.0, upper=1.0>[n_connections] MC_split_loc;
    row_vector<lower=0.0>[n_connections] MC_split_scale;
    /* MC_scale (model connectivity scale factor (multiplying standard deviation) */
    real<lower=0.0> MC_scale;

    /* Integration */
    real dt;
    /* Equilibrium point variability */
    real<lower=0.0> sig_eq;
    /* Initial condition variability */
    real<lower=0.0> sig_init;
    /* Dynamic noise strength parameter (default: gamma distribution) */
    real<lower=0.0> sig_lo;
    real<lower=0.0> sig_hi;
    real sig_loc;
    real<lower=0.0> sig_scale;
    real sig_p[2];
    int<lower=0> sig_pdf;

    /* Observation model */
    int observation_model;
    matrix[n_signals, n_regions] mixing;
    row_vector[n_signals] signals[n_times];
    /* Observation variability parameter (default: lognormal distribution) */
    real<lower=0.0> eps_lo;
    real<lower=0.0> eps_hi;
    real eps_loc;
    real<lower=0.0> eps_scale;
    real eps_p[2];
    int<lower=0> eps_pdf;
    /* Observation signal scaling parameter (defaul: normal distribution) */
    real<lower=0.0> scale_signal_lo;
    real<lower=0.0> scale_signal_hi;
    real scale_signal_loc;
    real<lower=0.0> scale_signal_scale;
    real scale_signal_p[2];
    int<lower=0> scale_signal_pdf;
    /* Observation signal offset parameter (only normal distribution) */
    real offset_signal_lo;
    real offset_signal_hi;
    real offset_signal_loc;
    real<lower=0.0> offset_signal_scale;
    // real offset_signal_p[2];
    // int<lower=0> offset_signal_pdf;
}


transformed data {
    // Calculate db parameter, which corresponds to parameter b for the 2D reduced Epileptor (Proix etal 2014)
    real db = d - b;
    real sqrtdt = sqrt(dt);
    row_vector[n_regions] zeros = rep_row_vector(0.0, n_regions);
    /* Transformation of low and high bounds for star parameters
     * following (x-loc) / scale transformation of pdf support */
    real tau1_star_lo = (tau1_lo - tau1_loc) / tau1_scale;
    real tau1_star_hi = (tau1_hi - tau1_loc) / tau1_scale;
    real tau0_star_lo = (tau0_lo - tau0_loc) / tau0_scale;
    real tau0_star_hi = (tau0_hi - tau0_loc) / tau0_scale;
    real K_star_lo = (K_lo - K_loc) / K_scale;
    real K_star_hi = (K_hi - K_loc) / K_scale;
    real sig_star_lo = (sig_lo - sig_loc) / sig_scale;
    real sig_star_hi = (sig_hi - sig_loc) / sig_scale;
    real eps_star_lo = (eps_lo - eps_loc) / eps_scale;
    real eps_star_hi = (eps_hi - eps_loc) / eps_scale;
    real scale_signal_star_lo = (scale_signal_lo - scale_signal_loc) / scale_signal_scale;
    real scale_signal_star_hi = (scale_signal_hi - scale_signal_loc) / scale_signal_scale;
    // TODO: Adjustment of signal scaling, offset and eps!


    }

}


parameters {

    /* Generative model */
    /* Epileptor */
    row_vector<lower=x1eq_lo, upper=x1eq_hi>[n_regions] x1eq; // x1 equilibrium point coordinate
    row_vector<lower=x1init_lo, upper=x1init_hi>[n_regions] x1init; // x1 initial condition coordinate
    row_vector<lower=zinit_lo, upper=zinit_hi>[n_regions] zinit; // x1 initial condition coordinate
    // row_vector[n_active_regions] x1_dWt[n_times-1]; // x1 dWt
    row_vector[n_active_regions] z_dWt[n_times]; // z dWt
    real<lower=tau1_star_lo, upper=tau1_star_hi> tau1_star; // time scale [n_active_regions]
    real<lower=tau0_star_lo, upper=tau0_star_hi> tau0_star; // time scale separation [n_active_regions]
    /* Coupling */
    real<lower=K_star_lo, upper=K_star_hi> K_star; // global coupling scaling
    row_vector[n_connections] MC_split; // Model connectivity direction split
    matrix<lower=0.0>[n_regions, n_regions] MC; // Model connectivity

    /* Integration */
    real<lower=sig_star_lo, upper=sig_star_hi> sig_star; // variance of phase flow, i.e., dynamic noise

    /* Observation model */
    real<lower=eps_star_lo, upper=eps_star_hi> eps_star; // variance of observation noise
    real<lower=scale_star_signal_lo, upper=scale_star_signal_hi> scale_signal_star; // observation signal scaling
    real<lower=offset_signal_lo, upper=offset_signal_hi> offset_signal; // observation signal offset
}


transformed parameters {

    /* Generative model */

    /* Epileptor */
    row_vector[n_regions] x1[n_times]; // x1 state variable
    row_vector[n_regions] z[n_times]; // z state variable
    real<lower=0.0> tau1 = tau1_star * tau1_scale + tau1_loc; // time scale
    real<lower=0.0> tau0 = tau0_star * tau0_scale + tau0_loc; // time scale separation
    /* zeq, z equilibrium point coordinate */
    row_vector[n_regions] zeq = EpileptorDP2D_fun_x1(n_regions, x1eq, zeros, yc, Iext1, a, db, d, slope, 1.0);

    /* Coupling */
    real<lower=0.0> K = K_star * K_scale + K_loc; // global coupling scaling
    row_vector[n_regions] coupling_eq = calc_coupling(n_regions, n_regions, x1eq, x1eq, MC); // coupling at equilibrium
    row_vector[n_regions] coupling[n_times]; // actual effective coupling per time point

    /* x0, excitability parameter */
    row_vector[n_regions] x0 = EpileptorDP2D_fun_z_lin(n_regions, x1eq, zeq, zeros, K * coupling_eq, 1.0, 1.0) / 4.0;

    /* Observation model */
    row_vector[n_signals] fit_signals[n_times]; // expected output signal
    real<lower=0.0> eps = eps_star * eps_scale + eps_loc; // variance of observation noise
    real<lower=0.0> scale_signal = scale_signal_star * scale_signal_scale + scale_signal_loc; // observation signal scaling

    /* Integration of auto-regressive generative model  */
    real<lower=0.0> sig = sig_star * sig_scale + sig_loc; // variance of phase flow, i.e., dynamic noise
    /* Initial condition */
    x1[1] = x1init;
    z[1] = zinit;
    coupling[1] = calc_coupling(n_regions, n_regions, x1[1], x1[1], MC);
    {
        row_vector[n_regions] df;
        row_vector[n_regions] observation;

        for (tt in 2:n_times) {
            df = EpileptorDP2D_fun_x1(n_regions, x1[tt-1], z[tt-1], yc, Iext1, a, db, d, slope, tau1);
            x1[tt] = ode_step(n_regions, x1[tt-1], df, dt);
            coupling[tt] = calc_coupling(n_regions, n_regions, x1[tt], x1[tt], MC);
            df = EpileptorDP2D_fun_z_lin(n_regions, x1[tt-1], z[tt-1], x0, K*coupling[tt-1], tau0, tau1);
            z[tt, active_regions] = sde_step(n_regions, z[tt-1, active_regions], df, dt, z_dWt[tt-1] * sqrtdt);
            z[tt, nonactive_regions] = ode_step(n_regions, z[tt-1, active_regions], df, dt);

            if  (observation_model == 0) {
                // seeg log power: observation with some log mixing, scaling and offset_signal
                fit_signals[tt] = (scale_signal * log(mixing * exp(x1[tt]')) + offset_signal)';
            } else if (observation_model == 1){
                // observation with some linear mixing, scaling and offset_signal
                fit_signals[tt] = (scale_signal * mixing * x1[tt]' + offset_signal)';
            } else {
                // observation with some scaling and offset_signal, without mixing
                fit_signals[tt] = scale_signal * x1[tt] + offset_signal;
            }
        }
    }
}


model {

    int icon = 0;
    real MC_loc;

    /* Sampling of time scales */
    tau1_star ~ sample(tau1_pdf, tau1_p);
    tau0_star ~ sample(tau1_pdf, tau0_p);
    /* Sampling of global coupling scaling */
    K_star ~ sample(K_pdf, K_p);
    /* Sampling of model connectivity and its split parameter */
    MC_split ~ normal(MC_split_loc, MC_split_scale);
    for (ii in 1:n_regions) {
        for (jj in ii:n_regions) {
            if (ii == jj) {
                MC[ii, jj] ~ normal(0.0, 0.0);
            } else {
                icon += 1;
                MC_loc = SC[ii, jj] * MC_split[icon];
                MC[ii, jj] ~ normal(MC_loc, MC_loc * MC_scale);
                MC_loc = SC[jj, ii] * (1-MC_split[icon]);
                MC[jj, ii] ~ normal(MC_loc, MC_loc * MC_scale);}
        }
    }
    /* Sampling of noise strength */
    sig_star ~ sample(sig_pdf, sig_p);
    /* Sampling of x1 equilibrium point coordinate and initial condition */
    x1eq ~ normal(x1eq0, sig_eq);
    x1init ~ normal(x1eq, sig_init);
    zinit ~ normal(zeq, sig_init/2);

    /* Sampling of observation scaling and offset */
    scale_signal_star ~ sample(scale_signal_pdf, scale_signal_p);
    offset_signal ~ normal(offset_signal_loc, offset_signal_scale);
    /* Integrate & predict  */
    for (tt in 1:n_times) {
        /* Auto-regressive generative model  */
        // to_vector(x1_dWt[tt]) ~ normal(0, 1);
        to_vector(z_dWt[tt]) ~ normal(0, 1);
    }
    /* Observation model  */
    if (SIMULATE <= 0){
        for (tt in 1:n_times)
            signals[tt] ~ normal(fit_signals[tt], eps);
    }
}
