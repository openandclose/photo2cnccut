#!/usr/bin/env python

"""Generate line cut (black to cut depth)."""

from photo2cnccut import base


class Data(base.Data):
    """Process line or point method data."""

    def build_lines(self, pointer=None):

        pointer = pointer or Pointer
        self.pointer = pointer(self.conf)

        _is_point = (self.conf.method == 'point')

        x, y = 0, 0
        direction = -1  # stop: 0, forward: 1, backward: -1
        line, lines = [], []
        move = self.pointer.move
        while True:
            kind, x, y = move(x, y, direction)
            if kind == 'end':
                if line:
                    lines.append(line)
                break
            # if method is point,
            # the script omits the last adjustment point (line border).
            elif _is_point and kind == 'last':
                continue
            elif kind == 'first':
                direction *= -1
                if line:
                    lines.append(line)
                line = []
            x, y = self.conf._round(x), self.conf._round(y)
            intensity = self.get_intensity(x, y)
            # TODO: Which is best, None, math.nan or -99999?
            if intensity is None:
                continue
            line.append([x, y, intensity])

        self.lines = lines


class Pointer(object):
    """Calculate next point."""

    def __init__(self, conf):
        self.conf = conf
        self.w, self.h = self.conf.width, self.conf.height
        self.tan = self.conf.tan

        self.step = self._get_step()
        self.linestep = self._get_linestep()

    def move(self, x, y, direction):
        _x, _y = self.step
        x2 = x + _x * direction
        y2 = y - _y * direction
        if self._is_inside(x2, y2):
            return '', x2, y2

        # if on the border, move to next line, flip direction
        limit = self._get_limit(direction)
        if x == limit[0] or y == limit[1]:
            x2, y2 = self._get_first_point(x, y, direction)
            if x2 is not None:
                return 'first', x2, y2

        # adjust the last point to the border
        x2, y2 = self._get_last_point(x, y, direction)
        if x2 != x:
            return 'last', x2, y2

        return 'end', None, None

    def _get_step(self):
        x = self.conf.resolution
        return x, x * self.tan

    def _get_linestep(self):
        distance = self.conf.maxwidth * self.conf.stepover
        if self.tan == 0:
            return 0, distance
        x = distance / self.conf.sin
        return x, x * self.tan

    def _is_inside(self, x, y):
        return (0 <= x <= self.w) and (0 <= y <= self.h)

    def _get_x(self, x, y, y2, direction=1):
        if self.tan == 0:
            raise ValueError('line angle is 0.')
        return x + abs(y - y2) / self.tan * direction

    def _get_y(self, y, x, x2, direction=1):
        return y - abs(x - x2) * self.tan * direction

    def _get_limit(self, direction=1):
        if direction == 1:
            return self.w, 0
        if direction == -1:
            return 0, self.h

    def _get_last_point(self, x, y, direction=1):
        limit = self._get_limit(direction)

        if self.tan == 0:
            return limit[0], y

        x_inc1 = abs(limit[0] - x)
        x_inc2 = abs(limit[1] - y) / self.tan
        if x_inc1 <= x_inc2:
            x2 = limit[0]
            y2 = y - x_inc1 * self.tan * direction
        else:
            x2 = x + x_inc2 * direction
            y2 = limit[1]
        return x2, y2

    def _get_first_point(self, x, y, direction=1):
        limit = self._get_limit(direction)

        _x, _y = self.linestep
        move_x = (x + _x, y)
        move_y = (x, y + _y)

        if self.tan == 0:
            point = (limit[0], y + _y)
        elif direction == 1:
            if y == limit[1]:
                point = move_x
                if point[0] > self.w:  # passed the top-right corner
                    y2 = self._get_y(0, point[0], self.w, direction=-1)
                    point = (self.w, y2)
            if x == limit[0]:
                point = move_y
        elif direction == -1:
            if x == limit[0]:
                point = move_y
                if point[1] > self.h:  # passed the bottom-left corner
                    x2 = self._get_x(0, point[1], self.h, direction=1)
                    point = (x2, self.h)
            if y == limit[1]:
                point = move_x

        if self._is_inside(*point):
            return point
        return None, None
