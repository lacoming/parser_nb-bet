# -*- mode: python ; coding: utf-8 -*-
# parser_nb-bet PyInstaller spec — target exe < 10 MB

a = Analysis(
    ['src\\main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets/data', 'assets/data')],
    hiddenimports=[
        'rapidfuzz',
        'rapidfuzz.fuzz',
        'rapidfuzz.fuzz_cpp',
        'rapidfuzz.utils',
        'rapidfuzz.utils_cpp',
        'rapidfuzz._feature_detector_cpp',
        'lxml._elementpath',
        'zoneinfo',
        'src.paths',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL', 'pillow',
        'tkinter.test', 'unittest', 'pydoc', 'doctest', 'difflib',
        'setuptools', 'pkg_resources', 'wheel', 'test', 'xmlrpc', 'curses',
        'lxml.objectify', 'lxml.html.diff', 'lxml.html.clean', 'lxml.isoschematron',
        'lxml.sax', 'lxml.builder',
        'xlsxwriter',
        'openpyxl.chart', 'openpyxl.chartsheet', 'openpyxl.drawing',
        'openpyxl.pivot', 'openpyxl.comments', 'openpyxl.formula',
    ],
    noarchive=False,
    optimize=0,
)

# Strip unnecessary Tcl/Tk data to reduce size
# Keep only essential encodings
_tcl_enc_keep = {
    'ascii.enc', 'cp1250.enc', 'cp1251.enc', 'cp1252.enc',
    'cp866.enc', 'iso8859-1.enc', 'iso8859-15.enc',
    'iso8859-2.enc', 'iso8859-5.enc', 'koi8-r.enc', 'utf-8.enc',
}

_tzdata_keep = ('Europe/', 'Etc/', 'UTC', 'tzdata/__init__', 'METADATA')

def _should_strip_data(name):
    n = name.replace('\\', '/')
    # Strip CJK and unused Tcl encodings
    if '_tcl_data' in n and '/encoding/' in n:
        fname = n.rsplit('/', 1)[-1]
        return fname not in _tcl_enc_keep
    # Strip Tcl timezone data (Python uses zoneinfo, not Tcl)
    if '_tcl_data' in n and '/tzdata/' in n:
        return True
    # Strip Tcl test, demos, docs, http, msgcat, opt
    if 'tcltest' in n.lower():
        return True
    if 'demos' in n.lower():
        return True
    if 'tcl8/' in n:
        return True
    # Strip unnecessary Tcl scripts
    _tcl_strip = ('clock.tcl', 'safe.tcl', 'opt0.4/', 'msgs/')
    if '_tcl_data' in n and any(s in n for s in _tcl_strip):
        return True
    # Strip Tk images, PostScript, and console
    _tk_strip = ('images/', 'mkpsenc.tcl', 'console.tcl', 'msgs/')
    if '_tk_data' in n and any(s in n for s in _tk_strip):
        return True
    # Strip non-European tzdata zones (we only need Europe/Moscow)
    if 'tzdata/zoneinfo/' in n:
        if not any(k in n for k in _tzdata_keep):
            return True
    return False

a.datas = [(n, s, t) for n, s, t in a.datas if not _should_strip_data(n)]

# Strip unnecessary native extensions to save space
_strip_binaries = (
    'lxml\\sax', 'lxml\\builder', 'lxml/sax', 'lxml/builder',
    'lxml\\html\\_difflib', 'lxml/html/_difflib',
    'rapidfuzz\\distance\\metrics_cpp_avx2', 'rapidfuzz/distance/metrics_cpp_avx2',
    'rapidfuzz\\distance\\metrics_cpp.', 'rapidfuzz/distance/metrics_cpp.',
    'rapidfuzz\\process_cpp_impl', 'rapidfuzz/process_cpp_impl',
    'rapidfuzz\\process_cpp.', 'rapidfuzz/process_cpp.',
    'rapidfuzz\\process_cpp_avx2', 'rapidfuzz/process_cpp_avx2',
    'rapidfuzz\\fuzz_cpp_avx2', 'rapidfuzz/fuzz_cpp_avx2',
    'rapidfuzz\\utils_cpp_avx2', 'rapidfuzz/utils_cpp_avx2',
    'rapidfuzz\\distance\\_initialize_cpp', 'rapidfuzz/distance/_initialize_cpp',
)
a.binaries = [
    (n, s, t) for n, s, t in a.binaries
    if not any(x in n for x in _strip_binaries)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='parser_nb-bet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
