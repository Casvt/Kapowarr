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

from backend.db import close_all_db, set_db_location, setup_db
from backend.helpers import check_python_version, get_python_exe
from backend.logging import LOGGER, setup_logging
from backend.server import SERVER
from frontend.api import Settings, download_handler, task_handler

SUB_PROCESS_TIMEOUT = 20.0


def _main(db_folder: Union[str, None] = None) -> NoReturn:
    """The main function of the Kapowarr sub-process

    Args:
        db_folder (Union[str, None], optional): The folder in which the database
        will be stored or in which a database is for Kapowarr to use. Give
        `None` for the default location.
            Defaults to None.

    Raises:
        ValueError: Value of `db_folder` exists but is not a folder.

    Returns:
        NoReturn: Exit code 0 means to shutdown.
        Exit code 131 means to restart.
    """
    set_start_method('spawn')
    setup_logging()
    LOGGER.info('Starting up Kapowarr')

    if not check_python_version():
        exit(1)

    set_db_location(db_folder)

    SERVER.create_app()

    with SERVER.app.app_context():
        setup_db()

        settings = Settings()
        host: str = settings['host']
        port: int = settings['port']
        url_base: str = settings['url_base']
        SERVER.set_url_base(url_base)

        download_handler.create_download_folder()

    download_handler.load_download_thread.start()
    task_handler.handle_intervals()

    # =================
    SERVER.run(host, port)
    # =================

    download_handler.stop_handle()
    task_handler.stop_handle()
    close_all_db()

    if SERVER.do_restart:
        LOGGER.info('Restarting Kapowarr')
        exit(131)

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


def _run_sub_process() -> int:
    """Start the sub-process that Kapowarr will be run in.

    Returns:
        int: The return code from the sub-process.
    """
    comm = [get_python_exe(), "-u", __file__] + argv[1:]
    proc = Popen(
        comm,
        env={
            **environ,
            "KAPOWARR_RUN_MAIN": "1"
        }
    )
    proc._sigint_wait_secs = SUB_PROCESS_TIMEOUT # type: ignore
    register(_stop_sub_process, proc=proc)
    signal(SIGTERM, lambda signal_no, frame: _stop_sub_process(proc))

    try:
        return proc.wait()
    except (KeyboardInterrupt, SystemExit, ChildProcessError):
        return 0


def Kapowarr() -> int:
    """The main function of Kapowarr

    Returns:
        int: The return code.
    """
    rc = 131
    while rc == 131:
        rc = _run_sub_process()

    return rc


if __name__ == "__main__":
    if environ.get("KAPOWARR_RUN_MAIN") == "1":

        parser = ArgumentParser(
            description="Kapowarr is a software to build and manage a comic book library, fitting in the *arr suite of software.")
        parser.add_argument(
            '-d', '--DatabaseFolder',
            type=str,
            help="The folder in which the database will be stored or in which a database is for Kapowarr to use"
        )

        args = parser.parse_args()
        try:
            _main(db_folder=args.DatabaseFolder)
        except ValueError:
            parser.error("The value for -d/--DatabaseFolder is not a folder")

    else:
        rc = Kapowarr()
        exit(rc)
