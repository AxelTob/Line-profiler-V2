import functools
import inspect
import linecache
import os
import sys
from line_profiler import LineProfiler


def is_coroutine(f):
    return inspect.iscoroutinefunction(f)


def is_generator(f):
    return inspect.isgeneratorfunction(f)


def is_classmethod(f):
    return isinstance(f, classmethod)


class MyLineProfiler(LineProfiler):
    def __call__(self, func):
        self.add_function(func)
        if is_classmethod(func):
            wrapper = self.wrap_classmethod(func)
        elif is_coroutine(func):
            wrapper = self.wrap_coroutine(func)
        elif is_generator(func):
            wrapper = self.wrap_generator(func)
        else:
            wrapper = self.wrap_function(func)
        return wrapper

    def wrap_classmethod(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            with self:
                result = func.__func__(func.__class__, *args, **kwds)
            return result
        return wrapper

    def wrap_coroutine(self, func):
        @functools.wraps(func)
        async def wrapper(*args, **kwds):
            with self:
                result = await func(*args, **kwds)
            return result
        return wrapper

    def wrap_generator(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            g = func(*args, **kwds)
            with self:
                item = next(g)
            input_ = (yield item)
            while True:
                with self:
                    item = g.send(input_)
                input_ = (yield item)
        return wrapper

    def wrap_function(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            with self:
                result = func(*args, **kwds)
            return result
        return wrapper

    def print_stats(self, stream=None, output_unit=None, stripzeros=False):
        stats = self.get_stats()
        show_text(stats.timings, stats.unit, output_unit=output_unit,
                  stream=stream, stripzeros=stripzeros)

    def add_module(self, mod):
        nfuncsadded = 0
        for item in mod.__dict__.values():
            if inspect.isclass(item):
                for k, v in item.__dict__.items():
                    if inspect.isfunction(v):
                        self.add_function(v)
                        nfuncsadded += 1
            elif inspect.isfunction(item):
                self.add_function(item)
                nfuncsadded += 1
        return nfuncsadded

    def show_func(filename, start_lineno, func_name, timings, unit,
                  output_unit=None, stream=None, stripzeros=False):
        if not stream:
            stream = sys.stdout
        if not os.path.exists(filename):
            stream.write(f"Could not find file {filename}\n")
            return
        total_time = sum(time for _, _, time in timings)
        if stripzeros and total_time == 0:
            return
        if not output_unit:
            output_unit = unit

        scalar = unit / output_unit
        stream.write(
            f"Total time in {func_name}: {total_time * scalar:6.3f} s\n")
        stream.write(f"File: {filename}\n")
        stream.write(f"Function: {func_name} at line {start_lineno}\n")

        linecache.clearcache()
        all_lines = linecache.getlines(filename)
        sublines = inspect.getblock(all_lines[start_lineno - 1:])

        d = {}
        for lineno, nhits, time in timings:
            percent = '' if sum(
                time for _, _, time in timings) == 0 else f'{100 * time / sum(time for _, _, time in timings): 5.1f}'
            d[lineno] = (nhits,
                         f"{time * scalar:5.1f}",
                         f"{float(time) * scalar / nhits:5.1f}",
                         percent)

        header = f"{'Line #':6} {'Hits':9} {'Time':12} {'Per Hit':8} {'% Time':8}  {'Line Contents':-s}"
        stream.write("\n" + header + "\n")
        stream.write("=" * len(header) + "\n")

        empty = ("", "", "", "")
        linenos = range(start_lineno, start_lineno + len(sublines))
        for lineno, line in zip(linenos, sublines):
            nhits, time, per_hit, percent = d.get(lineno, empty)
            txt = f"{lineno:6} {nhits:9} {time:12} {per_hit:8} {percent:8} {line.rstrip():-s}"
            stream.write(txt + "\n")

        stream.write("\n")


def show_text(stats, unit, output_unit=None, stream=None, stripzeros=False):
    """ Show text for the given timings.
    """
    if stream is None:
        stream = sys.stdout

    if output_unit is not None:
        stream.write('Timer unit: %g s\n\n' % output_unit)
    else:
        stream.write('Timer unit: %g s\n\n' % unit)

    for (fn, lineno, name), timings in sorted(stats.items()):
        show_func(fn, lineno, name, stats[fn, lineno, name], unit,
                  output_unit=output_unit, stream=stream,
                  stripzeros=stripzeros)


######## TEST ########
profile = LineProfiler()


def call_a():
    import time
    users = [{"user": {i}} for i in range(1000)]
    time.sleep(0.1)
    for _ in range(1000):
        pass
    return 1


def call_b():
    users = [{"user": {i}} for i in range(1000)]
    return users


@ profile
def testfunc():
    """ A function to test the profiler.
    """
    n = 10
    for i in range(n):
        print(i)
        call_a()

    call_b()


def main():
    testfunc()
    profile.print_stats(output_unit=1e-3)


if __name__ == '__main__':
    main()
