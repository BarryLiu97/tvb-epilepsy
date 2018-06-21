functions {

    matrix vector_differencing(row_vector x1) {
        matrix[num_elements(x1), num_elements(x1)] D;
        for (i in 1:num_elements(x1)) {
            D[i] = x1 - x1[i];
        }
        return D;
    }

    row_vector x1_step(row_vector x1, row_vector z, real Iext1, real tau1) { //, row_vector dX1t, real sigma
        int n_active_regions = num_elements(x1);
        row_vector[n_active_regions] x1_next;
        row_vector[n_active_regions] Iext1_vec = rep_row_vector(Iext1 + 1.0, n_active_regions);
        row_vector[n_active_regions] dx1 = Iext1_vec - (x1 .* x1 .* x1) - 2.0 * (x1 .* x1) - z;
        x1_next = x1 + (tau1 * dx1); # + dX1t * sigma;
        return x1_next;
    }

    row_vector z_step(row_vector x1, row_vector z, row_vector x0, matrix FC, vector Ic, real x1_eq_def, real tau1,
                      row_vector dZt, real sigma, real tau0) {
        int n_active_regions = num_elements(z);
        row_vector[n_active_regions] z_next;
        matrix[n_active_regions, n_active_regions] D = vector_differencing(x1);
        // Ic = Ic_i = sum_{j in nonactive regions} [w_ij]
        // gx(nonactive->active) = Ic * (x1_j - x1_i) = Ic * (x1_eq_def - x1)
        row_vector[n_active_regions] gx = to_row_vector(rows_dot_product(FC, D) + Ic .* to_vector(x1_eq_def - x1));
        row_vector[n_active_regions] dz = inv(tau0) * (4 * (x1 - x0) - z - gx);
        z_next = z + (tau1 * dz) + dZt * sigma;
        return z_next;
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
    int DEBUG;
    int SIMULATE;
    int n_active_regions;
    int n_times; // 1012
    int n_target_data;
    real Iext1; //=3.1
    real dt; //~= 0.1 (used 0.0976562)
    real x0_hi; // 2.5
    // real x0_std; // ~0.5
    // real x0_lo;  // 0.0
    row_vector [n_active_regions] x0_star_mu; // x0_hi - x0_mean = 2.5 - ~[-2.5 to 0.0] = ~[2.5 to 5]
    row_vector [n_active_regions] x0_star_std; // minimum((x0_mean - x0_lo)/2.0) ~= 1.0
    // row_vector [n_active_regions] x0_mu;  // healthy: -2.5, sick ~=-2.0, max = [-3.0, -4.0], min = -1.0
    real x1_eq_def; // = -5.0/3 the value of all healhty non-active node
    real x1_lo;
    real x1_hi;
    int X1_PRIOR;
    row_vector[n_active_regions] x1_loc;
    row_vector[n_active_regions] x1_mu;
    row_vector[n_active_regions] x1_sigma;
    row_vector [n_active_regions] x1_init_mu; // in [-2.0, -1.0], used -1.566
    row_vector [n_active_regions] z_init_mu; // in [2.9, 4.5], used 3.060
    real x1_init_lo;
    real x1_init_hi;
    real x1_init_std; // 0.0333
    real z_init_std; // 0.0333/2
    int TAU1_PRIOR;
    real tau1_mu; // 0.5
    real tau1_std; // 0.0667
    real tau1_lo;
    real tau1_hi;
    int TAU0_PRIOR;
    real tau0_mu; // 0.5
    real tau0_std; // 0.0667
    real tau0_lo;
    real tau0_hi;
    int K_PRIOR;
    real K_mu; // 3.448 = 3 * 100 / n_regions(=87)
    real K_std; // 0.575 = K_mu/6
    real K_lo;
    real K_hi;
    int SDE;
    real sigma_mu; // =0.05
    real sigma_std; // =0.01/3
    real sigma_lo; //0
    real sigma_hi; // 0.15
    real epsilon_mu; //=0.1
    real epsilon_std; //=0.1/3
    real offset_mu;  //=0.0
    real offset_std; //=1.0
    real scale_mu; //=1.0
    real scale_std; //=1.0/6
    real scale_lo; // =0.3
    int log_target_data; // 1 for log, 0 for linear obervation function
    matrix[n_target_data, n_active_regions] gain;
    row_vector[n_target_data] target_data[n_times];
    vector[n_active_regions] Ic;
    matrix<lower=0.0, upper=1.0>[n_active_regions, n_active_regions] SC;
}

transformed data {
    real sqrtdt = sqrt(dt);
    real scale_mu_sigma[2] = normal_mean_std_to_lognorm_mu_sigma(scale_mu, scale_std);
    real epsilon_mu_sigma[2] = normal_mean_std_to_lognorm_mu_sigma(epsilon_mu, epsilon_std);
    real sigma_star_lo = -1.0;
    real sigma_star_hi = 1.0;
    real sigma_mu_sigma[2] = normal_mean_std_to_lognorm_mu_sigma(sigma_mu, sigma_std);
    real tau1_star_lo = -1.0;
    real tau1_star_hi = 1.0;
    real tau1_mu_sigma[2] = normal_mean_std_to_lognorm_mu_sigma(tau1_mu, tau1_std);
    real tau0_star_lo = -1.0;
    real tau0_star_hi = 1.0;
    real tau0_mu_sigma[2] = normal_mean_std_to_lognorm_mu_sigma(tau0_mu, tau0_std);
    real K_star_lo = -1.0;
    real K_star_hi = 1.0;
    real K_mu_sigma[2] = normal_mean_std_to_lognorm_mu_sigma(K_mu, K_std);
    row_vector[n_active_regions] x0_logmu = normal_mean_std_to_lognorm_mu(x0_star_mu, x0_star_std);
    row_vector[n_active_regions] x0_sigma = normal_mean_std_to_lognorm_sigma(x0_star_mu, x0_star_std);
    matrix [n_active_regions, n_active_regions] SC_ = SC;
    for (i in 1:n_active_regions) SC_[i, i] = 0;
    SC_ = SC_ / max(SC_) * rows(SC_);

    if (SDE>0) {
        if (sigma_lo>0) {
            sigma_star_lo = lognormal_to_standard_normal(sigma_lo, sigma_mu_sigma[1], sigma_mu_sigma[2]);
        } else {
            sigma_star_lo = -1000.0;
        }
        sigma_star_hi = lognormal_to_standard_normal(sigma_hi, sigma_mu_sigma[1], sigma_mu_sigma[2]);
    }

    if (TAU1_PRIOR>0) {
        tau1_star_lo = lognormal_to_standard_normal(tau1_lo, tau1_mu_sigma[1], tau1_mu_sigma[2]);
        tau1_star_hi = lognormal_to_standard_normal(tau1_hi, tau1_mu_sigma[1], tau1_mu_sigma[2]);
    }

    if (TAU0_PRIOR>0) {
        tau0_star_lo = lognormal_to_standard_normal(tau0_lo, tau0_mu_sigma[1], tau0_mu_sigma[2]);
        tau0_star_hi = lognormal_to_standard_normal(tau0_hi, tau0_mu_sigma[1], tau0_mu_sigma[2]);
    }

    if (K_PRIOR>0) {
        K_star_lo = lognormal_to_standard_normal(K_lo, K_mu_sigma[1], K_mu_sigma[2]);
        K_star_hi = lognormal_to_standard_normal(K_hi, K_mu_sigma[1], K_mu_sigma[2]);
    }

    if (DEBUG > 0) {
        print("scale_mu_sigma=", scale_mu_sigma,
              ", scale=", standard_normal_to_lognormal(0.0, scale_mu_sigma[1], scale_mu_sigma[2]));
        print("epsilon_mu_sigma=", epsilon_mu_sigma,
              ", epsilon=", standard_normal_to_lognormal(0.0, epsilon_mu_sigma[1], epsilon_mu_sigma[2]));
        if (TAU1_PRIOR>0) {
            print("tau1_mu_sigma=", tau1_mu_sigma,
                  ", tau1=", standard_normal_to_lognormal(0.0, tau1_mu_sigma[1], tau1_mu_sigma[2]));
        }
        if (TAU0_PRIOR>0) {
            print("tau0_mu_sigma=", tau1_mu_sigma,
                  ", tau0=", standard_normal_to_lognormal(0.0, tau0_mu_sigma[1], tau0_mu_sigma[2]));
        }
        if (K_PRIOR>0) {
            print("K_mu_sigma=", K_mu_sigma,
                  ", k=", standard_normal_to_lognormal(0.0, K_mu_sigma[1], K_mu_sigma[2]));
        }
        if (SDE>0) {
            print("sigma_mu_sigma=", sigma_mu_sigma,
                  ", sigma=", standard_normal_to_lognormal(0.0, sigma_mu_sigma[1], sigma_mu_sigma[2]));
        }
        print("x0_logmu=", x0_logmu, ", x0_sigma=", x0_sigma);
    }
}

parameters {
    // integrate and predict
    row_vector [n_active_regions] x0_star;
    real epsilon_star;
    real scale_star;
    real offset_star;
    real<lower=sigma_star_lo, upper=sigma_star_hi> sigma_star;
    real<lower=tau1_star_lo, upper=tau1_star_hi> tau1_star;
    real<lower=tau0_star_lo, upper=tau0_star_hi> tau0_star;
    real<lower=K_star_lo, upper=K_star_hi> K_star;

    // time-series state non-centering:
    row_vector<lower=x1_init_lo-max(x1_init_mu), upper=x1_init_hi-min(x1_init_mu)>[n_active_regions] x1_init_star;
    row_vector[n_active_regions] z_init_star;
    // row_vector[n_active_regions] dX1t_star[n_times - 1];
    row_vector[n_active_regions] dZt_star[n_times - 1];

}

transformed parameters {
    real offset = offset_mu + offset_star * offset_std;
    real scale = standard_normal_to_lognormal(scale_star, scale_mu_sigma[1], scale_mu_sigma[2]);
    real epsilon = standard_normal_to_lognormal(epsilon_star, epsilon_mu_sigma[1], epsilon_mu_sigma[2]);
    real sigma;
    real tau1;
    real tau0;
    real K;
    row_vector[n_active_regions] x0 = x0_hi - standard_normal_to_lognormal_row(x0_star, x0_logmu, x0_sigma);
    row_vector<lower=x1_lo, upper=x1_hi>[n_active_regions] x1_init = x1_init_mu + x1_init_star * x1_init_std;
    row_vector[n_active_regions] z_init = z_init_mu + z_init_star * z_init_std;
    row_vector<lower=x1_lo, upper=x1_hi>[n_active_regions] x1[n_times];
    row_vector[n_active_regions] z[n_times];
    row_vector[n_target_data] fit_target_data[n_times];

    if (SDE>0) {
        sigma = standard_normal_to_lognormal(sigma_star, sigma_mu_sigma[1], sigma_mu_sigma[2]);
    } else {
        sigma = sigma_mu + sigma_std * sigma_star;
    }

    if (TAU1_PRIOR>0) {
        tau1 = standard_normal_to_lognormal(tau1_star, tau1_mu_sigma[1], tau1_mu_sigma[2]);
    } else {
        tau1 = tau1_mu + tau1_std * tau1_star;
    }

    if (TAU0_PRIOR>0) {
        tau0 = standard_normal_to_lognormal(tau0_star, tau0_mu_sigma[1], tau0_mu_sigma[2]);
    } else {
        tau0 = tau0_mu + tau0_std * tau0_star;
    }

    if (K_PRIOR>0) {
        K = standard_normal_to_lognormal(K_star, K_mu_sigma[1], K_mu_sigma[2]);
    } else {
        K = K_mu + K_std * K_star;
    }

    x1[1] = x1_init; // - 1.5;
    z[1] = z_init; // 3.0;
    for (t in 1:(n_times-1)) {
        x1[t+1] = x1_step(x1[t], z[t], Iext1, dt*tau1); //, dX1t_star[t], sqrtdt*sigma
        z[t+1] = z_step(x1[t], z[t], x0, K*SC, Ic, x1_eq_def, dt*tau1, dZt_star[t], sqrtdt*sigma, tau0);
    }

    if (log_target_data>0) {
        for (t in 1:n_times)
            fit_target_data[t] = scale * (log(gain * exp(x1[t]'-x1_eq_def)) + offset)';
    } else {
        for (t in 1:n_times)
            fit_target_data[t] = scale * (gain * (x1[t]'-x1_eq_def) + offset)';
    }

    if (DEBUG > 0) {
        print("offset=", offset);
        print("scale=", scale);
        print("epsilon=", epsilon);
        print("K=", K);
        print("sigma=", sigma);
        print("tau1=", tau1);
        print("tau0=", tau0);
        print("x0=", x0);
    }
}

model {
    offset_star ~ normal(0.0, 1.0);
    scale_star ~ normal(0.0, 1.0);
    epsilon_star ~ normal(0.0, 1.0);
    sigma_star ~ normal(0.0, 1.0);
    tau1_star ~ normal(0.0, 1.0);
    tau0_star ~ normal(0.0, 1.0);
    K_star ~ normal(0.0, 1.0);
    to_row_vector(x0_star) ~ normal(0.0, 1.0);
    x1_init_star ~ normal(0.0, 1.0);
    z_init_star ~ normal(0.0, 1.0);

    for (t in 1:(n_times - 1)) {
        // to_vector(dX1t_star[t]) ~ normal(0.0, 1.0);
        to_vector(dZt_star[t]) ~ normal(0.0, 1.0);
    }

    if (X1_PRIOR>0) {
         for (t in 1:(n_times - 1))
            to_vector(x1[t] - x1_lo - x1_loc) ~ lognormal(x1_mu, x1_sigma);
    }

    if (SIMULATE<1)
        for (t in 1:n_times)
            target_data[t] ~ normal(fit_target_data[t], epsilon);
}


generated quantities {
    row_vector[n_target_data] log_likelihood[n_times];
    for (t in 1:n_times) {
        for (s in 1:n_target_data) {
            log_likelihood[t][s] = normal_lpdf(target_data[t][s] |  fit_target_data[t][s], epsilon);
        }
    }
}
