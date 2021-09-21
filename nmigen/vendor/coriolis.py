from abc import abstractproperty
from os import path
from ..hdl import *
from ..build import *

__all__ = ["CoriolisPlatform"]

class CoriolisPlatform(TemplatedPlatform):
    """
    Coriolis toolchain
    -----------------

    Required tools:
        * ``Coriolis``
        * ``PDKMaster`` with ``FreePDK45``

    The environment is populated by running the script specified in the environment variable
    ``NMIGEN_ENV_Coriolis``, if present.

    Available overrides:
        * ``verbose``: enables logging of informational messages to standard error.
        * ``read_verilog_opts``: adds options for ``read_verilog`` Yosys command.
        * ``script_after_read``: inserts commands after ``read_ilang`` in Yosys script.
        * ``script_after_coarse_synth``: inserts commands after ``synth`` in Yosys script.
        * ``script_after_synth``: inserts commands after all synthesis and mapping in Yosys script.
        * ``yosys_opts``: adds extra options for ``yosys``.

    Build products:
        * ``{{name}}.rpt``: Yosys log.
        * ``{{name}}.blif``: synthesized RTL.
        * ``{{name}}.gds``: output GDS-II.
    """
    top_dir = abstractproperty() # PDKMaster/FreePDK install dir
    nda_dir = abstractproperty() # NDA path relative to top_dirs
    liberty_file = abstractproperty() # path to liberty file relative to top_dir
    tech_name = abstractproperty() # tuple of (import path, name) for Python technology

    def __init__(self):
        super().__init__()

    def liberty_path(self):
        return path.join(self.top_dir, self.liberty_file)
    def nda_path(self):
        return path.join(self.top_dir, self.nda_dir)
    def tech_module(self):
        return self.tech_name[0]
    def tech_class(self):
        return self.tech_name[1]

    toolchain = "Coriolis"
    required_tools = [
        "yosys",
        "python2",
    ]

    file_templates = {
        **TemplatedPlatform.build_script_templates,
        "{{name}}.il": r"""
            # {{autogenerated}}
            {{emit_rtlil()}}
        """,
        "{{name}}.debug.v": r"""
            /* {{autogenerated}} */
            {{emit_debug_verilog()}}
        """,
        "{{name}}.ys": r"""
            # {{autogenerated}}
            read_liberty -lib -ignore_miss_dir -setattr blackbox {{platform.liberty_path()}}
            {% for file in platform.iter_files(".v") -%}
                read_verilog {{get_override("read_verilog_opts")|options}} {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".sv") -%}
                read_verilog -sv {{get_override("read_verilog_opts")|options}} {{file}}
            {% endfor %}
            {% for file in platform.iter_files(".il") -%}
                read_ilang {{file}}
            {% endfor %}
            read_ilang {{name}}.il
            delete w:$verilog_initial_trigger
            {{get_override("script_after_read")|default("# (script_after_read placeholder)")}}
            synth -flatten -top {{name}}
            {{get_override("script_after_coarse_synth")|default("# (script_after_coarse_synth placeholder)")}}
            dfflibmap -liberty {{platform.liberty_path()}}
            opt
            abc -liberty {{platform.liberty_path()}} -script +strash;scorr;ifraig;retime,{D};strash;dch,-f;map,-M,1,{D}
            setundef -zero
            clean -purge
            {{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
            write_blif {{name}}.blif
            write_verilog {{name}}.synth.v
            stat
        """,
        "{{name}}_pnr.py": r"""
            import os
            import CRL, Hurricane as Hur, Katana, Etesian, Anabatic, Cfg
            from helpers import u, l, setNdaTopDir
            from helpers.overlay import CfgCache

            ndadir = "{{platform.nda_path()}}"
            setNdaTopDir(ndadir)

            from {{platform.tech_module()}} import {{platform.tech_class()}} as tech

            tech.setup()
            tech.FlexLib_setup()

            print("Coriolis tech initialized")

            from plugins.cts.clocktree import HTree, computeAbutmentBox
            from plugins.chip.configuration import ChipConf

            af = CRL.AllianceFramework.get()
            env = af.getEnvironment()
            print(env.getPrint())

            with CfgCache(priority=Cfg.Parameter.Priority.ConfigurationFile) as cfg:
                cfg.anabatic.topRoutingLayer = 'metal6'

            env.setCLOCK('clk')

            # P&R
            cell_name = "{{name}}"

            # Core block
            cell = CRL.Blif.load(cell_name)
            cell.setName(cell_name + "_pnr")
            af.saveCell(cell, CRL.Catalog.State.Logical)


            # # Place-and-route
            chipconf = ChipConf( {}, cell, None )

            cellGauge = af.getCellGauge()
            spaceMargin = Cfg.getParamPercentage('etesian.spaceMargin').asPercentage()/100.0
            aspectRatio = Cfg.getParamPercentage('etesian.aspectRatio').asPercentage()/100.0
            bb = computeAbutmentBox(cell, spaceMargin, aspectRatio, cellGauge)

            et = Etesian.EtesianEngine.create(cell)
            ht = HTree.create(chipconf, cell, None, bb)
            et.place()
            ht.connectLeaf()
            ht.route()
            et.destroy()

            kat = Katana.KatanaEngine.create(cell)
            kat.digitalInit()
            kat.runGlobalRouter(Katana.Flags.NoFlags)
            kat.loadGlobalRouting(Anabatic.EngineLoadGrByNet)
            kat.layerAssign(Anabatic.EngineNoNetLayerAssign)
            kat.runNegociate(Katana.Flags.NoFlags)
            route_success = kat.isDetailedRoutingSuccess()
            kat.finalizeLayout()
            kat.destroy()

            af.saveCell(cell, CRL.Catalog.State.Logical|CRL.Catalog.State.Physical)
            CRL.Gds.save(cell)

            assert route_success
        """
    }
    command_templates = [
        r"""
        {{invoke_tool("yosys")}}
            {{quiet("-q")}}
            {{get_override("yosys_opts")|options}}
            -l {{name}}.rpt
            {{name}}.ys
        """,
        r"""
        {{invoke_tool("python2")}}
            {{name}}_pnr.py
        """,
    ]
