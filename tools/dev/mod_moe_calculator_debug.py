# -*- coding: utf-8 -*-
"""DEV-ONLY: TCP REPL into the running WoT client (adapted from juho-p/wot-debugserver).

Packaged as com.14th_ua.moe_calculator_debug.wotmod (see build_debug_wotmod.py) and dropped
in mods/<version>/. Listens on 127.0.0.1:2224 (the research bar's debug REPL owns 2223;
distinct ports let both mods' debug servers run at once). NOT shipped with the real mod.
IMPORTANT: keep this package SLIM (only this file) so it does not conflict with the
real mod's moe_calculator package (duplicate files make WoT ignore the whole package).
Python 2.7 (BigWorld runtime).
"""
import socket
import threading

try:
    from debug_utils import LOG_NOTE, LOG_CURRENT_EXCEPTION
except Exception:
    def LOG_NOTE(*a, **k):
        print 'wgdbg:', a
    def LOG_CURRENT_EXCEPTION():
        import traceback
        traceback.print_exc()

PORT = 2224
SENTINEL = '__WGEND__'
NEWLINE = '\r\n'


def _serve_once():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', PORT))
    s.listen(1)
    conn = f = None
    try:
        conn, _addr = s.accept()
        f = conn.makefile()
        local_vars = {}

        def echo(text):
            f.write(str(text))
            f.write(NEWLINE)
            f.flush()

        local_vars['echo'] = echo
        for line in f:
            line = line.strip()
            if line == 'QUIT':
                break
            if not line:
                echo(SENTINEL)
                continue
            try:
                try:
                    res = eval(line, local_vars)
                    echo(repr(res))
                except SyntaxError:
                    exec line in local_vars
            except Exception:
                import traceback
                echo(traceback.format_exc())
            echo(SENTINEL)
    finally:
        try:
            s.close()
        except Exception:
            pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if f is not None:
            try:
                f.close()
            except Exception:
                pass


def _run():
    LOG_NOTE('[moe_calculator-debug] REPL server starting on 127.0.0.1:%d' % PORT)
    while True:
        try:
            _serve_once()
            LOG_NOTE('[moe_calculator-debug] REPL connection closed, restarting listener')
        except Exception:
            LOG_CURRENT_EXCEPTION()


try:
    _t = threading.Thread(target=_run)
    _t.setDaemon(True)
    _t.start()
    LOG_NOTE('[moe_calculator-debug] thread started')
except Exception:
    LOG_CURRENT_EXCEPTION()
