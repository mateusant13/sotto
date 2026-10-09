import numpy as np, math, sys
sys.path.insert(0, r"H:\sotto\worker")
import denoise as D
rng = np.random.default_rng(20261008)
sr = 16000
noise = (rng.standard_normal(sr*3)*0.01).astype(np.float32)
g = D.SpectralGate(sr=sr)
y = g.process(noise)
st = g.stats()
in_rms = float(np.sqrt(np.mean(noise.astype(np.float64)**2)))
print("in_rms", in_rms, "p_db", 10*math.log10(in_rms**2))
print("noise_db_mean", st["noise_db_mean"], "gain_db_mean", st["gain_db_mean"])
print("bias_meas", 10**((10*math.log10(in_rms**2) - st["noise_db_mean"])/10))
# direct: mean(Psm)/mean(Nf) and mean(P_windowed)
print("hann mean-square", float(np.mean(np.hanning(513)[:-1]**2)))
print("stats", {k: st[k] for k in ("frames","atten_frac","gain_db_p10","gain_db_p90")})
