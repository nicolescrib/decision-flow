from __future__ import annotations

import pygame

from renderer import CompactListRenderer, SimpleNumberRenderer, ParticleRenderer
from simulator import Simulator
from ui import UI

# Renders the interface at its base resolution and scales it up to the window.
# Raise this for a bigger window/UI on high-DPI displays; 1.0 keeps it native size.
UI_SCALE = 2.0


def main() -> None:
    pygame.init()
    simulator = Simulator()
    simulator.create_default_graph()

    renderers = [ParticleRenderer(scale=1.0), SimpleNumberRenderer(), CompactListRenderer()]
    ui = UI(simulator, renderers, ui_scale=UI_SCALE)
    ui.run()


if __name__ == "__main__":
    main()
