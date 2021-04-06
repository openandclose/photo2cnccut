
import argparse
import glob
import os
import subprocess
import sys

import photo2cnccut.base
import photo2cnccut.line
import photo2cnccut.ui

dirname = os.path.dirname(os.path.abspath(__file__))
datadir = os.path.join(dirname, 'data')
os.chdir(datadir)

REF_EXT = '.ref'


def verify_files(file1, file2):
    with open(file1) as f:
        with open(file2) as g:
            for line in f:
                assert line == g.readline()


class TestBasic:

    _CREATE_TESTFILES = False

    fname = '1.1x0.9.png'

    def test(self):
        config = {
            'width': 10,
            'height': 10,
            'maxwidth': 1.0,
            'resolution': 0.8,
            'stepover': 1.0,
        }

        _, args = photo2cnccut.ui._build_args([])
        args.fname = self.fname

        angles = (0, 10, 45, 70)

        for angle in angles:
            self._test(config, args, angle)

        config.update({'stepover': 1.5})

        for angle in angles:
            self._test(config, args, angle)

    def _test(self, config, args, angle):
        config.update({'line_angle': angle})
        d = photo2cnccut.line.Data(config=config, args=args)
        d.build()
        d.write_gcode()
        d.write_svg()

        fname = self.fname
        angle = config['line_angle']
        stepover = config['stepover']
        new = '%s-deg%02d-step%.1f' % (fname, angle, stepover)

        if self._CREATE_TESTFILES:
            os.rename(fname + '.nc', new + '.nc')
            os.rename(fname + '.svg', new + '.svg')
        else:
            verify_files(fname + '.nc', new + '.nc')
            os.remove(fname + '.nc')
            verify_files(fname + '.svg', new + '.svg')
            os.remove(fname + '.svg')

    def preview(self):
        svgs = sorted(glob.glob(self.fname + '*.svg'))
        pngs = []
        for svg in svgs:
            pngs.append(svg.replace('.svg', '.png'))

        for infile, outfile in zip(svgs, pngs):
            photo2cnccut.base.svg2png(100, 100, infile, outfile)

        from PIL import Image
        # inscape creates RGBA png
        image = Image.new(
            mode='RGBA', size=(220, int(120 * len(pngs) / 2)), color=255)
        y = 0
        for i, png in enumerate(pngs):
            im = Image.open(png)
            x = 120 if i % 2 else 0
            image.paste(im, (x, y))
            if i % 2:
                y += 120

        image.save(self.fname + '-all.png')

        for png in pngs:
            os.remove(png)


def test_cylinder():
    _test_main('cylinder.png')


def _test_main(fname):
    ref = fname + '.ref'
    photo2cnccut.ui.main([fname])
    verify_files(fname + '.nc', ref + '.nc')
    os.remove(fname + '.nc')
    verify_files(fname + '.svg', ref + '.svg')
    os.remove(fname + '.svg')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] in ('p', '-p', '--preview'):
        TestBasic().preview()
    else:
        TestBasic().test()
