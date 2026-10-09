import numpy as np, math, sys
sys.path.insert(0, r"H:\sotto\worker")
import denoise as D

rng = np.random.default_rng(7)
sr = 16000
noise = (rng.standard_normal(sr*6)*0.01).astype(np.float32)

for decay in (1.002, 1.01, 1.02):
    g = D.SpectralGate(sr=sr, noise_decay=decay)
    g.process(noise)
    psm = np.asarray([], np.float64)
    nf = np.asarray([], np.float64)
    # re-run capturing the internal arrays per frame by monkeypatching
    ratios = []
    g2 = D.SpectralGate(sr=sr, noise_decay=decay)
    orig = g2._frame_gain
    def spy(P, _g=g2, _o=orig, _r=ratios):
        out = _o(P)
        _r.append((float(np.mean(_g._psm)), float(np.mean(_g._noise))))
        return out
    g2._frame_gain = spy
    g2.process(noise)
    r = np.asarray(ratios[100:], np.float64)  # steady state
    print("decay=%.3f  mean(Psm)/mean(Nf) = %.3f   mean(Nf)/mean(P) = %.3f   frames=%d"
          % (decay, np.mean(r[:,0]/r[:,1]), np.mean(r[:,1])/np.mean(r[:,0]), len(ratios)))
