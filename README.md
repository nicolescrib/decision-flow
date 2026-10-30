# Decision Flow

## Overview
Decision Flow is a small, calm physics puzzle game in Python and pygame. A source releases a limited stream of particles that drift through a pressure field. Your job is to steer that flow into every ring on the board, using a handful of pins, without letting it fall into voids.

The look is a crisp late-90s pixel toy: a dark board, glowing particle trails, chunky outlines and synthesized blips. The original free-form pressure **sandbox** is still there as a separate mode.

## How to play
- Each level has one or more **sources** (warm circles, showing how many units are left) and one or more **rings** to fill (showing `filled/target`).
- Press **Space** to open the sources. Each particle comes out along the pull of the field and keeps its momentum as it travels.
- Rings pull the flow towards them and absorb it until they are full, then go quiet.
- **Voids** (purple swirls, some orbiting) destroy any particle that touches them. Those units are gone for good.
- The supply is finite. If too little flow is left to fill every ring, the level is lost ("Out of flow").
- Before releasing, a dotted line previews where the stream will go. Use it to plan where your pins go.

### Pins
Each level gives you a few pins in the tray at the bottom. Drag one onto the board to place it.
- **Pull pins** (blue) attract every particle. A pull pin gathers the stream into a swarm, and you can **carry the swarm by dragging the pin**: around walls, past voids, and onto a ring to deliver it.
- **Push pins** (orange) repel particles. Use them as banks and shields to bend the stream without catching it.
- Scroll the mouse wheel (or press `[` / `]`) over a pin to change its strength (1 to 3). Right-click a pin to return it to the tray.
- Pins can be moved at any time, including while the flow is running. Your layout is kept when you restart.

### Colours
In later levels the flow comes in two colours. A coloured ring only pulls on, and only accepts, particles of its own colour. Pins move every colour, so a carried swarm can be sorted ring by ring.

### Stars
Clear a level to earn stars based on how many particles you lost. The thresholds are shown at the top right, and the stars there dim live as you lose particles. Clearing a level unlocks the next. Best results are saved to `~/.decision_flow_progress.json`.

## Controls
| Where | Input | Action |
|---|---|---|
| Level select | Click / arrows + Enter | Play a level |
| | `S` | Open the sandbox |
| | `M` | Mute / unmute |
| | `Esc` | Quit |
| Puzzle | Drag from tray | Place a pin |
| | Drag a pin | Move it (live, while flowing) |
| | Right-click a pin | Remove it |
| | Wheel or `[` / `]` over a pin | Pin strength |
| | `Space` | Release the flow / pause |
| | `R` | Restart (pins stay) |
| | `C` | Clear all pins |
| | Hold `F` | Fast-forward ×3 |
| | `Enter` | Next level (after a win) |
| | `M` | Mute / unmute |
| | `Esc` | Back to level select |

### Sandbox controls
- **Space** run / pause, **Tab** cycle renderers, **Esc** back to the title.
- **Click a node** to select it. **Up / Down** change its units by 1, **+ / −** by 5 (or zoom the particle view when nothing is selected).
- **( / )** change the selected node's pressure by 0.5. **[ / ]** do the same, or change the global **pressure gain** when no node is selected.
- **i** inverts the whole pressure field. **n / k** add / remove a random node.
- The **Settings** menu lists every editable setting (renderer, gain, inversion, particle scale).

## Running
```
pip install -r requirements.txt
python main.py
```
Run the tests with `python -m unittest discover -s tests -t .`. They include a scripted three-star solution for every level, so a physics or level change that makes a level impossible fails the suite.

## Architecture
- `simulator.py`: the physics. Nodes have a role: `node` (the original sandbox node, which emits, absorbs, pulls and trades units depending on pressure), `source` (only emits) or `goal` (only absorbs, and goes quiet when full). On top of nodes there are pins (field-only pushes and pulls), walls (axis-aligned rectangles that particles bounce off) and voids (destroy particles, optionally orbiting). Particles are numpy arrays of positions, velocities and colours, so forces, wall bounces and absorption are vectorized. Each force is `(particle - source) * pressure / distance²`. Units are conserved: `nodes + particles + lost` stays constant. `predict_path` powers the preview line.
- `levels.py`: level data (sources, rings, walls, voids, pin allowance, star thresholds) and the puzzle physics settings: less drag than the sandbox, a speed cap so particles can't tunnel through walls, and a short-range particle repulsion so a gathered cloud reads as a swarm.
- `puzzle.py`: the rules for one level. Pin placement and inventory, the design → running → won/failed states, failure detection (per colour) and star rating.
- `puzzle_view.py`: drawing for a puzzle. Board, trails, rings, voids, pins, preview, HUD, tray and result panels.
- `game.py`: the `App` (window, scaling, main loop) and its screens. The title/level select (with a live simulation in the background) and the puzzle screen. Puzzle physics ticks at 30 per second; the screen draws at 60 fps.
- `audio.py`: sounds synthesized with numpy at start-up, including pentatonic plinks for absorption, a sweep for lost particles and chords for filled rings and wins. Silent if there is no audio device.
- `progress.py`: saved best stars and the mute setting.
- `ui.py` and `renderer.py`: the sandbox screen and its three renderers (particle, number tiles, list).
- `main.py`: entry point. `UI_SCALE` sets the window scale.

## Ideas for later
- A level editor, and saving/loading custom levels.
- Moving walls, gates that open when a ring fills, and sources that pulse.
- Time-based par scores alongside the loss-based stars.
- Particle-to-particle interactions beyond the swarm repulsion.
