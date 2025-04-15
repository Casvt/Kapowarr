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

from backend.base.definitions import Constants, RestartVersion
from backend.base.helpers import check_python_version, get_python_exe
from backend.base.logging import LOGGER, setup_logging
from backend.features.download_queue import DownloadHandler
from backend.features.tasks import TaskHandler
from backend.implementations.flaresolverr import FlareSolverr
from backend.internals.db import close_all_db, set_db_location, setup_db
from backend.internals.server import SERVER, handle_restart_version
from backend.internals.settings import Settings


def _main(
    restart_version: RestartVersion,
    db_folder: Union[str, None] = None,
    log_folder: Union[str, None] = None,
) -> NoReturn:
    """The main function of the Kapowarr sub-process

    Args:
        restart_version (RestartVersion): The type of (re)start.

        db_folder (Union[str, None], optional): The folder in which the database
        will be stored or in which a database is for Kapowarr to use. Give
        `None` for the default location.
            Defaults to None.

        log_folder (Union[str, None], optional): The folder in which the logs from
        Kapowarr will be stored. Give `None` for the default location.
            Defaults to None.

    Raises:
        ValueError: Value of `db_folder` exists but is not a folder.

    Returns:
        NoReturn: Exit code 0 means to shutdown.
        Exit code 131 or higher means to restart with possibly special reasons.
    """
    set_start_method('spawn')
    setup_logging(log_folder=log_folder)
    LOGGER.info('Starting up Kapowarr')

    if not check_python_version():
        exit(1)

    set_db_location(db_folder)

    SERVER.create_app()

    with SERVER.app.app_context():
        handle_restart_version(restart_version)
        setup_db()

        settings = Settings().get_settings()
        flaresolverr = FlareSolverr()
        SERVER.set_url_base(settings.url_base)

        if settings.flaresolverr_base_url:
            flaresolverr.enable_flaresolverr(settings.flaresolverr_base_url)

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
        flaresolverr.disable_flaresolverr()
        close_all_db()

        if SERVER.restart_version is not None:
            LOGGER.info('Restarting Kapowarr')
            exit(SERVER.restart_version.value)

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
    restart_version: RestartVersion = RestartVersion.NORMAL
) -> int:
    """Start the sub-process that Kapowarr will be run in.

    Args:
        restart_version (RestartVersion, optional): Why Kapowarr was restarted.
            Defaults to `RestartVersion.NORMAL`.

    Returns:
        int: The return code from the sub-process.
    """
    env = {
        **environ,
        "KAPOWARR_RUN_MAIN": "1",
        "KAPOWARR_RESTART_VERSION": str(restart_version.value)
    }

    comm = [get_python_exe(), "-u", __file__] + argv[1:]
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
    """The main function of Kapowarr

    Returns:
        int: The return code.
    """
    rc = RestartVersion.NORMAL.value
    while rc in RestartVersion._member_map_.values():
        rc = _run_sub_process(
            RestartVersion(rc)
        )

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
        parser.add_argument(
            '-l', '--LogFolder',
            type=str,
            help="The folder in which the logs from Kapowarr will be stored"
        )
        args = parser.parse_args()

        rv = RestartVersion(int(environ.get(
            "KAPOWARR_RESTART_VERSION",
            RestartVersion.NORMAL.value
        )))

        try:
            _main(
                restart_version=rv,
                db_folder=args.DatabaseFolder,
                log_folder=args.LogFolder,
            )

        except ValueError as e:
            if e.args and e.args[0] == 'Database location is not a folder':
                parser.error(
                    "The value for -d/--DatabaseFolder is not a folder"
                )
            else:
                raise e

    else:
        rc = Kapowarr()
        exit(rc)
