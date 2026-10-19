from __future__ import annotations

from game import App

# Renders the interface at its base resolution and scales it up to the window.
# Raise this for a bigger window/UI on high-DPI displays; 1.0 keeps it native size.
UI_SCALE = 2.0


def main() -> None:
    App(ui_scale=UI_SCALE).run()


if __name__ == "__main__":
    main()
