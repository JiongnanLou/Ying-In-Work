"""Install the separately distributed Windows runtime, verifying each file first."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name('runtime-manifest.json')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description='校验/准备 Link 2 Windows x64 运行组件')
    parser.add_argument('--archive', type=Path, help='从 Releases 下载的 runtime-windows-x64.zip')
    parser.add_argument('--check', action='store_true', help='仅检查现有运行组件')
    args = parser.parse_args()
    if args.archive and args.check:
        parser.error('--archive 与 --check 不能同时使用')
    files = json.loads(MANIFEST.read_text('utf-8'))['files']
    native = (ROOT/'product/native').resolve()
    targets = {}
    for name in files:
        target = (ROOT/name).resolve()
        if target.parent != native or target.suffix not in ('.dll', '.exe'):
            raise ValueError('运行组件清单含有非法目标路径')
        targets[name] = target

    if args.archive:
        # Validate every member before replacing anything in the project.
        with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(args.archive) as archive:
            staged = {}
            for name, info in files.items():
                member = archive.getinfo(name)
                if member.file_size != info['size']:
                    raise ValueError(f'文件大小不匹配：{name}')
                target = Path(folder)/targets[name].name
                with archive.open(member) as source, target.open('wb') as dest:
                    shutil.copyfileobj(source, dest)
                if digest(target) != info['sha256']:
                    raise ValueError(f'SHA256 校验失败：{name}')
                staged[name] = target
            native.mkdir(parents=True, exist_ok=True)
            for name, source in staged.items():
                target = targets[name]
                temporary = target.with_suffix(target.suffix+'.tmp')
                try:
                    shutil.copyfile(source, temporary)
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)

    missing = []
    for name, info in files.items():
        target = targets[name]
        ok = target.is_file() and target.stat().st_size == info['size'] and digest(target) == info['sha256']
        print(('OK ' if ok else 'MISSING/CHANGED ') + name)
        if not ok:
            missing.append(name)
    if missing:
        print('请下载同版本运行组件，再执行：python tools/setup_runtime.py --archive <压缩包路径>')
        return 1
    print('运行组件已就绪。')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise SystemExit(f'运行组件准备失败：{exc}')
