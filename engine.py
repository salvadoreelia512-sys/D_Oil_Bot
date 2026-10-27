import math
import numpy as np

YEAR_HOURS = 252*23

def number(inputs, key, default=0):
    item = inputs[key]["value"]
    return default if item is None else float(item)

def penalty(stock, capacity, expiry):
    u = np.asarray(stock)/capacity
    soft = np.logaddexp(0, 30*(u-.85))/30
    raw = 60*np.exp(-expiry/30)*soft/np.maximum(1-u, .02)
    return 500*np.tanh(raw/500)

def simulate(inputs, history, capacity=76., expiry=20.,
             hours=115., paths=3000, seed=42, events=()):
    if inputs["price"]["value"] is None:
        raise ValueError("Current price unavailable")
    if not 0 < capacity or expiry < 0:
        raise ValueError("Invalid capacity or expiry")
    stock = number(inputs, "inventory", capacity*.6)
    if not 0 <= stock <= capacity:
        raise ValueError("Inventory exceeds assumed capacity; verify capacity")
    sigma = float(np.std(np.diff(history[-61:]), ddof=1)*np.sqrt(252)) if len(history)>=90 else 25.
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("Invalid estimated volatility")
    sigma = np.clip(sigma, 1, 120)
    anchor = float(np.median(history[-60:])) if history else number(inputs, "price")
    rng = np.random.default_rng(seed)
    steps = max(24, min(1000, int(hours*2)))
    grid = np.linspace(0, hours, steps+1)
    dt = hours/YEAR_HOURS/steps
    price = np.full(paths, number(inputs, "price"))
    variance = np.full(paths, sigma*sigma)
    inventory = np.full(paths, stock)
    samples = np.empty((steps+1, paths), np.float32)
    variance_mean = np.empty(steps+1)
    inventory_bands = np.empty((steps+1, 3))
    samples[0] = price
    variance_mean[0] = variance.mean()
    inventory_bands[0] = np.quantile(inventory, [.05, .5, .95])
    target = np.clip(sigma*sigma*np.exp(
        .25*np.tanh(number(inputs, "freight")) +
        .2*np.tanh(number(inputs, "curve")/10)), 1, 120**2)
    multiplier = np.exp(
        .35*np.tanh((number(inputs, "crack", 15)-15)/10) +
        .25*np.tanh((number(inputs, "utilization", 88)-88)/5))
    macro = -4*(number(inputs, "rate", 1.5)-1.5)-25*number(inputs, "dollar")
    event_steps = [int(np.searchsorted(grid, t))
                   for t in events if 0 < t <= hours]
    cap_count = 0
    for j in range(1, steps+1):
        zp, independent, zi = rng.standard_normal((3, paths))
        zv = -.45*zp+math.sqrt(1-.45**2)*independent
        response = -3*np.tanh(number(inputs, "surprise"))*2**(-grid[j]/46)
        drift = anchor-price+macro+12*(multiplier-1)+response-penalty(inventory, capacity, expiry)
        counts = rng.poisson(4*dt, paths)
        price += drift*dt + np.sqrt(variance*dt)*zp
        price += 3*np.sqrt(counts)*rng.standard_normal(paths)
        for _ in range(event_steps.count(j)):
            price += rng.standard_normal(paths)
        candidate = variance+5*(target-variance)*dt+12*np.sqrt(variance*dt)*zv
        cap_count += np.count_nonzero(candidate > 120**2)
        variance = np.clip(candidate, 1, 120**2)
        inventory += 4*math.sqrt(dt)*zi
        inventory = capacity-np.abs(np.mod(inventory, 2*capacity)-capacity)
        samples[j] = price
        variance_mean[j] = variance.mean()
        inventory_bands[j] = np.quantile(inventory, [.05, .5, .95])
    if not np.isfinite(samples).all():
        raise ValueError("Numerical instability")
    return dict(grid=grid, samples=samples, variance=variance_mean,
                inventory=inventory_bands,
                bands=np.quantile(samples, [.05, .5, .95], axis=1).T,
                sigma=float(sigma), cap_fraction=float(cap_count/(steps*paths)))

def signal(inputs, history, sim, now, capacity, expiry,
           demo_mode=False, verified=False):
    limits = dict(price=1/3, rate=240, dollar=120, inventory=504,
                  utilization=504, crack=120, freight=240,
                  curve=120, surprise=504)
    blockers = []
    for key, limit in limits.items():
        obs = inputs[key]
        if obs["value"] is None:
            blockers.append(key+": missing")
        elif not np.isfinite(obs["value"]):
            blockers.append(key+": invalid")
        elif not demo_mode:
            age = (now-obs["date"]).total_seconds()/3600 if obs["date"] else float("inf")
            if obs["status"] not in ("observed", "proxy") or not -1/12 <= age <= limit:
                blockers.append(key+": stale, future-dated or unobserved")
    if len(history)<90:
        blockers.append("Insufficient completed daily history")
    if not demo_mode and not verified:
        blockers.append("Physical assumptions and release schedule not verified")
    if not demo_mode and sim["grid"][-1]/YEAR_HOURS*365.25 >= expiry:
        blockers.append("Horizon crosses assumed expiry; no roll model")
    if sim["cap_fraction"]>.01:
        blockers.append("Numerical variance cap active")
    spot = number(inputs, "price")
    endpoint = sim["samples"][-1]
    up, down = float(np.mean(endpoint>spot+.04)), float(np.mean(endpoint<spot-.04))
    low, high = np.quantile(endpoint, [.05, .95])
    past = history[-20:]
    center = float(np.mean(past)) if past else spot
    width = max(.01, float(np.std(past))) if past else float("inf")
    action, direction = "HOLD", 0
    if not blockers:
        if spot>center+1.5*width and up>=.6:
            action, direction = ("STRONG LONG" if low>spot+.04 else "LONG NOW"), 1
        elif spot<center-1.5*width and down>=.6:
            action, direction = ("STRONG SHORT" if high<spot-.04 else "SELL NOW"), -1
    pressure = float(penalty(number(inputs, "inventory", capacity*.6), capacity, expiry))/500
    risk = max(.01, sim["sigma"]*math.sqrt(sim["grid"][-1]/YEAR_HOURS)*math.sqrt(1+2*pressure))
    tp = spot+direction*1.8*risk if direction else None
    sl = spot-risk/(1+pressure) if direction==1 else spot+risk*(1+pressure) if direction==-1 else None
    return dict(action=action, up=up, down=down,
                low=float(low), high=float(high), tp=tp, sl=sl,
                blockers=blockers)