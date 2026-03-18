# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('rich')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('textual')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# include dynamic submodules for yt_dlp which uses plugin-style imports
hiddenimports += collect_submodules('yt_dlp')

# Also include package data for the main package to ensure templates and modules
tmp_ret = collect_all('video_downloader')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# If a local "bundled_bins" directory exists, include its files as binaries
# This lets the build script copy ffmpeg/aria2c/etc into the bundle before packaging.
bundled_dir = os.path.join(os.path.abspath('.'), 'bundled_bins')
if os.path.isdir(bundled_dir):
    for fname in os.listdir(bundled_dir):
        fpath = os.path.join(bundled_dir, fname)
        if os.path.isfile(fpath):
            # (src, dest) - put bundled binaries under bundled_bins/ in the app folder
            binaries.append((fpath, os.path.join('bundled_bins', fname)))


a = Analysis(
    ['classydl_entry.py'],
    pathex=[os.path.abspath('.')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='classydl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX compression can cause issues on some systems; disable for reliability
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
