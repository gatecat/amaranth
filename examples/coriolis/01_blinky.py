from nmigen import *
from nmigen.vendor.coriolis import *
from nmigen.build import *

import os

class FreePDK45Platform(CoriolisPlatform):
    top_dir = os.environ["TOP_DIR"]
    nda_dir = "coriolis/techno"
    liberty_file = "views/FreePDK45/FlexLib/liberty/FlexLib_nom.lib"
    tech_name = ("NDA.node45", "freepdk45_c4m")
    connectors  = []
    # TODO: define a pad ring
    resources   = [
        Resource("clk", 0, Pins("0", dir="i"), Clock(25e6)),
        Resource("arstn", 0, PinsN("1", dir="i")),
        Resource("led", 0, PinsN("2 3 4 5", dir="o")),
    ]
    # TODO: define IO buffer types?
    def get_input(self, pin, port, attrs, invert):
        m = Module()
        m.d.comb += pin.eq(self._invert_if(invert, port))
        return m

    def get_output(self, pin, port, attrs, invert):
        m = Module()
        m.d.comb += port.eq(self._invert_if(invert, pin))
        return m

class Blinky(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        timer  = Signal(24)
        clk = platform.request("clk")
        arst = platform.request("arstn")
        led = platform.request("led")

        m.domains.sync = ClockDomain(async_reset=True)
        m.d.comb += ClockSignal().eq(clk.i)
        m.d.comb += ResetSignal().eq(arst.i)
        m.d.sync += timer.eq(timer + 1)
        m.d.comb += led.o.eq(timer[-4:])
        return m

if __name__ == "__main__":
    # Example usage:
    # TOP_DIR=$HOME/freepdk/c4m_pdk_freepdk45-0.0.1 NMIGEN_ENV_Coriolis=$HOME/nmigen/examples/coriolis/coriolis_env.sh \
    #  python3 $HOME/nmigen/examples/coriolis/01_blinky.py
    platform = FreePDK45Platform()

    blinky = Blinky()
    platform.build(blinky)
