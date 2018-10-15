functions {

    matrix vector_differencing(row_vector x1) {
        matrix[num_elements(x1), num_elements(x1)] D;
        for (i in 1:num_elements(x1)) {
            D[i] = x1 - x1[i];
        }
        return D;
    }

    row_vector fx1(row_vector x1, row_vector z, real Iext1, real tau1) {
        int n_active_regions = num_elements(x1);
        row_vector[n_active_regions] x1_next;
        row_vector[n_active_regions] Iext1_vec = rep_row_vector(Iext1 + 1.0, n_active_regions);
        row_vector[n_active_regions] dx1 = Iext1_vec - (x1 .* x1 .* x1) - 2.0 * (x1 .* x1) - z;
        dx1 = tau1 * dx1;
        return dx1;
    }

    row_vector x1_step(row_vector x1, row_vector z, real Iext1, real tau1) { //, row_vector dX1t, real sigma
        int n_active_regions = num_elements(x1);
        row_vector[n_active_regions] dx1 = fx1(x1, z, Iext1, tau1);
        row_vector[n_active_regions]  x1_next = x1 + dx1; # + dX1t * sigma;
        return x1_next;
    }

    row_vector calc_zeq(row_vector x1eq, real Iext1, real tau1) {
        int n_active_regions = num_elements(x1eq);
        row_vector[n_active_regions] zeq = fx1(x1eq, 0*x1eq, Iext1, 1.0);
        return zeq;
    }

    row_vector fz(row_vector x1, row_vector z, row_vector x0, matrix FC, vector Ic, real x1_eq_def,
                  real tau1, real tau0) {
        int n_active_regions = num_elements(z);
        matrix[n_active_regions, n_active_regions] D = vector_differencing(x1);
        // Ic = Ic_i = sum_{j in nonactive regions} [w_ij]
        // gx(nonactive->active) = Ic * (x1_j - x1_i) = Ic * (x1_eq_def - x1)
        row_vector[n_active_regions] gx = to_row_vector(rows_dot_product(FC, D) + Ic .* to_vector(x1_eq_def - x1));
        row_vector[n_active_regions] dz = inv(tau0) * (4 * (x1 - x0) - z - gx);
        dz = tau1 * dz;
        return dz;
    }

    row_vector z_step(row_vector x1, row_vector z, row_vector x0, matrix FC, vector Ic, real x1_eq_def, real tau1,
                      row_vector dWt, real sigma, real tau0) {
        int n_active_regions = num_elements(z);
        row_vector[n_active_regions] dz = fz(x1, z, x0, FC, Ic, x1_eq_def, tau1, tau0);
        row_vector[n_active_regions] z_next = z + (tau1 * dz) + dWt * sigma;
        return z_next;
    }

    row_vector calc_x0(row_vector x1eq, row_vector zeq, matrix FC, vector Ic, real x1_eq_def) {
        int n_active_regions = num_elements(zeq);
        row_vector[n_active_regions] x0 = fz(x1eq, zeq, 0*x1eq, FC, Ic, x1_eq_def, 1.0, 1.0)/4;
        return x0;
    }

    real[] normal_mean_std_to_lognorm_mu_sigma(real mean_, real std_) {
        real mu_sigma[2];
        real logsm21 = std_/mean_;
        logsm21 = log(logsm21 * logsm21 + 1.0);
        mu_sigma[1] = log(mean_) - 0.5 * logsm21;
        mu_sigma[2] = sqrt(logsm21);
        return mu_sigma;
    }

    row_vector normal_mean_std_to_lognorm_mu(row_vector mean_, row_vector std_) {
        int n_active_regions = num_elements(mean_);
        row_vector[n_active_regions] logsm21 = std_ ./ mean_;
        logsm21 = log(logsm21 .* logsm21 + 1.0);
        return log(mean_) - 0.5 * logsm21;
    }

    row_vector normal_mean_std_to_lognorm_sigma(row_vector mean_, row_vector std_) {
        int n_active_regions = num_elements(mean_);
        row_vector[n_active_regions] logsm21 = std_ ./ mean_;
        logsm21 = log(logsm21 .* logsm21 + 1.0);
        return sqrt(logsm21);
    }

    real standard_normal_to_lognormal(real standard_normal, real mu, real sigma){
        return exp(mu + sigma * standard_normal);
    }

    real lognormal_to_standard_normal(real lognormal, real mu, real sigma){
        return (log(lognormal) - mu)/sigma;
    }

    row_vector standard_normal_to_lognormal_row(row_vector standard_normal, row_vector mu, row_vector sigma){
        return exp(mu + sigma .* standard_normal);
    }

}


data {
    int DEBUG; // flag to print debugging messages once (DEBUG > 0) or at every iteration (DEBUG > 1)
    int SIMULATE; // flag to fit data (SIMULATE < 1) or just generate data
    int UPSAMPLE; // flag and integer upsampling ratio for UPSAMPLE > 1
    int NORMAL; // flag to force normal distributions, for NORMAL =1

    int n_active_regions; // number of active regions
    int n_times; // 1012 // number of time points
    int n_target_data;   // number of target time series

    real dt; // integration time step, ~= 0.1 (used 0.0976562)
    row_vector[n_target_data] target_data[n_times]; // data to fit
    int LOG_TARGET_DATA; // flag, 1 for log, 0 for linear obervation function
    matrix[n_target_data, n_active_regions] gain; // source to sensor gain matrix

    // Constant dynamic model parameters
    real Iext1; //=3.1
    vector[n_active_regions] Ic; // Total input from non active regions
    matrix<lower=0.0, upper=1.0>[n_active_regions, n_active_regions] SC; // Structural connectivity input

    // Priors related data:

    // Epileptogenicity or Excitability
    int XMODE; // flag to sample x1eq (XMODE > 0) or x0
    real x_lo;
    real x_hi;
    row_vector [n_active_regions] x_mu;
    row_vector [n_active_regions] x_std;
    real x1_eq_def; // = -5.0/3 the value of all healhty non-active nodes, i.e. the resting manifold

    // Initial conditions
    row_vector [n_active_regions] x1_init_mu; // in [-2.0, -1.0], used -1.566
    row_vector [n_active_regions] z_init_mu; // in [2.9, 4.5], used 3.060
    real x1_init_lo;
    real x1_init_hi;
    real x1_init_std; // 0.0333
    real z_init_lo;
    real z_init_hi;
    real z_init_std; // 0.0333/2

    // Dynamic model hyperparameters

    // General time scale parameter
    int TAU1_PRIOR; // flag to fit tau1 (>0) or just dummy-sample it
    real tau1_mu; // 0.5
    real tau1_std; // 0.0667
    real tau1_lo;
    real tau1_hi;

    // Time scale separation parameter
    int TAU0_PRIOR; // flag to fit tau0 (>0) or just dummy-sample it
    real tau0_mu; // 0.5
    real tau0_std; // 0.0667
    real tau0_lo;
    real tau0_hi;

    // Global coupling scaling
    int K_PRIOR; // flag to fit K (>0) or just dummy-sample it
    real K_mu; // 3.448 = 3 * 100 / n_regions(=87)
    real K_std; // 0.575 = K_mu/6
    real K_lo;
    real K_hi;

    // Integration parameters
    int SDE; // flag to fit tau1 (>0) or just dummy-sample it
    real sigma_mu; // =0.1
    real sigma_std; // =0.1/2
    real sigma_lo; //0.05
    real sigma_hi; // 0.15

    // Observation model hyperparameters
    real epsilon_lo; //0.0
    real epsilon_hi; // 1.0
    real epsilon_mu; //=0.1
    real epsilon_std; //=0.1/3

    real offset_mu;  //=0.0
    real offset_std; //=1.0
    real offset_lo; //=offset_mu-1.0
    real offset_hi; //=offset_mu+1.0

    real scale_mu; //=0.5
    real scale_std; //=0.5/3
    real scale_lo; // =0.1
    real scale_hi; // =1.0

}


transformed data {
    // Effective time step
    real dtt = dt/UPSAMPLE;
    real sqrtdt = sqrt(dtt);

    // Transformations from standard normal to normal or lognormal distributions,
    // as well as of their upper ane lower limits

    // Assuming normal distributions

    // Epileptogenicity or Excitability
    row_vector[n_active_regions] x_logmu;
    row_vector[n_active_regions] x_logsigma;
    real x_star_lo;
    real x_star_hi;

    // Initial conditions
    real x1_init_star_lo = max((x1_init_lo - x1_init_mu)./x1_init_std);
    real x1_init_star_hi = min((x1_init_hi - x1_init_mu)./x1_init_std);
    real z_init_star_lo = max((z_init_lo - z_init_mu)./z_init_std);
    real z_init_star_hi = min((z_init_hi - z_init_mu)./z_init_std);

    // Dynamic model hyperparameters
    // Initializing to constant values
    real tau1_star_mu = tau1_mu;
    real tau1_star_std = 0.0001*(tau1_hi - tau1_lo);
    real tau1_star_lo = tau1_star_mu - 0.001;
    real tau1_star_hi = tau1_star_mu + 0.001;
    real tau1_mu_sigma[2];
    real tau0_star_mu = tau0_mu;
    real tau0_star_std = 0.0001*(tau0_hi - tau0_lo);
    real tau0_star_lo = tau0_star_mu - 0.001;
    real tau0_star_hi = tau0_star_mu + 0.001;
    real tau0_mu_sigma[2];
    real K_star_mu = K_mu;
    real K_star_std = 0.0001*(K_hi - K_lo);
    real K_star_lo = K_star_mu - 0.001;
    real K_star_hi = K_star_mu + 0.001;
    real K_mu_sigma[2];

    // Integration parameters
    // Initializing asumming ODE
    real dWt_star_std = 0.001;
    real sigma_star_std = 0.0001*(sigma_hi - sigma_lo);
    real sigma_star_lo = -0.001;
    real sigma_star_hi = 0.001;
    real sigma_mu_sigma[2];

    // Observation model hyperparameters
    // Assuming normals
    real epsilon_star_lo;
    real epsilon_star_hi;
    real epsilon_mu_sigma[2];
    real scale_star_lo;
    real scale_star_hi;
    real scale_mu_sigma[2];
    real offset_star_lo = (offset_lo - offset_mu)/offset_std;
    real offset_star_hi = (offset_hi - offset_mu)/offset_std;

    // Model connectivity constant
    matrix [n_active_regions, n_active_regions] SC_ = SC;
    for (i in 1:n_active_regions) SC_[i, i] = 0;
    SC_ = SC_ / max(SC_) * rows(SC_);

    // Dynamic model hyperparameters

    if (TAU1_PRIOR>0) {
        tau1_star_std = 1.0;
        if (NORMAL == 1) {
            tau1_star_lo = (tau1_lo - tau1_mu)/tau1_std;
            tau1_star_hi = (tau1_hi - tau1_mu)/tau1_std;
        } else {
            // Transformations for lognormal
            tau1_mu_sigma = normal_mean_std_to_lognorm_mu_sigma(tau1_mu, tau1_std);
            tau1_star_lo = lognormal_to_standard_normal(tau1_lo, tau1_mu_sigma[1], tau1_mu_sigma[2]);
            tau1_star_hi = lognormal_to_standard_normal(tau1_hi, tau1_mu_sigma[1], tau1_mu_sigma[2]);
        }
    }

    if (TAU0_PRIOR>0) {
        tau0_star_std = 1.0;
        if (NORMAL == 1) {
            tau0_star_lo = (tau0_lo - tau0_mu)/tau0_std;
            tau0_star_hi = (tau0_hi - tau0_mu)/tau0_std;
        } else {
            // Transformations for lognormal
            tau0_mu_sigma = normal_mean_std_to_lognorm_mu_sigma(tau0_mu, tau0_std);
            tau0_star_lo = lognormal_to_standard_normal(tau0_lo, tau0_mu_sigma[1], tau0_mu_sigma[2]);
            tau0_star_hi = lognormal_to_standard_normal(tau0_hi, tau0_mu_sigma[1], tau0_mu_sigma[2]);
        }
    }

    if (K_PRIOR>0) {
        K_star_std = 1.0;
        if (NORMAL == 1) {
            K_star_lo = (K_lo - K_mu)/K_std;
            K_star_hi = (K_hi - K_mu)/K_std;
        } else {
            // Transformations for lognormal
            K_mu_sigma = normal_mean_std_to_lognorm_mu_sigma(K_mu, K_std);
            K_star_lo = lognormal_to_standard_normal(K_lo, K_mu_sigma[1], K_mu_sigma[2]);
            K_star_hi = lognormal_to_standard_normal(K_hi, K_mu_sigma[1], K_mu_sigma[2]);
        }
    }

    if (NORMAL == 1) {
        x_star_lo = max((x_lo - x_mu)./x_std);
        x_star_hi = min((x_hi - x_mu)./x_std);
        epsilon_star_lo = (epsilon_lo - epsilon_mu)/epsilon_std;
        epsilon_star_hi = (epsilon_hi - epsilon_mu)/epsilon_std;
        scale_star_lo = (scale_lo - scale_mu)/scale_std;
        scale_star_hi = (scale_hi - scale_mu)/scale_std;
    } else {
        // Transformations for lognormals
        // Epileptogenicity or Excitability
        int indexes[n_active_regions];
        x_logmu = normal_mean_std_to_lognorm_mu(x_hi - x_mu, x_std);
        x_logsigma = normal_mean_std_to_lognorm_sigma(x_hi - x_mu, x_std);
        // Find the faster growing distribution...
        indexes = sort_indices_desc(standard_normal_to_lognormal_row(rep_row_vector(1.0, n_active_regions),
                                                                     x_logmu, x_logsigma));
        // ...and use it to compute the minimum x_star_hi
        x_star_hi = lognormal_to_standard_normal(x_hi - x_lo, x_logmu[indexes[1]], x_logsigma[indexes[1]]);
        x_star_lo = -10;

        // Observation model hyperparameters
        epsilon_mu_sigma = normal_mean_std_to_lognorm_mu_sigma(epsilon_mu, epsilon_std);
        if (epsilon_lo>0) {
            epsilon_star_lo = lognormal_to_standard_normal(epsilon_lo, epsilon_mu_sigma[1], epsilon_mu_sigma[2]);
        } else {
            epsilon_star_lo = -10.0;
            epsilon_star_hi = lognormal_to_standard_normal(epsilon_hi, epsilon_mu_sigma[1], epsilon_mu_sigma[2]);
        }
        scale_mu_sigma = normal_mean_std_to_lognorm_mu_sigma(scale_mu, scale_std);
        scale_star_lo = lognormal_to_standard_normal(scale_lo, scale_mu_sigma[1], scale_mu_sigma[2]);
        scale_star_hi = lognormal_to_standard_normal(scale_hi, scale_mu_sigma[1], scale_mu_sigma[2]);
    }

    // Integration parameters
    if (SDE>0) {
        dWt_star_std = 1.0;
        sigma_star_std = 1.0;
        if (NORMAL == 1) {
            sigma_star_lo = (sigma_lo - sigma_mu)/sigma_std;
            sigma_star_hi = (sigma_hi - sigma_mu)/sigma_std;
        } else {
            sigma_mu_sigma = normal_mean_std_to_lognorm_mu_sigma(sigma_mu, sigma_std);
            if (sigma_lo>0) {
                sigma_star_lo = lognormal_to_standard_normal(sigma_lo, sigma_mu_sigma[1], sigma_mu_sigma[2]);
            } else {
                sigma_star_lo = -10.0;
            }
            sigma_star_hi = lognormal_to_standard_normal(sigma_hi, sigma_mu_sigma[1], sigma_mu_sigma[2]);
        }
    }

    if (DEBUG > 0) {
        print("upsample=", UPSAMPLE, ", effective dt = dt/USPAMPLE = ", dtt);
        print("x_star_hi=", x_star_hi, ", x_star_lo=", x_star_lo);
        if (NORMAL<1){
            print("x_logmu=", x_logmu, ", x_logsigma=", x_logsigma,
                  ", x_mu=", x_hi - standard_normal_to_lognormal_row(rep_row_vector(0.0, n_active_regions),
                                                                     x_logmu, x_logsigma));
        }
        if ((TAU1_PRIOR>0) && (NORMAL<1)){
            print("tau1_mu_sigma=", tau1_mu_sigma,
                  ", tau1=", standard_normal_to_lognormal(0.0, tau1_mu_sigma[1], tau1_mu_sigma[2]));
        }
        print("tau1_star_std=", tau1_star_std, ", tau1_star_hi=", tau1_star_hi, ", tau1_star_lo=", tau1_star_lo);
        if ((TAU0_PRIOR>0) && (NORMAL<1)){
            print("tau0_mu_sigma=", tau0_mu_sigma,
                  ", tau0=", standard_normal_to_lognormal(0.0, tau0_mu_sigma[1], tau0_mu_sigma[2]));
        }
        print("tau0_star_std=", tau0_star_std, ", tau0_star_hi=", tau0_star_hi, ", tau0_star_lo=", tau0_star_lo);
        if ((K_PRIOR>0) && (NORMAL<1)){
            print("K_mu_sigma=", K_mu_sigma,
                  ", K=", standard_normal_to_lognormal(0.0, K_mu_sigma[1], K_mu_sigma[2]));
        }
        print("K_star_std=", K_star_std, ", K_star_hi=", K_star_hi, ", K_star_lo=", K_star_lo);
        if ((SDE>0) && (NORMAL<1)){
            print("sigma_mu_sigma=", sigma_mu_sigma,
                  ", sigma=", standard_normal_to_lognormal(0.0, sigma_mu_sigma[1], sigma_mu_sigma[2]));
        }
        print("sigma_star_std=", sigma_star_std, ", sigma_star_hi=", sigma_star_hi, ", sigma_star_lo=", sigma_star_lo);
        print("dWt_star_std=", dWt_star_std);
        if (NORMAL<1){
            print("scale_log_mu_sigma=", scale_mu_sigma,
                  ", scale_star_mu=", standard_normal_to_lognormal(0.0, scale_mu_sigma[1], scale_mu_sigma[2]),
                  ", scale_star_lo = ", scale_star_lo, ", scale_star_hi = ", scale_star_hi);
            print("epsilon_log_mu_sigma=", epsilon_mu_sigma,
                  ", epsilon_star_mu=", standard_normal_to_lognormal(0.0, epsilon_mu_sigma[1], epsilon_mu_sigma[2]),
                  ", epsilon_star_lo = ", epsilon_star_lo, ", epsilon_star_hi = ", epsilon_star_hi);
        } else {

            print("scale_star_lo = ", scale_star_lo, ", scale_star_hi = ", scale_star_hi);
            print("epsilon_star_lo = ", epsilon_star_lo, ", epsilon_star_hi = ", epsilon_star_hi);
        }
        print("offset_star_lo = ", offset_star_lo, ", offset_star_hi = ", offset_star_hi);
    }
}


parameters {
    // Epileptogenicity or Excitability
    row_vector<lower=x_star_lo, upper=x_star_hi>[n_active_regions] x_star;

    // Initial conditions
    row_vector<lower=x1_init_star_lo, upper=x1_init_star_hi>[n_active_regions] x1_init_star;
    row_vector<lower=z_init_star_lo, upper=z_init_star_hi>[n_active_regions] z_init_star;

    // Dynamic model hyperparameters
    real<lower=tau1_star_lo, upper=tau1_star_hi> tau1_star;
    real<lower=tau0_star_lo, upper=tau0_star_hi> tau0_star;
    real<lower=K_star_lo, upper=K_star_hi> K_star;

    // Integration parameters
    real<lower=sigma_star_lo, upper=sigma_star_hi> sigma_star;
    row_vector[n_active_regions] dWt_star[n_times - 1];

    // Observation model hyperparameters
    real<lower=epsilon_star_lo, upper=epsilon_star_hi>epsilon_star;
    real<lower=scale_star_lo, upper=scale_star_hi> scale_star;
    real<lower=offset_star_lo, upper=offset_star_hi> offset_star;

}


transformed parameters {

    // Epileptogenicity or Excitability
    row_vector[n_active_regions] x;
    row_vector[n_active_regions] x1eq; //x1 equilibrium point
    row_vector[n_active_regions] zeq; //z equilibrium point
    row_vector[n_active_regions] x0; // Excitability

    // Initial conditions
    row_vector[n_active_regions] x1_init = x1_init_mu + x1_init_star * x1_init_std;
    row_vector[n_active_regions] z_init = z_init_mu + z_init_star * z_init_std;

    row_vector[n_active_regions] x1[n_times];  // <lower=x1_lo, upper=x1_hi>
    row_vector[n_active_regions] z[n_times];

    // Dynamic model hyperparameters
    // Assuming constants/normals
    real tau1 = tau1_mu + tau1_std * tau1_star;
    real tau0 = tau1_mu + tau1_std * tau1_star;
    real K = tau1_mu + tau1_std * tau1_star;

    // Integration parameters
    real sigma = 0.0; // Assuming ODE

    // Observation model hyperparameters
    real epsilon;
    real offset = offset_mu + offset_std * offset_star; // always normal
    real scale;

    // Predicted target data
    row_vector[n_target_data] fit_target_data[n_times];

    if (NORMAL==1) {
        // Epileptogenicity or Excitability
        x = x_mu + x_std .* x_star;

        // Integration parameters
        // ODE or SDE selection
        if (SDE>0) {
            sigma = sigma_mu + sigma_std * sigma_star;
        }

        // Observation model hyperparameters
        epsilon = epsilon_mu + epsilon_std * epsilon_star;
        scale = scale_mu + scale_std * scale_star;
    } else {
        // Epileptogenicity or Excitability
        x = x_hi - standard_normal_to_lognormal_row(x_star, x_logmu, x_logsigma);

        // Dynamic model hyperparameters

        if (TAU1_PRIOR>0) {
            tau1 = standard_normal_to_lognormal(tau1_star, tau1_mu_sigma[1], tau1_mu_sigma[2]);
        }

        if (TAU0_PRIOR>0) {
            tau0 = standard_normal_to_lognormal(tau0_star, tau0_mu_sigma[1], tau0_mu_sigma[2]);
        }

        if (K_PRIOR>0) {
            K = standard_normal_to_lognormal(K_star, K_mu_sigma[1], K_mu_sigma[2]);
        }

         // Integration parameters
        // ODE or SDE selection
        if (SDE>0) {
            sigma = standard_normal_to_lognormal(sigma_star, sigma_mu_sigma[1], sigma_mu_sigma[2]);
        }

        // Observation model hyperparameters
        epsilon = standard_normal_to_lognormal(epsilon_star, epsilon_mu_sigma[1], epsilon_mu_sigma[2]);
        scale = standard_normal_to_lognormal(scale_star, scale_mu_sigma[1], scale_mu_sigma[2]);
    }

    // Selection of x1eq or x0 for fitting
    if (XMODE > 0) {
        // Sample x1eq, compute zeq, x0, and set initial conditions' priors around equilibria
        x1eq = x;
        zeq = calc_zeq(x1eq, Iext1, tau1);
        x0 = calc_x0(x1eq, zeq, SC, Ic, x1_eq_def);
        // x1_init= x1eq + x1_init_star * x1_init_std;
        // z_init= zeq + z_init_star * z_init_std;
    } else {
        // Sample x0, set initial conditions'priors and equilibria following input data
        x0 = x;
        x1eq = x1_init;
        zeq = z_init;
    }

    // Initial conditions
    x1[1] = x1_init; // - 1.5;
    z[1] = z_init; // 3.0;

    // Integration
    if (UPSAMPLE>1) {
        for (t in 1:(n_times-1)) {
            row_vector[n_active_regions] x1t = x1[t];
            row_vector[n_active_regions] zt = z[t];
            for (tt in 1:UPSAMPLE) {
                x1[t+1] = x1_step(x1t, zt, Iext1, dtt*tau1);
                z[t+1] = z_step(x1t, zt, x0, K*SC, Ic, x1_eq_def, dtt*tau1, dWt_star[t], sqrtdt*sigma, tau0);
                x1t = x1[t+1];
                zt = z[t+1];
            }
        }
    } else {
        for (t in 1:(n_times-1)) {
            x1[t+1] = x1_step(x1[t], z[t], Iext1, dtt*tau1); //, dX1t_star[t], sqrtdt*sigma
            z[t+1] = z_step(x1[t], z[t], x0, K*SC, Ic, x1_eq_def, dtt*tau1, dWt_star[t], sqrtdt*sigma, tau0);
        }
     }

    // Target data prediction
    if (LOG_TARGET_DATA>0) {
        for (t in 1:n_times)
            fit_target_data[t] = scale * (log(gain * exp(x1[t]'-x1_eq_def)))' + offset;
    } else {
        for (t in 1:n_times)
            fit_target_data[t] = scale * (gain * (x1[t]'-x1_eq_def))' + offset;
    }

    if (DEBUG > 1) {
        print("offset=", offset);
        print("scale=", scale);
        print("epsilon=", epsilon);
        print("K=", K);
        print("sigma=", sigma);
        print("tau1=", tau1);
        print("tau0=", tau0);
        print("x0=", x0);
        print("x1eq=", x1eq);
        print("zeq=", zeq);
        print("x1_init=", x1_init);
        print("z_init=", z_init);
        print("sum(x1(1))=", sum(x1[1]));
        print("sum(z(1))=", sum(z[1]));
        print("sum(fit_target_data(1))=", sum(fit_target_data[1]));
        print("sum(x1(end))=", sum(x1[n_times]));
        print("sum(z(end))=", sum(z[n_times]));
        print("sum(fit_target_data(end))=", sum(fit_target_data[n_times]));
        if (DEBUG>2) {
            for (t in 1:n_times) {
                print("x1(", t, ")=", x1[t]);
                print("z(", t, ")=", z[t]);
                print("fit_target_data(", t, ")=", fit_target_data[t]);
            }
        }
    }


}


model {

    // Epileptogenicity or Excitability
    x_star ~ normal(0.0, 1.0);

    // Initial conditions
    to_row_vector(x1_init_star) ~ normal(0.0, 1.0);
    to_row_vector(z_init_star) ~ normal(0.0, 1.0);

    // Dynamic model hyperparameters
    tau1_star ~ normal(0.0, tau1_star_std);
    tau0_star ~ normal(0.0, tau0_star_std);
    K_star ~ normal(0.0, K_star_std);

    // Integration parameters
    sigma_star ~ normal(0.0, sigma_star_std);
    for (t in 1:(n_times - 1)) {
        to_vector(dWt_star[t]) ~ normal(0.0, dWt_star_std);
    }

    // Observation model hyperparameters
    epsilon_star ~ normal(0.0, 1.0);
    offset_star ~ normal(0.0, 1.0);
    scale_star ~ normal(0.0, 1.0);

    // Fit or forward simulation
    if (SIMULATE<1)
        for (t in 1:n_times)
            target_data[t] ~ normal(fit_target_data[t], epsilon);
}


generated quantities {
    // Log-likelihood computation for information criteria metrics
    row_vector[n_target_data] log_likelihood[n_times];
    for (t in 1:n_times) {
        for (s in 1:n_target_data) {
            log_likelihood[t][s] = normal_lpdf(target_data[t][s] |  fit_target_data[t][s], epsilon);
        }
    }
}
