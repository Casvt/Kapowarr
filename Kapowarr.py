#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from atexit import register
from multiprocessing import set_start_method
from os import environ, name
from signal import SIGINT, SIGTERM, signal
from subprocess import Popen
from sys import argv
from typing import NoReturn, Union

from backend.base.custom_exceptions import InvalidKeyValue
from backend.base.definitions import Constants, StartType
from backend.base.helpers import check_min_python_version, get_python_exe
from backend.base.logging import LOGGER, setup_logging
from backend.features.download_queue import DownloadHandler
from backend.features.tasks import TaskHandler
from backend.internals.db import set_db_location, setup_db
from backend.internals.server import SERVER, handle_start_type
from backend.internals.settings import Settings

import hupper

def _main(
    start_type: StartType,
    db_folder: Union[str, None] = None,
    log_folder: Union[str, None] = None,
    log_file: Union[str, None] = None,
    host: Union[str, None] = None,
    port: Union[int, None] = None,
    url_base: Union[str, None] = None
) -> NoReturn:
    """The main function of the Kapowarr sub-process.

    Args:
        start_type (StartType): The type of (re)start.

        db_folder (Union[str, None], optional): The folder in which the database
        will be stored or in which a database is for Kapowarr to use.
            Defaults to None.

        log_folder (Union[str, None], optional): The folder in which the logs
        from Kapowarr will be stored.
            Defaults to None.

        log_file (Union[str, None], optional): The filename of the file in which
        the logs from Kapowarr will be stored.
            Defaults to None.

        host (Union[str, None], optional): The host to bind the server to.
            Defaults to None.

        port (Union[int, None], optional): The port to bind the server to.
            Defaults to None.

        url_base (Union[str, None], optional): The URL base to use for the
        server.
            Defaults to None.

    Raises:
        ValueError: One of the arguments has an invalid value.

    Returns:
        NoReturn: Exit code 0 means to shutdown.
        Exit code 131 or higher means to restart with possibly special reasons.
    """
    set_start_method('spawn')
    setup_logging(log_folder, log_file)
    LOGGER.info('Starting up Kapowarr')

    if not check_min_python_version(*Constants.MIN_PYTHON_VERSION):
        exit(1)

    set_db_location(db_folder)

    SERVER.create_app()

    with SERVER.app.app_context():
        handle_start_type(start_type)
        setup_db()

        s = Settings()
        s.restart_on_hosting_changes = False

        if host:
            try:
                s.update({"host": host})
            except InvalidKeyValue:
                raise ValueError("Invalid host value")

        if port:
            try:
                s.update({"port": port})
            except InvalidKeyValue:
                raise ValueError("Invalid port value")

        if url_base is not None:
            try:
                s.update({"url_base": url_base})
            except InvalidKeyValue:
                raise ValueError("Invalid url base value")

        s.restart_on_hosting_changes = True
        settings = s.get_settings()
        SERVER.set_url_base(settings.url_base)

        download_handler = DownloadHandler()
        download_handler.load_downloads()
        task_handler = TaskHandler()
        task_handler.handle_intervals()

    try:
        # =================
        SERVER.run(settings.host, settings.port)
        # =================

    finally:
        download_handler.stop_handle()
        task_handler.stop_handle()

        if SERVER.start_type is not None:
            LOGGER.info('Restarting Kapowarr')
            exit(SERVER.start_type.value)

        exit(0)


def _stop_sub_process(proc: Popen) -> None:
    """Gracefully stop the sub-process unless that fails. Then terminate it.

    Args:
        proc (Popen): The sub-process to stop.
    """
    if proc.returncode is not None:
        return

    try:
        if name != 'nt':
            try:
                proc.send_signal(SIGINT)
            except ProcessLookupError:
                pass
        else:
            import win32api  # type: ignore
            import win32con  # type: ignore
            try:
                win32api.GenerateConsoleCtrlEvent(
                    win32con.CTRL_C_EVENT, proc.pid
                )
            except KeyboardInterrupt:
                pass
    except BaseException:
        proc.terminate()


def _run_sub_process(
    start_type: StartType = StartType.STARTUP
) -> int:
    """Start the sub-process that Kapowarr will be run in.

    Args:
        start_type (StartType, optional): Why Kapowarr was started.
            Defaults to `StartType.STARTUP`.

    Returns:
        int: The return code from the sub-process.
    """
    env = {
        **environ,
        "KAPOWARR_RUN_MAIN": "1",
        "KAPOWARR_START_TYPE": str(start_type.value)
    }

    py_exe = get_python_exe()
    if not py_exe:
        print("ERROR: Python executable not found")
        return 1

    comm = [py_exe, "-u", __file__] + argv[1:]
    proc = Popen(
        comm,
        env=env
    )
    proc._sigint_wait_secs = Constants.SUB_PROCESS_TIMEOUT # type: ignore
    register(_stop_sub_process, proc=proc)
    signal(SIGTERM, lambda signal_no, frame: _stop_sub_process(proc))

    try:
        return proc.wait()
    except (KeyboardInterrupt, SystemExit, ChildProcessError):
        return 0


def Kapowarr() -> int:
    """The main function of Kapowarr.

    Returns:
        int: The return code.
    """
    rc = StartType.STARTUP.value
    while rc in StartType._member_map_.values():
        rc = _run_sub_process(
            StartType(rc)
        )

    return rc

def main():
    if environ.get("ENV") == "development":
        hupper.start_reloader("Kapowarr.main")

    if environ.get("KAPOWARR_RUN_MAIN") == "1":

        parser = ArgumentParser(
            description="Kapowarr is a software to build and manage a comic book library, fitting in the *arr suite of software.")

        fs = parser.add_argument_group(title="Folders and files")
        fs.add_argument(
            '-d', '--DatabaseFolder',
            type=str,
            help="The folder in which the database will be stored or in which a database is for Kapowarr to use"
        )
        fs.add_argument(
            '-l', '--LogFolder',
            type=str,
            help="The folder in which the logs from Kapowarr will be stored"
        )
        fs.add_argument(
            '-f', '--LogFile',
            type=str,
            help="The filename of the file in which the logs from Kapowarr will be stored"
        )

        hs = parser.add_argument_group(title="Hosting settings")
        hs.add_argument(
            '-o', '--Host',
            type=str,
            help="The host to bind the server to"
        )
        hs.add_argument(
            '-p', '--Port',
            type=int,
            help="The port to bind the server to"
        )
        hs.add_argument(
            '-u', '--UrlBase',
            type=str,
            help="The URL base to use for the server"
        )

        args = parser.parse_args()

        st = StartType(int(environ.get(
            "KAPOWARR_START_TYPE",
            StartType.STARTUP.value
        )))

        db_folder: Union[str, None] = args.DatabaseFolder
        log_folder: Union[str, None] = args.LogFolder
        log_file: Union[str, None] = args.LogFile
        host: Union[str, None] = None
        port: Union[int, None] = None
        url_base: Union[str, None] = None
        if st == StartType.STARTUP:
            host = args.Host
            port = args.Port
            url_base = args.UrlBase

        try:
            _main(
                start_type=st,
                db_folder=db_folder,
                log_folder=log_folder,
                log_file=log_file,
                host=host,
                port=port,
                url_base=url_base
            )

        except ValueError as e:
            if not e.args:
                raise e

            elif e.args[0] == 'Database location is not a folder':
                parser.error(
                    'The value for -d/--DatabaseFolder is not a folder'
                )

            elif e.args[0] == 'Logging folder is not a folder':
                parser.error(
                    'The value for -l/--LogFolder is not a folder'
                )

            elif e.args[0] == 'Logging file is not a file':
                parser.error(
                    'The value for -f/--LogFile is not a file'
                )

            elif e.args[0] == 'Invalid host value':
                parser.error(
                    'The value for -h/--Host is not valid'
                )

            elif e.args[0] == 'Invalid port value':
                parser.error(
                    'The value for -p/--Port is not valid'
                )

            elif e.args[0] == 'Invalid url prefix value':
                parser.error(
                    'The value for -u/--UrlPrefix is not valid'
                )

            else:
                raise e

    else:
        rc = Kapowarr()
        exit(rc)

if __name__ == "__main__":
    main()
