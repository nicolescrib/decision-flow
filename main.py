from __future__ import annotations

import pygame

from renderer import CompactListRenderer, SimpleNumberRenderer, ParticleRenderer
from simulator import Simulator
from ui import UI


def main() -> None:
    pygame.init()
    simulator = Simulator()
    simulator.create_default_graph()

    renderers = [SimpleNumberRenderer(), CompactListRenderer(), ParticleRenderer(scale=1.0)]
    ui = UI(simulator, renderers)
    ui.run()


if __name__ == "__main__":
    main()
