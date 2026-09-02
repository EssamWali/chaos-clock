"""Twenty thousand particles chasing a Lorenz attractor, which every so often
stop chasing it and arrange themselves into the current time.

    python chaos_clock.py                    # open a window
    python chaos_clock.py --benchmark        # compare the two renderers
    python chaos_clock.py --record out.gif   # headless, writes a GIF

Each particle carries its own Lorenz state, seeded a hair apart from every other.
That is the point of the piece: identical equations from near-identical starting
points, pulling visibly apart within seconds. The clock is what happens when a
second force is switched on and chaos loses.
"""

import argparse
import os
import time
from datetime import datetime, timedelta

import numpy as np

# Lorenz
SIGMA, RHO, BETA = 10.0, 28.0, 8.0 / 3.0
DT = 0.01

# Blending
LORENZ_STRENGTH = 0.001
TIME_STRENGTH = 0.004

# How much of the chaos pull survives while the clock is on screen.
#
# At full strength the clock never actually forms once the simulation has been
# running for a while. Early on every particle's Lorenz state is still near the
# origin, so the chaos force is small and points the same way for all of them,
# and the text wins easily. Once the states have diverged - which is the entire
# point of the piece - each particle is dragged toward a different part of the
# attractor and the digits settle into a smear about 50 px wide. Keeping a tenth
# of the pull brings the mean distance to target from 52 px down to 6 px, which
# reads as a clock that shimmers. Setting it to zero gives 0.05 px, a clock made
# of stone, and throws away the nicest thing about it.
LORENZ_WHEN_SHOWING = 0.1
DAMPING = 0.98
JITTER_WHEN_UNDERSAMPLED = 1.5

# Text
FONT_PATH = "Orbitron-Regular.ttf"
FONT_PIXEL_SIZE = 160
TARGET_SCALE = 0.9
ALPHA_THRESHOLD = 20
TIME_FORMAT = "%H:%M"

BACKGROUND = (8, 8, 10)

# A 3x3 block per particle. The original drew a radius-2 circle, which is about
# thirteen pixels; nine reads a little crisper and costs a third as much.
KERNEL = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


class ChaosClock:
    """The simulation. Knows nothing about how it is drawn."""

    def __init__(self, particles, width, height, seed=None):
        rng = np.random.default_rng(seed)
        self.n = particles
        self.width = width
        self.height = height

        self.positions = np.empty((particles, 2), dtype=np.float32)
        self.positions[:, 0] = rng.uniform(0, width, particles)
        self.positions[:, 1] = rng.uniform(0, height, particles)
        self.velocities = rng.uniform(-1, 1, (particles, 2)).astype(np.float32)
        self.colours = rng.integers(40, 256, (particles, 3)).astype(np.uint8)

        # Every particle starts from (0.1, 0, 0) plus a nudge of order 1e-2. That
        # nudge is the whole illusion: the trajectories are indistinguishable for
        # the first second or so and completely unrelated a few seconds later.
        noise = rng.normal(scale=1e-2, size=(particles, 3)).astype(np.float32)
        self.lorenz = np.array([0.1, 0.0, 0.0], dtype=np.float32) + noise

        self.targets = np.zeros((0, 2), dtype=np.float32)
        self.showing_time = False

    def step(self):
        x, y, z = self.lorenz[:, 0], self.lorenz[:, 1], self.lorenz[:, 2]
        self.lorenz[:, 0] += (SIGMA * (y - x)) * DT
        self.lorenz[:, 1] += (x * (RHO - z) - y) * DT
        self.lorenz[:, 2] += (x * y - BETA * z) * DT

        attractor = np.stack(
            [
                np.interp(self.lorenz[:, 0], [-30, 30], [0, self.width]),
                np.interp(self.lorenz[:, 1], [-30, 30], [self.height, 0]),
            ],
            axis=1,
        ).astype(np.float32)

        self.velocities *= DAMPING
        pull = LORENZ_STRENGTH * (LORENZ_WHEN_SHOWING if self.showing_time else 1.0)
        self.velocities += (attractor - self.positions) * pull
        if self.showing_time and self.targets.shape[0] == self.n:
            self.velocities += (self.targets - self.positions) * TIME_STRENGTH
        self.positions += self.velocities

        self._bounce()

    def _bounce(self):
        for axis, limit in ((0, self.width), (1, self.height)):
            low = self.positions[:, axis] < 0
            self.positions[low, axis] = 0
            self.velocities[low, axis] *= -1
            high = self.positions[:, axis] >= limit
            self.positions[high, axis] = limit - 1
            self.velocities[high, axis] *= -1


def time_targets(text, font, width, height, count):
    """Rasterise the time, then sample the lit pixels as destinations."""
    import pygame

    surface, _ = font.render(text, fgcolor=(255, 255, 255), bgcolor=None)
    surface_width, surface_height = surface.get_size()
    alpha = pygame.surfarray.array_alpha(surface)
    if alpha.shape == (surface_width, surface_height):
        alpha = alpha.T

    ys, xs = np.nonzero(alpha > ALPHA_THRESHOLD)
    if len(xs) == 0:
        return np.zeros((0, 2), dtype=np.float32)

    coords = np.column_stack((xs, ys)).astype(np.float32)
    low = coords.min(axis=0)
    high = coords.max(axis=0)
    mask_width = high[0] - low[0] + 1.0
    scale = (width * TARGET_SCALE) / mask_width
    centre = np.array([low[0] + mask_width / 2.0, low[1] + (high[1] - low[1]) / 2.0])
    coords = (coords - centre) * scale + np.array([width / 2.0, height / 2.0])

    rng = np.random.default_rng()
    available = coords.shape[0]
    if available >= count:
        return coords[rng.choice(available, size=count, replace=False)].astype(np.float32)

    # Fewer lit pixels than particles: reuse them and scatter, so the digits read
    # as a cloud rather than as a stack of particles on identical coordinates.
    sampled = coords[rng.choice(available, size=count, replace=True)]
    jitter = rng.normal(scale=JITTER_WHEN_UNDERSAMPLED, size=sampled.shape)
    return (sampled + jitter).astype(np.float32)


def render_circles(surface, sim):
    """The original renderer: one draw call per particle, every frame."""
    import pygame

    surface.fill(BACKGROUND)
    for i in range(sim.n):
        pygame.draw.circle(
            surface,
            tuple(sim.colours[i]),
            (int(sim.positions[i, 0]), int(sim.positions[i, 1])),
            2,
        )


def render_scatter(surface, sim, frame, trails=0.0):
    """Scatter every particle into a pixel array in one pass, then blit once.

    Twenty thousand draw calls a frame is 1.2 million a second at 60 fps, and
    almost all of that is call overhead rather than pixels. Writing the array
    directly moves the loop into numpy and leaves pygame with a single blit.
    """
    import pygame

    if trails:
        frame *= trails
    else:
        frame[:] = BACKGROUND

    xs = sim.positions[:, 0].astype(np.int32)
    ys = sim.positions[:, 1].astype(np.int32)

    for dx, dy in KERNEL:
        px = np.clip(xs + dx, 0, sim.width - 1)
        py = np.clip(ys + dy, 0, sim.height - 1)
        frame[px, py] = sim.colours

    pygame.surfarray.blit_array(surface, frame)


def make_font():
    import pygame.freetype

    try:
        return pygame.freetype.Font(FONT_PATH, FONT_PIXEL_SIZE)
    except (OSError, FileNotFoundError):
        print(f"{FONT_PATH} not found, falling back to a system font")
        return pygame.freetype.SysFont(None, FONT_PIXEL_SIZE)


def new_frame(width, height):
    frame = np.empty((width, height, 3), dtype=np.uint8)
    frame[:] = BACKGROUND
    return frame


def benchmark(args):
    """Time the two renderers over the same simulation, physics measured apart."""
    import pygame

    pygame.init()
    surface = pygame.Surface((args.width, args.height))
    sim = ChaosClock(args.particles, args.width, args.height, seed=0)
    frame = new_frame(args.width, args.height)

    for _ in range(20):  # warm up numpy and the allocator
        sim.step()

    def timed(fn, frames):
        start = time.perf_counter()
        for _ in range(frames):
            fn()
        return (time.perf_counter() - start) / frames

    physics = timed(sim.step, args.frames)
    circles = timed(lambda: render_circles(surface, sim), args.frames)
    scatter = timed(lambda: render_scatter(surface, sim, frame), args.frames)

    print(f"\n{args.particles:,} particles, {args.width}x{args.height}, "
          f"{args.frames} frames each\n")
    print(f"  physics only          {physics * 1000:7.2f} ms/frame")
    print(f"  render: draw.circle   {circles * 1000:7.2f} ms/frame   "
          f"{1 / (physics + circles):6.1f} fps")
    print(f"  render: numpy scatter {scatter * 1000:7.2f} ms/frame   "
          f"{1 / (physics + scatter):6.1f} fps")
    print(f"\n  speedup: {circles / scatter:.1f}x on the render, "
          f"{(physics + circles) / (physics + scatter):.1f}x end to end")
    pygame.quit()


def run(args):
    if args.record:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    import pygame
    import pygame.freetype

    pygame.init()
    pygame.freetype.init()

    if args.record:
        surface = pygame.Surface((args.width, args.height))
    else:
        surface = pygame.display.set_mode((args.width, args.height))
        pygame.display.set_caption("Chaos Clock")

    clock = pygame.time.Clock()
    font = make_font()
    sim = ChaosClock(args.particles, args.width, args.height)
    frame = new_frame(args.width, args.height)

    # The particles all start from the same Lorenz seed plus a nudge of order
    # 1e-2. Divergence is exponential but it still takes a few hundred steps to
    # become visible, so a recording that begins at step zero opens on a single
    # dot. Warming up first means the GIF starts on the attractor.
    for _ in range(args.warmup):
        sim.step()

    minute = datetime.now().minute
    sim.targets = time_targets(
        datetime.now().strftime(TIME_FORMAT), font, args.width, args.height, args.particles
    )
    next_switch = datetime.now() + timedelta(seconds=args.interval)

    frames = []
    # When recording there is no real-time clock to switch against - headless
    # frames render as fast as the CPU allows, so a wall-clock interval would
    # give a different number of frames per phase on every machine.
    switch_every = max(1, int(args.interval * args.fps))
    step_count = 0
    running = True
    while running:
        if not args.record:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

        now = datetime.now()
        if now.minute != minute:
            minute = now.minute
            sim.targets = time_targets(
                now.strftime(TIME_FORMAT), font, args.width, args.height, args.particles
            )
        if args.record:
            # A recording wants one transition, landing on the assembled clock.
            # Alternating on a fixed period puts the end of the file wherever the
            # arithmetic happens to leave it, which is usually mid-dissolve.
            if args.switch_at is not None:
                sim.showing_time = step_count >= args.switch_at
            elif step_count and step_count % switch_every == 0:
                sim.showing_time = not sim.showing_time
        elif now >= next_switch:
            sim.showing_time = not sim.showing_time
            next_switch = now + timedelta(seconds=args.interval)

        sim.step()
        step_count += 1

        if args.renderer == "circles":
            render_circles(surface, sim)
        else:
            render_scatter(surface, sim, frame, trails=args.trails)

        if args.record:
            # The particles need several hundred steps to settle into the digits,
            # so a GIF that showed every step would be enormous and mostly still.
            # Keeping every Nth frame covers the whole convergence in a file a
            # README will actually load.
            if step_count % args.every == 0:
                frames.append(
                    np.transpose(pygame.surfarray.array3d(surface), (1, 0, 2)).copy()
                )
            if len(frames) >= args.frames:
                running = False
        else:
            pygame.display.flip()
            clock.tick(args.fps)

    if args.record:
        from pathlib import Path

        from PIL import Image

        Path(args.record).parent.mkdir(parents=True, exist_ok=True)

        images = [Image.fromarray(f) for f in frames]
        if args.scale != 1.0:
            size = (int(args.width * args.scale), int(args.height * args.scale))
            images = [im.resize(size, Image.LANCZOS) for im in images]
        images = [im.quantize(colors=args.colours) for im in images]
        images[0].save(
            args.record,
            save_all=True,
            append_images=images[1:],
            duration=int(1000 / args.fps),
            loop=0,
            optimize=True,
        )
        print(f"wrote {args.record}  ({len(images)} frames)")

    pygame.quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--particles", type=int, default=20000)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--interval", type=float, default=15.0,
                        help="seconds between chaos and clock")
    parser.add_argument("--renderer", choices=("scatter", "circles"), default="scatter")
    parser.add_argument("--trails", type=float, default=0.0, metavar="DECAY",
                        help="0 clears each frame; 0.85 leaves fading trails")
    parser.add_argument("--record", metavar="PATH", help="write a GIF, no window")
    parser.add_argument("--switch-at", type=int, default=None, metavar="STEP",
                        help="recording only: turn the clock on once, at this step")
    parser.add_argument("--warmup", type=int, default=0,
                        help="steps to run before the first frame is kept")
    parser.add_argument("--every", type=int, default=1,
                        help="keep every Nth simulated frame when recording")
    parser.add_argument("--colours", type=int, default=128,
                        help="GIF palette size")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="downscale factor for the recorded GIF")
    parser.add_argument("--frames", type=int, default=240,
                        help="frames to record, or to time per renderer")
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()

    benchmark(args) if args.benchmark else run(args)


if __name__ == "__main__":
    main()
