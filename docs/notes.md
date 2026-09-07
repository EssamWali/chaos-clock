# Development notes

## Making it fast

The first version drew each particle with `pygame.draw.circle`. Twenty thousand
calls a frame is 1.2 million a second at 60 fps, and almost all of that cost is
call overhead rather than pixels. It could not hold 60 fps on a machine that had
no trouble with the physics.

Scattering the particles into a numpy array and blitting once moves the loop out
of Python entirely:

| | ms/frame | end-to-end fps |
| --- | ---: | ---: |
| physics only | 0.67 | — |
| render: `pygame.draw.circle` ×20,000 | 23.60 | 41.2 |
| render: numpy scatter, one blit | 6.30 | **143.5** |

3.7× on the render, 3.5× end to end, and it clears 60 fps with room to spare.
Reproduce with `--benchmark`.

The original drew a radius-2 circle, which is about thirteen pixels; the scatter
renderer writes a 3×3 block, which reads a little crisper and costs a third as
much.

### What did not work

The obvious next step is to flatten the nine per-particle offsets into one big
fancy-index assignment instead of nine smaller ones. It is slower, 6.5 ms against
5.1, because the `np.repeat` needed to line the colours up allocates more than
the batching saves. The simpler code was also the faster code.

## The clock that would not form

Running it for a while, the digits stopped resolving. They would gather into a
smear roughly the right shape and stay there.

It is not a rendering problem, it is the physics. Early in a session every
particle's Lorenz state is still close to the origin, so the chaos force is small
and points much the same way for all of them, and the text attraction wins
easily. Once the states have diverged, which is the entire point of the piece,
every particle is being dragged toward a different part of the attractor, and
those pulls no longer cancel. The two forces reach equilibrium with the particles
sitting about 50 px from where they are supposed to be.

Measured, as mean distance from each particle to its target after 800 steps of
attraction, starting from a fully diverged state:

| chaos pull kept while the clock shows | mean error |
| --- | ---: |
| 100% (original) | 52.30 px |
| 50% | 28.62 px |
| 25% | 14.97 px |
| **10%** | **6.16 px** |
| 0% | 0.05 px |

Ten percent is the number in the code (`LORENZ_WHEN_SHOWING`). Zero gives a
clock made of stone and throws away the shimmer, which is the nicest thing about
it.

This regression shipped once. A frame count alone would not have caught it; CI
now measures the distance from each particle to its target after 2,000 free steps
and 800 attracting steps, and fails if the mean exceeds 15 px.

## Recording

Headless frames render as fast as the CPU allows, so a wall-clock switch interval
would give a different number of frames per phase on every machine; recording
switches on a step count instead (`--switch-at`, or every `interval × fps`
steps). The particles need several hundred steps to settle into the digits, so
the recorder keeps every Nth frame (`--every`) and starts after a warm-up
(`--warmup`) so the GIF opens on the attractor rather than on a single dot.
