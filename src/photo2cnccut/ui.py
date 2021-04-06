#!/usr/bin/env python

"""Handle user interface part."""

import argparse
import copy
import importlib
import math
import os
import sys
import time

CONFIG_FILENAME = 'p2cconfig.py'
CONFIG_DICTIONARY_NAME = 'config'

DATA_FILENAME = 'p2cmodule.py'
DATA_CLASS_NAME = 'Data'

# default configuration
_CONFIG = {

    # '_version': 1.0,

    # The script only generates the following g-codes:
    # N, X, Y, Z
    # G0 G1 M1

    # X, Y and Z are neutral to units.
    # So it should work both for mm and inch, if they are consistent.
    # But note that I am in a metric world, and only tested for mm.

    # Generic:

    # Output width and height (actual cut dimension without units).
    # The script tries width and then height, calculates the other,
    # keeping the aspect ratio.
    'width': 100,
    'height': 100,

    # feed rate (mm or inch per minute)
    # only used for time estimation
    'feed': 100,

    # round to this digit (e.g. 1.2345 to 1.234 when 3)
    'digit': 3,

    # add line number (one of 'all', 'retract' or 'none')
    # When 'retract', 'M1' is also appended to the line ('N280 G0 Z3. M1').
    # This is convenient for line method (stops at each line end retract),
    # but useless for point method.
    'line_number_type': 'retract',

    # line number increment
    'line_number_increment': 2,

    # The first movements are:
    # 1. G0 X0 Y0
    # 2. G0 Z<initial_z>
    # 3. G0 Z<retract_z>
    # 4. G0 X<first point> Y<first point>
    # 5. G1 Z<cut depth> ...
    # After that, non-cut-movements are always
    # G0 (retract) and G1 (plunge).
    #
    # The last movements are:
    # 1. G0 Z<retract_z>
    # 2. G0 Z<initial_z>

    'initial_z': 3,
    'retract_z': 1,

    'tool_angle': 45,

    # cut width when cut is deepest (grayscale 0)
    'maxwidth': 0.6,

    # Initialization and finalization g-codes
    # They are just copied in output,
    # before and after the g-codes the script generates.
    # (G0, G90, G21, G54, T, S, F, M3, M30 ...)
    'header': '',
    'footer': '',

    # The colors of svg path and background (cut and uncut parts).
    # Any css color should work.
    # https://developer.mozilla.org/en-US/docs/Web/CSS/color_value
    'svg_color': 'black',
    'svg_background': 'white',

    # scale svg size from g-code width and height.
    # 1.0 means 100px for width 100,
    # which is sometimes too small for web browsers.
    # it is conceptually 96 for inch, 96/25.4 (3.780) for mm,
    # but a bit bigger one looks better.
    'svg_scale': 5,

    # Scale png size, relative to svg size.
    'png_scale': 1,

    # 'line' or 'point'
    'method': 'line',

    # Whether line paths cut beyond the material border.
    # If True, retracts and plunges on each line start and end are omitted.
    # Normally, 'method' should be 'line'.
    'cut_through': False,

    # Line/Point Method Specific:

    # It starts around the top-left corner (X0, Y0),
    # and ends around the bottom-right, say, (X100, Y-100)

    # 0 <= line_angle < 90 (degree)
    'line_angle': 22.5,

    # x increment for the next point in a line (x resolution)
    'resolution': 0.3,

    # distance between lines, ratio to the maxwidth
    # (1.0 means no space between lines at the maxwidth)
    'stepover': 1.2,
}


class Conf(object):
    """Create uniform configuration object with dot access."""

    def __init__(self, config=None, args=None):
        self._config = copy.deepcopy(_CONFIG)
        self._args = args
        if config:
            self._config.update(config)
        for k, v in self._config.items():
            setattr(self, k, v)
        fname = getattr(args, 'fname', None)
        if fname:
            setattr(self, 'fname', fname)

        line_angle = self.line_angle * (math.pi / 180)
        self.sin = math.sin(line_angle)
        self.cos = math.cos(line_angle)
        self.tan = math.tan(line_angle)

        self._times = [time.time()]

    def _round(self, x):
        x = round(x, self.digit)
        if x == 0:
            return 0  # sometimes x is -0.0, which is inconvenient
        return x

    def _time(self, msg):
        if self._args._time:
            t = self._times
            t.append(time.time())
            print('%-6s %.3f' % (msg, (t[-1] - t[-2])))


_description = """
Create g-code and svg files from a picture file
('a.jpg' to 'a.jpg.nc' and 'a.jpg.svg')
""".lstrip('\n')


def _build_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=_description)

    h = 'file path to a picture'
    parser.add_argument('fname', nargs='?', help=h)

    h = 'show default configuration and descriptions'
    parser.add_argument('-H', '--Help', action='store_true', help=h)

    h = 'suppress normal printout (a few lines of info)'
    parser.add_argument('-q', '--quiet', action='store_true', help=h)

    h = "print current config (with user config updates, 'fname' required)"
    parser.add_argument('-c', '--print-config', action='store_true', help=h)

    h = 'print default config (without descriptions)'
    parser.add_argument('-C', '--print-Config', action='store_true', help=h)

    h = 'create only g-code (.nc) file from input file'
    parser.add_argument('-g', '--gcode', action='store_true', help=h)

    h = 'create only svg file from input file'
    parser.add_argument('-s', '--svg', action='store_true', help=h)

    h = ('create png file from svg file '
         "(<fname> + '.svg' to <fname> + '.png')")
    parser.add_argument('-p', '--png', action='store_true', help=h)

    h = 'print time passed (for development)'
    parser.add_argument('-_t', '--_time', action='store_true',
        help=argparse.SUPPRESS)

    args = parser.parse_args(args)
    return parser, args


def _get_python_object(directory, fname, objname):
    if os.path.isfile(os.path.join(directory, fname)):
        if directory not in sys.path:
            sys.path.insert(0, directory)
        try:
            mod = importlib.import_module(fname[:-3])
            return getattr(mod, objname, None)
        except (ImportError, AttributeError):
            pass


def _load_user_files(fname):
    directory = os.path.dirname(fname)

    config = _get_python_object(
        directory, CONFIG_FILENAME, CONFIG_DICTIONARY_NAME)
    data_class = _get_python_object(
        directory, DATA_FILENAME, DATA_CLASS_NAME)

    if directory in sys.path:
        sys.path.remove(directory)  # remove the first item
    return config, data_class


def _print_default_config(comment=False):
    title = '# default configuration:'
    start = '_CONFIG = {\n'
    end = '}\n'
    ret = []

    with open(__file__) as f:
        for line in f:
            if line == start:
                ret = []
                ret.append(title)
                ret.append('config = {')
                continue

            if line == end:
                ret.append(end.strip())
                break

            line = line.rstrip()
            if not comment:
                if not line or line.lstrip().startswith('#'):
                    continue
            ret.append(line)

    print('\n'.join(ret))


def main(args=None, data_class=None, conf=None):
    args_ = args or sys.argv[1:]
    parser, args = _build_args(args_)

    if len(args_) == 0:
        parser.print_help()
        return

    if args.Help or args.print_Config:
        _print_default_config(comment=args.Help)
        return

    if getattr(args, 'fname', None) is None:
        raise ValueError('No filename to process. Run -h or --help.')

    config, data_class_ = _load_user_files(args.fname)
    data_class = data_class or data_class_
    if data_class is None:
        import photo2cnccut.line
        data_class = photo2cnccut.line.Data

    if conf is None:
        conf = Conf

    data = data_class(config=config, args=args, conf=conf)
    data.build()

    if args.print_config:
        print(data.print_config())
        return

    if args.gcode or args.svg or args.png:
        if args.gcode:
            data.write_gcode()
        if args.svg:
            data.write_svg()
        if args.png:
            data.write_png()
    else:
        data.write_gcode()
        data.write_svg()


if __name__ == '__main__':
    sys.exit(main())
