"""Read-only synthetic CPU infrastructure acceptance, never an Actor result.

Use only the owned source snapshot and exact, pre-inspected external weights.
The seccomp phase rejects filesystem mutation and networking. Output goes to
stdout, redirected by the trusted launcher into the owned evidence directory.
"""
from __future__ import annotations

import ctypes
import contextlib
import errno
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import socket
import sys
import time
from typing import Any

ROOT = Path('/home/duandh/projects/EEG-AI-Scientist-20261030')
RESOURCES = {
    'cbramod': ('/neurobench/checkpoints/omni/pretrained_weights.pth',
                '0792cb808c14e6b7a2bb2ce1dff379bc47bc54c49a779825bdfeb33bf8157178'),
    'reve_base': ('/neurobench/checkpoints/omni/reve-base/model.safetensors',
                  '8ecc650619598748286c2457f81f5c6bd12e8bb59db44f7b02af1955c44de8fe'),
    'reve_positions': ('/neurobench/checkpoints/omni/reve-positions/model.safetensors',
                       '4b793820b9df0998667deb6c8ce2dbb86b38221d5165c1844bc4971941b13f13'),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def readonly_seccomp() -> dict[str, Any]:
    """No namespaces required; fail closed if libseccomp cannot install rules."""
    class Comparison(ctypes.Structure):
        _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_uint),
                    ('datum_a', ctypes.c_uint64), ('datum_b', ctypes.c_uint64)]

    seccomp = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                              ctypes.c_int, ctypes.c_uint,
                                              ctypes.POINTER(Comparison)]
    seccomp.seccomp_rule_add_array.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    seccomp.seccomp_attr_set.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError('seccomp_init failed')
    deny = 0x00050000 | errno.EACCES
    denied: list[str] = []

    def rule(name: str, comparison: Comparison | None = None) -> None:
        syscall = seccomp.seccomp_syscall_resolve_name(name.encode())
        if syscall < 0:
            return
        result = seccomp.seccomp_rule_add_array(
            context, deny, syscall, int(comparison is not None),
            ctypes.byref(comparison) if comparison is not None else None)
        if result != 0:
            raise RuntimeError(f'seccomp rule {name}: {result}')
        denied.append(name)

    for name in ('creat', 'openat2', 'unlink', 'unlinkat', 'rename', 'renameat',
                 'renameat2', 'mkdir', 'mkdirat', 'rmdir', 'link', 'linkat',
                 'symlink', 'symlinkat', 'chmod', 'fchmod', 'fchmodat',
                 'chown', 'fchown', 'lchown', 'fchownat', 'truncate', 'ftruncate',
                 'mknod', 'mknodat', 'mount', 'umount2', 'setxattr', 'lsetxattr',
                 'fsetxattr', 'removexattr', 'lremovexattr', 'fremovexattr',
                 'utime', 'utimes', 'utimensat', 'socket', 'socketpair',
                 'connect', 'ptrace', 'process_vm_writev', 'io_uring_setup'):
        rule(name)
    # Masked equality catches each individual write/create/truncate flag.
    for name, argument in (('open', 1), ('openat', 2)):
        for flag in (os.O_WRONLY, os.O_RDWR, os.O_CREAT, os.O_TRUNC, os.O_APPEND):
            rule(name, Comparison(argument, 7, flag, flag))
    if seccomp.seccomp_attr_set(context, 4, 1) != 0:  # SCMP_FLTATR_CTL_TSYNC
        raise RuntimeError('Could not require seccomp synchronization across threads')
    result = seccomp.seccomp_load(context)
    seccomp.seccomp_release(context)
    if result != 0:
        raise RuntimeError(f'seccomp_load failed: {result}')
    try:
        (ROOT / 'evidence' / 'must-not-create.txt').open('wb')
    except PermissionError:
        pass
    else:
        raise AssertionError('Write sandbox ineffective')
    try:
        socket.socket()
    except PermissionError:
        pass
    else:
        raise AssertionError('Network sandbox ineffective')
    return {'mechanism': 'libseccomp filesystem-mutation/network deny',
            'write_negative_control': 'EACCES', 'network_negative_control': 'EACCES',
            'rules': len(denied),
            'synchronized_all_threads': True,
            'read_scope': 'not a read-isolated Actor sandbox',
            'namespace_isolation': False}


def load_exact(model: Any, state: dict[str, Any]) -> dict[str, Any]:
    import torch
    expected = model.state_dict()
    if set(expected) != set(state):
        raise AssertionError('State keys mismatch')
    for key, tensor in state.items():
        if tensor.shape != expected[key].shape or not torch.isfinite(tensor).all():
            raise AssertionError(f'Invalid tensor: {key}')
    result = model.load_state_dict(state, strict=True)
    assert not result.missing_keys and not result.unexpected_keys
    return {'strict': True, 'keys': len(state),
            'parameters': sum(parameter.numel() for parameter in model.parameters()),
            'all_checkpoint_tensors_finite': True}


def main() -> None:
    assert ROOT.resolve() == ROOT and ROOT.stat().st_uid == os.getuid() == 1027
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert Path(os.environ['TMPDIR']).is_relative_to(ROOT)
    source_manifest = json.loads((ROOT / 'evidence/source-provenance.json').read_text())
    assert source_manifest['source_commit'] == '0b24164977e82619de5ce0ab3d5e8f46f80d8a98'
    for relative, expected in source_manifest['files'].items():
        assert sha256(ROOT / 'source' / relative) == expected, f'Source changed: {relative}'
    cpus = sorted(os.sched_getaffinity(0))[:2]
    os.sched_setaffinity(0, cpus)
    os.nice(10)
    started = time.monotonic()
    import numpy as np
    import torch
    import transformers
    from safetensors import safe_open
    from safetensors.torch import load_file
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    assert torch.version.cuda is None
    sys.path.insert(0, str(ROOT / 'source' / 'framework'))
    import eegfm
    from eegfm.research_bench import real_data
    assert real_data.CHECKPOINT_SHA256 == RESOURCES['cbramod'][1]
    # The only imported model code is owned, hash-verified, pinned source.
    sys.path.insert(0, str(ROOT / 'source' / 'cbramod'))
    from models.cbramod import CBraMod
    sys.path.insert(0, str(ROOT / 'source' / 'framework/tasks/reve_isa/src/vendor'))
    from reve.configuration_reve import ReveConfig
    from reve.configuration_bank import RevePositionBankConfig
    with contextlib.redirect_stdout(sys.stderr):
        from reve.modeling_reve import Reve, ClassicalAttention
    from reve.position_bank import RevePositionBank
    report: dict[str, Any] = {
        'kind': 'synthetic_cpu_infrastructure_acceptance', 'actor_result': False,
        'real_eeg_data_read': False, 'gpu_use': False, 'cpus': cpus,
        'python': sys.version, 'torch': torch.__version__,
        'numpy': np.__version__, 'transformers': transformers.__version__,
        'source_commit': '0b24164977e82619de5ce0ab3d5e8f46f80d8a98',
        'source_archive_sha256': source_manifest['archive_sha256'],
        'project_imports': ['eegfm', 'eegfm.research_bench.real_data'],
        'dependencies': {name: importlib.metadata.version(name) for name in
                         ('torch', 'numpy', 'einops', 'transformers', 'safetensors')},
    }
    report['confinement'] = readonly_seccomp()
    bindings: dict[str, Any] = {}
    for name, (filename, expected) in RESOURCES.items():
        path = Path(filename)
        before = path.stat()
        observed = sha256(path)
        assert observed == expected, f'Resource changed: {name}'
        bindings[name] = {'path': filename, 'sha256': observed, 'bytes': before.st_size,
                          'uid': before.st_uid, 'inode': before.st_ino,
                          'mtime_ns': before.st_mtime_ns, 'access': 'read_only_in_place'}
        if path.suffix == '.safetensors':
            with safe_open(str(path), framework='pt', device='cpu') as handle:
                bindings[name]['schema'] = {
                    key: {'shape': handle.get_slice(key).get_shape(),
                          'dtype': handle.get_slice(key).get_dtype()}
                    for key in handle.keys()}
    report['resources'] = bindings
    torch.manual_seed(1729)
    backbone = CBraMod().cpu().eval()
    state = torch.load(RESOURCES['cbramod'][0], map_location='cpu', weights_only=True)
    report['cbramod'] = load_exact(backbone, state)
    sample = torch.linspace(-1, 1, 20 * 5 * 200).reshape(1, 20, 5, 200)
    with torch.inference_mode():
        output = backbone(sample)
    assert tuple(output.shape) == (1, 20, 5, 200) and torch.isfinite(output).all()
    report['cbramod'].update({'input_shape': list(sample.shape), 'output_shape': list(output.shape),
                              'output_finite': True, 'weights_only': True,
                              'output_sha256': hashlib.sha256(output.numpy().tobytes()).hexdigest()})
    vendor = ROOT / 'source/framework/tasks/reve_isa/src/vendor/reve'
    config = json.loads((vendor / 'config.json').read_text())
    position_config = json.loads((vendor / 'position_config.json').read_text())
    remote_config = Path('/neurobench/checkpoints/omni/reve-base/config.json')
    remote_positions = Path('/neurobench/checkpoints/omni/reve-positions/config.json')
    observed_config = json.loads(remote_config.read_text())
    observed_positions = json.loads(remote_positions.read_text())
    for key in ('depth', 'embed_dim', 'freqs', 'head_dim', 'heads', 'mlp_dim_ratio',
                'noise_ratio', 'patch_overlap', 'patch_size', 'use_geglu'):
        assert observed_config[key] == config[key], f'REVE config differs: {key}'
    assert observed_positions['position_names'] == position_config['position_names']
    report['resource_configs'] = {
        'base': {'path': str(remote_config), 'sha256': sha256(remote_config),
                 'architecture_matches_owned_config': True},
        'positions': {'path': str(remote_positions), 'sha256': sha256(remote_positions),
                      'ordered_names_match_owned_config': True}}
    reve = Reve(ReveConfig(**config)).cpu().eval()
    for attention, _ in reve.transformer.layers:
        attention.use_flash = False
        attention.attend = ClassicalAttention(attention.heads, use_sdpa=True)
    report['reve'] = load_exact(reve, load_file(RESOURCES['reve_base'][0], device='cpu'))
    bank = RevePositionBank(RevePositionBankConfig(**position_config)).cpu().eval()
    report['reve_positions'] = load_exact(bank, load_file(RESOURCES['reve_positions'][0], device='cpu'))
    channels = ['FP1', 'FP2', 'C3', 'C4']
    assert all(name in bank.mapping for name in channels)
    positions = bank(channels).unsqueeze(0)
    signal = torch.linspace(-1, 1, 4 * 1000).reshape(1, 4, 1000)
    with torch.inference_mode():
        features = reve(signal, positions)
    assert tuple(features.shape) == (1, 4, 5, 512) and torch.isfinite(features).all()
    report['reve'].update({'input_shape': list(signal.shape), 'position_shape': list(positions.shape),
                           'output_shape': list(features.shape), 'output_finite': True,
                           'channels': channels, 'attention': 'CPU torch SDPA',
                           'output_sha256': hashlib.sha256(features.numpy().tobytes()).hexdigest()})
    for name, (filename, expected) in RESOURCES.items():
        current = Path(filename).stat()
        assert current.st_size == bindings[name]['bytes']
        assert current.st_mtime_ns == bindings[name]['mtime_ns']
        assert sha256(Path(filename)) == expected
    report['resource_hashes_unchanged_after_probe'] = True
    report['worker_exit'] = 'flush result then _exit; retain owned import-time temporary files'
    report['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['elapsed_seconds'] = time.monotonic() - started
    report['status'] = 'passed'
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
    # This worker is permanently read-only after seccomp. Library atexit hooks
    # must not attempt to delete their import-time files. Keep those owned
    # temporary artifacts, flush the complete result, then exit the worker.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
