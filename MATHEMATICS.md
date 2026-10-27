# Arithmetic WTI multi-factor research model

Time is trading years: 252 sessions times 23 hours per year.
Price P is USD/barrel and may be negative.
Inventory I and assumed working capacity C are million barrels.
V is arithmetic variance, USD^2/barrel^2/year.

## Price system

dP = [kappa*(anchor-P) + M + betaQ*(F-1) - B(I,tau) + R]dt
     + sqrt(V)dW_P + J_g dN_g + sum_k J_E,k delta_Tk(dt)

M = -beta_r*(real_yield-1.5) - beta_D*dollar_change

crack = 42*(2*RBOB + ULSD)/3 - CL

F = exp(0.35*tanh((crack-15)/10)
        + 0.25*tanh((refinery_utilization-88)/5))

u = I/C
softplus_k(x) = log(1+exp(k*x))/k

B = 500*tanh(
    60*exp(-tau/30)*softplus_30(u-0.85)
    / (500*max(1-u,0.02))
)

tau is the user-supplied remaining expiry time, held fixed in a snapshot.
This is a storage-pressure hypothesis, not a calibrated reconstruction of 2020.
Available storage, lease commitments, delivery access and roll mechanics are absent.

## Variance and inventory

Theta = clip(
    sigma0^2 * exp(0.25*tanh(freight_z)+0.2*tanh(curve_slope/10)),
    1, 120^2
)

dV = 5*(Theta-V)dt + 12*sqrt(V)dW_V

corr(dW_P,dW_V) = -0.45

dI = 4*dW_I + reflection at 0 and C

sigma0 is estimated from 60 completed daily arithmetic price differences.
Continuous-contract roll changes can distort this estimate.
Positive annual dollar curve slope means contango.
Freight is an observed standardized VLCC rate, not an invented shipping proxy.

## Jumps and EIA

Geopolitical events follow Poisson intensity 4/year.
Their independent jump sizes are Normal(0, 3^2) USD/barrel.
Conditional on n events, total jump size is 3*sqrt(n)*Z.

Future EIA releases use scheduled Normal(0,1) jumps.
Default schedule: Wednesday 10:30 America/New_York, with regular weekly spacing.
Holiday exceptions are not supplied by an external calendar.

Latest EIA surprise is an own-forecast residual using preceding weekly changes,
not paid analyst consensus. Its assumed drift response decays over 46 trading hours.

## Numerical method

Euler-Maruyama uses correlated normal draws.
Variance is clipped to [1,120^2] as a numerical safeguard.
Inventory overshoots are reflected; prices are never floored at zero.
Frequent upper variance clipping blocks public signals.
The snapshot seed makes the random draws reproducible.

## Signals and TP/SL

Actions require a completed-history mean +/-1.5 standard-deviation breakout
and at least 60% modeled terminal share beyond assumed round-trip costs.
Strong labels additionally require the entire 5th-95th percentile modeled interval
beyond the current quote and costs.

Missing, stale, future-dated or unverified public inputs force HOLD.
HOLD does not receive invented TP/SL levels.

Let b = B/500 and R = sigma0*sqrt(T)*sqrt(1+2*b).
TP is quote +/-1.8*R.
Long SL is quote-R/(1+b).
Short SL is quote+R*(1+b).

These are unvalidated risk references, not guaranteed fills.
The displayed interval is a model predictive interval, not proof of a trading edge.
No fitted full-factor backtest or profitability claim is included.