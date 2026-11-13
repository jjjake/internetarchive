import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import internetarchive.session as session_module
from internetarchive import ArchiveSession


def test_socket_instrumented_before_session_creation():
    result = subprocess.run(  # noqa: S603 -- the interpreter and script are fixed test inputs.
        [
            sys.executable,
            '-c',
            '''
import socket
original_connect = socket.socket.connect
import internetarchive.session
assert socket.socket.connect is not original_connect
patched_connect = socket.socket.connect
internetarchive.session.ArchiveSession()
internetarchive.session.ArchiveSession()
assert socket.socket.connect is patched_connect
''',
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_connection_info_is_shared_per_thread(tmp_path):
    first = ArchiveSession(config_file=str(tmp_path / 'empty.ini'))
    second = ArchiveSession(config_file=str(tmp_path / 'empty.ini'))
    with socket.socket() as listener:
        listener.settimeout(5)
        listener.bind(('127.0.0.1', 0))
        listener.listen(2)
        address = listener.getsockname()
        with socket.create_connection(address, timeout=5) as connection:
            main_info = first.get_connection_info().copy()
            assert main_info['src_port'] == connection.getsockname()[1]
            assert main_info['dst_port'] == address[1]
            assert second.get_connection_info() == main_info
        accepted, _ = listener.accept()
        accepted.close()

        def connect_in_worker():
            assert first.get_connection_info() == {}
            with socket.create_connection(address, timeout=5) as connection:
                info = second.get_connection_info().copy()
                assert info['src_port'] == connection.getsockname()[1]
                assert first.get_connection_info() == info
                return info

        with ThreadPoolExecutor(max_workers=1) as executor:
            worker_info = executor.submit(connect_in_worker).result(timeout=10)
        accepted, _ = listener.accept()
        accepted.close()
        assert worker_info['dst_port'] == address[1]
        assert first.get_connection_info() == main_info


def test_reloading_session_does_not_stack_socket_wrappers():
    result = subprocess.run(  # noqa: S603 -- the interpreter and script are fixed test inputs.
        [
            sys.executable,
            '-c',
            '''
import importlib
import socket
import internetarchive.session as session
session.ArchiveSession()
for _ in range(3):
    importlib.reload(session)
client = session.ArchiveSession()
with socket.socket() as listener:
    listener.settimeout(5)
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    with socket.create_connection(listener.getsockname(), timeout=5):
        assert client.get_connection_info()['dst_port'] == listener.getsockname()[1]
    accepted, _ = listener.accept()
    accepted.close()
''',
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
