# Decision Flow — Zen Pressure Sandbox

## Overview
Decision Flow is a small Python toy program that simulates decision-making through the lens of pressure gradients. The first version will be a minimalist, interactive desktop sandbox where nodes accumulate or emit discrete units based on simple pressure differences.

The goal is to create a calm, puzzle-like experience with a modular architecture and clean separation between simulation, rendering, and UI.

## Concept
- The simulation is built around a set of nodes arranged in a simple layout.
- Each node holds a numeric quantity of "units." This quantity represents local pressure.
- Nodes can gain units, lose units, or transfer units depending on the pressure gradient between connected neighbors.
- The system evolves over time in discrete ticks.
- The player can interact with the sandbox by adjusting node values or changing simple rules.

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
- Represents nodes, edges, and node values.
- Maintains the current state of the system.
- Updates the state on each tick based on pressure gradients.
- Exposes a stable state snapshot to the renderer and UI.

### Renderer
- Converts simulation state into a simple visual representation.
- Uses a lightweight rendering layer such as `pygame`.
- Draws nodes, connections, and pressure indicators.
- Keeps rendering logic separate from simulation logic.

### UI
- Handles user input and window events.
- Allows stepping the simulation, resetting state, and optionally modifying node values.
- Drives the main loop and orchestrates simulation ticks and rendering.

### UI look and feel
- Use a crisp low-resolution grid aesthetic reminiscent of 90s/early-2000s pixel games.
- Render nodes as simple filled squares or circles with a chunky outline.
- Draw edges as single-pixel or 2px lines connecting nodes.
- Use a limited palette with subtle gradients: a dark background, cool tones for normal nodes, warm highlights for high pressure, and muted accents for sources/sinks.
- Show node pressure values as small pixel-style text or a color intensity bar.
- Use simple UI chrome: a small top or side panel with state labels, controls, and status text.
- Keep animations smooth but restrained: flow pulses and pressure changes should feel calm and deliberate.

### Main
- Wires the simulator, renderer, and UI together.
- Initializes the app and runs the main loop.

## User interaction
In the first iteration, the user should be able to:
- Start the sandbox and watch nodes exchange units.
- Observe the pressure gradient as nodes fill or empty.
- Reset the simulation.
- Optionally toggle a simple state, such as switching one node from source to sink.

## Simulation plan
- Use a small graph of nodes connected by edges.
- Each node stores a current `units` value that represents local pressure.
- Nodes may be ordinary nodes, a source node that emits units, or a sink node that absorbs units.
- On each tick, compute transfer proposals from higher-pressure nodes toward lower-pressure neighbors.
- Use a simple pressure-gradient rule:
  - for each edge, `transfer = clamp((high_pressure - low_pressure) * rate, 0, max_transfer)`
  - apply all transfers simultaneously to maintain stable, order-independent updates.
- Keep node state simple and deterministic, with a fixed update rate and optional damping so the system relaxes smoothly.
- Expose the computed node values and transfer directions to the renderer for visualization.

## Implementation plan
1. Create the initial file structure and modules.
2. Implement the simulator with:
   - `Node` and `Edge` objects
   - a `Simulator` class that holds state and computes tick updates
   - pressure-gradient transfer logic and source/sink behavior
3. Add a renderer that displays nodes, connections, and numeric or color-coded pressure.
4. Add a simple UI loop with `pygame` and basic controls for reset, pause, and node toggling.
5. Iterate on rules and visuals once the core structure is working.

## Requirements
- Python 3.10+ (or similar modern Python)
- `pygame` for rendering and input

## Future extensions
- Add puzzles with target pressure patterns.
- Support node types such as sources, sinks, and valves.
- Add more sophisticated gradients and diffusion behavior.
- Allow multiple layouts and interactive editing.
