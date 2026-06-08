# Decision Flow — Zen Pressure Sandbox

## Overview
Decision Flow is a small Python toy program that simulates decision-making through the lens of pressure gradients. The first version will be a minimalist, interactive desktop sandbox where nodes accumulate or emit discrete units based on simple pressure differences.

The goal is to create a calm, puzzle-like experience with a modular architecture and clean separation between simulation, rendering, and UI.

## Concept
- The simulation is built around a set of nodes placed in a 2D space.
- Each node holds a numeric quantity of "units" — a finite, conserved resource that only ever moves between being stored in a node and traveling as a free particle.
- Each node also has its own signed "pressure" value, independent of its unit count. Positive pressure makes a node emit particles (converting its own units into them); negative pressure makes a node attract and absorb nearby particles (converting them back into units).
- Particles drift freely through the space under the combined pull/push of every node's pressure field — their position relative to nodes is fully simulated, not fixed to predefined connections.
- The system evolves over time in discrete ticks.
- The player can interact with the sandbox by selecting nodes and adjusting their units or pressure.
- Beyond per-node pressure, a global **pressure field** modifier acts on every node at once: a multiplicative **gain** scales all pressures together (preserving their relative balance), and an **invert** toggle flips the whole field so emitters become absorbers and vice versa. Both are applied on top of each node's authored pressure, leaving the per-node values unchanged.

## Design goals
- Keep the first version small and understandable.
- Separate concerns clearly:
  - `simulator.py`: core model and update rules
  - `renderer.py`: drawing state to the screen
  - `ui.py`: window, input, and loop management
  - `main.py`: program bootstrap
- Use object-oriented style where it adds clarity without harming simplicity.
- Keep the visuals simple and pleasing, like a pixel-based late-90s/early-2000s toy applet.

## Planned architecture

### Simulator
- Represents nodes (each with a position, a unit count, and a pressure value) and free-roaming particles.
- Maintains the current state of the system, including the conserved total unit count.
- Each tick: applies pressure-field forces to move particles, absorbs particles into negative-pressure nodes, and emits particles from positive-pressure nodes.
- Exposes a stable state snapshot to the renderer and UI.
- Particles are stored as `numpy` arrays (positions and velocities as Nx2 float arrays) rather than a list of objects, so the per-tick force, movement, and absorption math is vectorized across all particles at once instead of looped in pure Python. This keeps the simulation responsive as the particle count grows into the thousands.

### Renderer
- Converts simulation state into a simple visual representation.
- Uses a lightweight rendering layer such as `pygame`.
- Draws nodes, drifting particles, and pressure-based color coding.
- Keeps rendering logic separate from simulation logic.

### UI
- Handles user input and window events.
- Allows stepping the simulation, resetting state, selecting a node, and adjusting that node's units and pressure.
- Drives the main loop and orchestrates simulation ticks and rendering.

### UI look and feel
- Use a crisp low-resolution grid aesthetic reminiscent of 90s/early-2000s pixel games.
- Render nodes as simple filled squares or circles with a chunky outline.
- Draw particles as small drifting dots whose motion traces the pressure field between nodes.
- Use a limited palette with subtle gradients: a dark background, cool tones for attracting (negative-pressure) nodes, warm tones for emitting (positive-pressure) nodes, and muted greens for neutral nodes.
- Show node pressure values as small pixel-style text or a color intensity bar.
- Use simple UI chrome: a small top or side panel with state labels, controls, and status text.
- Keep animations smooth but restrained: flow pulses and pressure changes should feel calm and deliberate.

### Main
- Wires the simulator, renderer, and UI together.
- Initializes the app and runs the main loop.

## User interaction
In the first iteration, the user should be able to:
- Start, stop, and step the sandbox and watch particles drift between nodes.
- Observe nodes fill or empty as they emit and absorb particles.
- Reset the simulation back to its initial unit values.
- Select a node and adjust its units and pressure live, to set up custom starting conditions or experiment with the field.
- Switch between alternative renderers (numeric, list, and spatial particle views).
- Raise or lower the global pressure gain to intensify or calm the entire field at once.
- Invert the whole pressure field, swapping every emitter and absorber.
- Open the **Settings** menu to view and edit every adjustable setting (active renderer, pressure gain, pressure inversion, particle scale) from one place, with controls that update live as new settings are added.

## Controls
- **Space** — run / pause the simulation.
- **Tab** — cycle through renderers.
- **Settings menu** — open it from the menu bar to adjust any editable setting with on-screen +/- and toggle controls.
- **Click a node** to select it.
- **Up / Down** — adjust the selected node's units by 1.
- **[ / ]** — adjust the selected node's pressure by 0.5.
- **( / )** — lower / raise the global **pressure gain**, which scales every node's pressure at once (range 0.0–3.0, default 1.0×).
- **i** — toggle **invert pressure** (emitters become absorbers and vice versa).
- **+ / −** — add / remove 5 units from the selected node, or zoom the particle view when no node is selected.
- **n / k** — add / remove a random node.
- **Esc** — quit.

## Simulation plan
- Place a small set of nodes at fixed positions in a 2D normalized space.
- Each node stores a `units` value (its share of the finite, conserved resource), a `capacity`, and a signed `pressure` value.
- Each particle is a free body with its own position and velocity.
- On each tick:
  - every particle feels a force from every node: `force = (particle_pos - node_pos) * node.pressure / distance^2`, so positive pressure pushes particles away and negative pressure pulls them in;
  - particles within range of a negative-pressure node are absorbed, converting back into one unit for that node (capacity permitting);
  - positive-pressure nodes accumulate an emission charge proportional to their pressure and convert their own units into newly emitted particles once the charge crosses a threshold.
- Because every conversion is symmetric (one unit becomes one particle and vice versa), `total_units = sum(node.units) + particle_count` stays exactly constant — the simulation has a finite, conserved pool of units.
- Expose node and particle state to the renderer for visualization.

## Implementation plan
1. Create the initial file structure and modules.
2. Implement the simulator with:
   - `Node` and `Particle` objects
   - a `Simulator` class that holds state and computes tick updates
   - pressure-field force calculation, particle absorption, and particle emission
3. Add a renderer that displays nodes, drifting particles, and pressure-based color/intensity coding.
4. Add a simple UI loop with `pygame` and controls for reset, pause/run, stepping, node selection, and adjusting a selected node's units and pressure.
5. Iterate on rules and visuals once the core structure is working.

## Requirements
- Python 3.10+ (or similar modern Python)
- `pygame` for rendering and input
- `numpy` for vectorized particle physics

## Future extensions
- Add puzzles with target pressure patterns or unit distributions.
- Let the user reposition nodes or add/remove them at runtime.
- Add more sophisticated field interactions, such as particle-to-particle forces or node-to-node pressure coupling.
- Allow saving and loading custom scenarios (positions, units, and pressures).
