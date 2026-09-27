"""进程内临时计时钩子；退出后恢复模块引用，不修改生成与验收协议。"""

from collections import Counter, defaultdict
from contextlib import contextmanager
from functools import wraps
import json
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack

from .. import evaluator
from . import preflight, search, worker


class Timings:
    def __init__(self):
        self.stack = []
        self.stages = defaultdict(Counter)
        self.calls = Counter()
        self.traffic = Counter()

    @contextmanager
    def stage(self, name):
        frame = [name, perf_counter(), 0.0]
        self.stack.append(frame)
        self.calls[name] += 1
        try:
            yield
        finally:
            elapsed = perf_counter() - frame[1]
            self.stack.pop()
            self.stages[name]['total'] += elapsed - frame[2]
            if self.stack:
                self.stack[-1][2] += elapsed

    def wrap(self, function, name):
        @wraps(function)
        def measured(*args, **kwargs):
            with self.stage(name):
                return function(*args, **kwargs)
        return measured

    def leaf(self, name, function, *args, **kwargs):
        started = perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            self.stages[self.stack[-1][0]][name] += perf_counter() - started
            self.calls[name] += 1

    @contextmanager
    def installed(self):
        timer = self
        native = evaluator.mcscai_engine
        simulator = native.Simulator

        class Simulator:
            def __init__(self):
                self.inner = timer.leaf('rust', simulator)

            def apply(self, command):
                result = timer.leaf('rust', self.inner.apply, command)
                timer.traffic['command_chars'] += len(command)
                timer.traffic['snapshot_chars'] += len(result)
                return result

            def __getattr__(self, name):
                function = getattr(self.inner, name)
                if name == 'apply_native':
                    def apply_native(command):
                        result = timer.leaf('rust', function, command)
                        timer.traffic['native_snapshots'] += 1
                        return result
                    return apply_native
                return function

        bridge = SimpleNamespace(Simulator=Simulator, __version__=native.__version__)
        if hasattr(native, 'generator_preflight'):
            bridge.generator_preflight = lambda *a: self.leaf('rust', native.generator_preflight, *a)
        codec = SimpleNamespace(
            loads=lambda *a, **kw: self.leaf('json_decode', json.loads, *a, **kw),
            dumps=lambda *a, **kw: self.leaf('json_encode', json.dumps, *a, **kw))
        with ExitStack() as stack:
            for module in (evaluator, preflight):
                stack.enter_context(patch.object(module, 'mcscai_engine', bridge))
                stack.enter_context(patch.object(module, 'json', codec))
            for module, name, label in (
                (search, 'construct', '构造与搜索'),
                (search, 'check', '两轮物理预筛'),
                (worker, 'evaluate', '三轮正式验收'),
                (worker, 'inspect', '机制证据'),
                (worker, 'canonical', '对称指纹')):
                stack.enter_context(patch.object(module, name, self.wrap(getattr(module, name), label)))
            yield

    def report(self):
        stages = {}
        for name, values in self.stages.items():
            values = dict(values)
            values['python_other'] = values['total'] - sum(
                values.get(k, 0) for k in ('rust', 'json_encode', 'json_decode'))
            stages[name] = values
        return dict(stages=stages, calls=dict(self.calls), traffic=dict(self.traffic))
