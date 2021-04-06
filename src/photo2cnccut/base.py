#!/usr/bin/env python

"""Define data interface from point data to formatted files."""

import math
import os
import subprocess
import textwrap

import PIL.Image

from photo2cnccut import ui


class Data(object):
    """Base data class.

    Subclasses should somehow fill ``self.lines``,
    usually by extending ``.build_lines``.

    g-code and svg formatters need this ``self.lines``.

    Other methods are just helpers for convenience.
    """

    def __init__(self, config=None, args=None, conf=None):
        conf = conf or ui.Conf
        self.conf = conf(config=config, args=args)

        self.g_formatter = GFormatter
        self.svg_formatter = SVGFormatter
        self.png_formatter = PNGFormatter
        self.lines = []

        self.init2()

    def init2(self):
        """Customize this."""

    def build(self, pixels=None, lines=None):
        """Build self.lines."""
        if pixels is None:
            self.load_image()
        else:
            self.pixels = pixels

        if lines is None:
            self.build_lines()
        else:
            self.lines = lines

        self.conf._time('build:')

    def build_lines(self):
        """Customize this."""

    def load_image(self, fname=None):
        """Load image and build self.pixels."""
        fname = fname or self.conf.fname
        self._im = PIL.Image.open(fname)

        self.get_sizes(self._im)
        self.get_pixels(self._im)

        self.conf._time('load:')

    def get_sizes(self, im):
        self.conf.width, self.conf.height = self._get_sizes(im)

    def _get_sizes(self, im):
        ratio = im.height / im.width
        w = self.conf.width
        if w:
            h = int(w * ratio)  # floor
        else:
            h = self.conf.height
            w = int(h / ratio)
        return w, h

    def get_pixels(self, im):
        if im.mode != 'L':
            im = im.convert('L')  # to grayscale
        # self.pixels = numpy.array(im)
        self.pixels = im.getdata()

    def get_intensity(self, x, y):
        intensity = self._get_intensity(x, y, self.pixels)
        return self.process_intensity(intensity)

    def _get_intensity(self, x, y, pixels):
        img_width = self._im.width
        scale = img_width / self.conf.width

        x, y = round(x * scale), round(y * scale)
        try:
            # return pixels[y -1, x -1]  # numpy version
            return pixels[x + (y - 1) * img_width - 1]
        except IndexError:
            return 255

    def process_intensity(self, intensity):
        """Customize this."""
        return intensity

    def write_gcode(self, lines=None):
        lines = lines or self.lines
        formatter = self.g_formatter(self.conf, lines)
        with open(self.conf.fname + '.nc', 'w') as f:
            for chunk in formatter.format():
                f.write(chunk)
        self.info(formatter)
        self.conf._time('gcode:')

    def write_svg(self, lines=None):
        lines = lines or self.lines
        formatter = self.svg_formatter(self.conf, lines)
        with open(self.conf.fname + '.svg', 'w') as f:
            for chunk in formatter.format():
                f.write(chunk)
        self.conf._time('svg:')

    def write_png(self):
        formatter = self.png_formatter(self.conf)
        formatter.format()
        self.conf._time('png:')

    def info(self, formatter):
        if self.conf._args.quiet:
            return
        # print('config version: %s' % self.conf._version)
        print('depth range: %s to %s' % formatter._get_depth_range())
        print('estimated cut time: %s' % formatter._estimate())

    def print_config(self):
        ret = []
        ret.append('config = {')
        for k, v in self.conf._config.items():
            ret.append('    %r: %r,' % (k, getattr(self.conf, k)))
        ret.append('}')
        return('\n'.join(ret))


class Formatter(object):
    """base Formatter class."""

    def __init__(self, conf, lines):
        self.conf = conf
        self.lines = lines

    def _get_width(self, intensity):
        return self.conf.maxwidth * ((255 - intensity) / 255)


class GFormatter(Formatter):
    """Create G-code string."""

    def __init__(self, conf, lines):
        super().__init__(conf, lines)
        self._depth_cache = {}  # MEMO: 0.241s -> 0.055s

        angle = (self.conf.tool_angle / 2) * (math.pi / 180)
        self.tool_tan = math.tan(angle)  # tool width / depth ratio

    def format(self):
        # using prev, just to avoid adding 'M1' to first and last lines.
        self.linenum = self.conf.line_number_increment
        prev = None
        _add_num = self._add_line_number

        if self.conf.header:
            yield from self._add_lines(self.conf.header)

        for line in self._format():
            if prev is None:
                prev = _add_num(' '.join(line))
            else:
                yield prev
                yield '\n'
                prev = _add_num(' '.join(line), m1=True)

        yield _add_num(' '.join(line))
        yield '\n'

        if self.conf.footer:
            yield from self._add_lines(self.conf.footer)

    def _add_lines(self, lines):
        for line in lines.split('\n'):
            yield self._add_line_number(line)
            yield '\n'

    def _add_line_number(self, line, m1=False):
        def _add_num(line):
            num = self.linenum
            self.linenum += inc
            return 'N' + str(num) + ' ' + line

        type_ = self.conf.line_number_type
        inc = self.conf.line_number_increment

        if type_ == 'all':
            return _add_num(line)
        if type_ == 'retract' and line.startswith('G0 '):
            if m1:
                return _add_num(line) + ' M1'
            else:
                return _add_num(line)

        return line

    def _format(self):
        _f = self._format_number
        _is_cut_through = self.conf.cut_through
        _is_point = (self.conf.method == 'point')

        initial = 'Z' + _f(self.conf.initial_z)
        retract = 'Z' + _f(self.conf.retract_z)

        yield ['G0', 'X0', 'Y0']
        yield [initial]
        yield [retract]

        for line in self.lines:
            first = True
            for point in line:
                x, y, intensity = _f(point[0]), _f(point[1] * -1), point[2]
                depth = _f(self._get_depth(intensity) * -1)
                if first:
                    first = False
                    if _is_cut_through:
                        yield ['X' + x, 'Y' + y]
                        yield ['Z' + depth]
                        yield ['G1']
                    else:
                        yield ['X' + x, 'Y' + y]
                        yield ['G1', 'Z' + depth]
                    if _is_point:
                        yield ['G0', retract]
                else:
                    if _is_point:
                        yield ['X' + x, 'Y' + y]
                        yield ['G1', 'Z' + depth]
                        yield ['G0', retract]
                    else:
                        yield ['X' + x, 'Y' + y, 'Z' + depth]

            if not _is_cut_through:
                yield ['G0', retract]

        yield [initial]

    def _format_number(self, num):  # number to string
        if num == 0:
            return '0'  # 0, -0, 0., 0.0 -> '0'

        s = str(num)
        if '.' in s:
            return s
        else:
            return s + '.'  # 1 -> '1.'

    def _get_depth(self, intensity):
        cache = self._depth_cache
        try:
            return cache[intensity]
        except KeyError:
            width = self._get_width(intensity)
            depth = (width / 2) / self.tool_tan
            depth = round(depth, self.conf.digit)
            cache[intensity] = depth
            return cache[intensity]

    # get actual min and max depth from cache
    def _get_depth_range(self):
        min_ = self._depth_cache[max(self._depth_cache)] * -1 or 0
        max_ = self._depth_cache[min(self._depth_cache)] * -1
        return min_, max_

    # estimate cut time (plunge + feed, omit rapid moves)
    def _estimate(self):
        retract = self.conf.retract_z
        _get_depth = lambda x: abs(self._get_depth(x))
        points = (point for line in self.lines for point in line)

        if self.conf.method == 'line':
            x = sum(abs(line[0][0] - line[-1][0]) for line in self.lines)
            xy = x / self.conf.cos
            z_above = retract * len(self.lines)
            z_below = sum(_get_depth(point[2]) for point in points)
            distance = z_above + math.hypot(xy, z_below)
        else:
            distance = sum(retract + _get_depth(point[2]) for point in points)

        t = round(distance / self.conf.feed * 60)

        if t < 60:
            return '%d sec' % t
        elif t < 3600:
            return '%d min %d sec' % (t // 60, t % 60)
        else:
            m, s = t // 60, t % 60
            return '%d h %d min %d sec' % (m // 60, m % 60, s)


class SVGFormatter(Formatter):
    """Create SVG string."""

    beginning = """
        <svg width="%s" height="%s" viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg" fill="%s">
        <rect width="%s" height="%s" fill="%s" />
    """  # noqa E501 line too long

    ending = """
        </svg>
    """

    def __init__(self, conf, lines):
        super().__init__(conf, lines)
        self._inc_cache = {}  # MEMO: 0.105s -> 0.061s

    def format(self):
        _is_point = (self.conf.method == 'point')

        yield self._get_beginning()
        yield '\n'
        for line in self.lines:
            if _is_point:
                yield ''.join(self._format_circle(line))
            else:
                yield ''.join(self._format_path(line))
        yield self._get_ending()

    def _get_beginning(self):
        text = textwrap.dedent(self.beginning.lstrip('\n').rstrip())
        w, h = self.conf.width, self.conf.height
        W, H = self._get_size()
        color, background = self.conf.svg_color, self.conf.svg_background
        return text % (W, H, w, h, color, w, h, background)

    def _get_size(self):
        w, h = self.conf.width, self.conf.height
        scale = self.conf.svg_scale
        _round = self.conf._round
        return _round(w * scale), _round(h * scale)

    def _get_ending(self):
        text = textwrap.dedent(self.ending.lstrip('\n').rstrip())
        return text

    def _format_circle(self, line):  # method: point
        for point in line:
            x, y, intensity = point
            x, y = self.conf._round(x), self.conf._round(y)
            radius = self._get_width(intensity) / 2
            yield '<circle cx="%s" cy="%s" r="%s"/>' % (x, y, radius)
            yield '\n'

    def _format_path(self, line):  # method: line
        first = True
        for point in self._build_points(line):
            x, y = point
            x, y = self.conf._round(x), self.conf._round(y)
            if first:
                first = False
                yield '<path d="M '
            else:
                yield 'L '
            yield '%s %s ' % (x, y)
        yield 'Z"/>\n'

    def _build_points(self, line):
        going = []
        comming = []
        for point in line:
            p1, p2 = self._get_apexes(point)
            going.append(p1)
            comming.append(p2)
        comming.reverse()
        return going + comming

    def _get_apexes(self, point, is_edge=False):
        x, y, intensity = point
        xi, yi = self._get_xy_inc(intensity)
        p1 = x - xi, y - yi
        p2 = x + xi, y + yi
        return p1, p2

    def _get_xy_inc(self, intensity):
        cache = self._inc_cache
        try:
            return cache[intensity]
        except KeyError:
            radius = self._get_width(intensity) / 2
            xi = radius * self.conf.sin
            yi = radius * self.conf.cos
            cache[intensity] = xi, yi
            return cache[intensity]


def svg2png(width, height, infile, outfile):
    cmd = ['inkscape', '-w', str(width), '-h', str(height),
            '--export-filename', outfile, infile]
    subprocess.run(cmd)


class PNGFormatter(Formatter):
    """Create PNG file. Use inkscape."""

    def __init__(self, conf):
        self.conf = conf

    def format(self):
        infile = self.conf.fname + '.svg'
        outfile = self.conf.fname + '.png'
        if not os.path.isfile(infile):
            msg = 'png formatting needs svg file: %s' % infile
            raise FileNotFoundError(msg)

        scale = self.conf.svg_scale * self.conf.png_scale
        width = int(self.conf.width * scale)
        height = int(self.conf.height * scale)
        svg2png(width, height, infile, outfile)
