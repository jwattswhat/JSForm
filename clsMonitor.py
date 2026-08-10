from screeninfo import get_monitors


def monitor_metrics(monitor, fallback_dpi=96):
    """Return usable metrics even when Windows omits physical dimensions."""
    width_mm = monitor.width_mm or 0
    height_mm = monitor.height_mm or 0
    width_in = width_mm * 0.039 if width_mm else monitor.width / fallback_dpi
    height_in = height_mm * 0.039 if height_mm else monitor.height / fallback_dpi
    return {
        "name": monitor.name,
        "primary": monitor.is_primary,
        "width": monitor.width,
        "height": monitor.height,
        "width_in": width_in,
        "height_in": height_in,
        "pixelsperinch": [int(monitor.width / width_in), int(monitor.height / height_in)],
    }


class clsMonitor:
    """
    clsMonitor - Manages data for the display.
    """
    fontsize = 1
    monitor = {}

    def __init__(self):
        monitors = list(get_monitors())
        primary = next((m for m in monitors if m.is_primary), monitors[0] if monitors else None)
        if primary is not None:
                self.monitor["primary"] = monitor_metrics(primary)
                pointsperinch = 0.013
                fontinches = self.fontsize * pointsperinch
                pixelinchesx = self.monitor["primary"]["pixelsperinch"][0]
                pixelinchesy = self.monitor["primary"]["pixelsperinch"][1]
                fontsizepixelsx = pixelinchesx * fontinches * self.fontsize
                fontsizepixelsy = pixelinchesy * fontinches * self.fontsize
                self.monitor["primary"]["fontsizepixelsx"] = fontsizepixelsx
                self.monitor["primary"]["fontsizepixelsy"] = fontsizepixelsy

    #        pprint.pprint(self.monitor)

    def getfontpixelsx(self, fontsize):
        return self.monitor["primary"]["fontsizepixelsx"] * fontsize

    def getfontpixelsy(self, fontsize):
        return self.monitor["primary"]["fontsizepixelsy"] * fontsize


PMON = clsMonitor()
