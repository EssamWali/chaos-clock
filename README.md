# Chaos Clock

Twenty thousand particles chase a Lorenz attractor and, every fifteen seconds,
stop chasing it and arrange themselves into the current time. Each particle
integrates its own copy of the Lorenz equations from a starting point that
differs from its neighbours' by a nudge of order `1e-2`; the same equations from
near-identical states produce visibly unrelated trajectories within a few
seconds. The clock is what happens when a second force is switched on and
outweighs the chaos. A single Python file, pygame and numpy.

![Particles on the Lorenz attractor collapsing into the digits 13:14](docs/demo.gif)

## How it works

### One Lorenz state per particle

Every particle carries its own `(x, y, z)` state, initialised at `(0.1, 0, 0)`
plus Gaussian noise of scale `1e-2`, and advanced each frame by one Euler step of
the Lorenz system (`σ = 10`, `ρ = 28`, `β = 8/3`, `dt = 0.01`). The state's `x`
and `y` are mapped from `[-30, 30]` onto the window (x to width, y to height,
inverted), giving each particle a private point on the attractor to chase. The
divergence is exponential but takes a few hundred steps to become visible, which
is why recordings run a warm-up before the first kept frame.

### Two forces

Each step, a particle's velocity is damped by `0.98`, then pulled toward its
attractor point with strength `0.001`. While the clock is showing, it is also
pulled toward an assigned pixel of the digits with strength `0.004`, and the
attractor pull is scaled down to a tenth (see below). Positions are updated by
the velocity and bounce off the window edges. Nothing else acts on them.

### Digits into targets

The current time (`%H:%M`) is rasterised with `pygame.freetype` in Orbitron at
160 px. The alpha channel is thresholded at 20, the coordinates of the lit
pixels are scaled so the text spans 90% of the window width and centred, and
those coordinates become the particles' destinations. When there are more
particles than lit pixels (the usual case), destinations are sampled with
replacement and jittered with Gaussian noise of 1.5 px, so the digits read as a
cloud rather than as stacks of particles on identical coordinates. Targets are
recomputed whenever the minute changes.

### The chaos pull while the clock shows

At full strength the attractor pull prevents the clock from forming once the
Lorenz states have diverged: each particle is dragged toward a different part of
the attractor, the pulls no longer cancel, and the two forces reach equilibrium
with particles sitting about 50 px from their targets. Mean distance from each
particle to its target after 800 steps of attraction, starting from a fully
diverged state (2,000 free steps, 20,000 particles, 800×600):

| chaos pull kept while the clock shows | mean error |
| --- | ---: |
| 100% | 52.30 px |
| 50% | 28.62 px |
| 25% | 14.97 px |
| **10%** | **6.16 px** |
| 0% | 0.05 px |

The code keeps 10% (`LORENZ_WHEN_SHOWING = 0.1`). Zero gives a perfectly still
clock; a tenth keeps the digits shimmering. CI asserts the mean error stays under
15 px from the same diverged start.

## Performance

Two renderers are included. `render_circles` calls `pygame.draw.circle` once per
particle; `render_scatter` writes a 3×3 block for every particle into a
`(width, height, 3)` numpy array with nine fancy-index assignments and blits the
array once. Measured with `--benchmark` at 20,000 particles, 800×600, on one
machine:

| | ms/frame | end-to-end fps |
| --- | ---: | ---: |
| physics only | 0.67 | — |
| render: `pygame.draw.circle` ×20,000 | 23.60 | 41.2 |
| render: numpy scatter, one blit | 6.30 | **143.5** |

3.7× on the render and 3.5× end to end. Absolute figures vary by machine; the
ordering is what CI checks. The scatter renderer is the default; `--trails` fades
the previous frame instead of clearing it.

## Running it

```
pip install -r requirements.txt

python chaos_clock.py                     # open a window
python chaos_clock.py --benchmark         # compare the two renderers
python chaos_clock.py --trails 0.9        # fading trails
python chaos_clock.py --record demo.gif --warmup 2000 --switch-at 400 \
    --frames 110 --every 12 --scale 0.5   # the GIF above, headless
```

Other options: `--particles`, `--width`, `--height`, `--fps`, `--interval`
(seconds between chaos and clock, default 15), `--renderer circles`. Recording
runs with a dummy SDL video driver and needs no display.

## Files

| | |
| --- | --- |
| `chaos_clock.py` | Simulation, both renderers, benchmark, GIF recorder. |
| `Orbitron-Regular.ttf` | The clock face. SIL Open Font License 1.1, see `OFL.txt`. |
| `docs/demo.gif` | The recording above. |
| `.github/workflows/ci.yml` | Checks the scatter renderer is faster and the clock still forms. |

The font is [Orbitron](https://github.com/theleagueof/orbitron) by The Orbitron
Project Authors, used under the SIL Open Font License 1.1.

More: [development notes](docs/notes.md).
