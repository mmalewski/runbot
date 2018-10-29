# -*- coding: utf-8 -*-
"""Containerize builds

The docker image used for the build is tagged like this:
    :tests-VERSION
For example:
    :tests-12.0
    will user the Docker image odoo:tests-12.0

This file contains helpers to containerize builds with Docker.
When testing this file:
    the first parameter should be a directory containing Odoo.
    The second parameter should be the version number.
    The third parameter is the exposed port
"""

import datetime
import logging
import os
import shutil
import subprocess
import sys
import time


_logger = logging.getLogger(__name__)


def docker_run(build_dir, log_path, odoo_cmd, container_name, exposed_port=None, cpu_limit=None, preexec_fn=None):
    """Run tests in a docker container
    :param build_dir: the build directory that contains the Odoo sources to build.
                      This directory is shared as a volume with the container
    :param log_path: path to the logfile that will contain odoo stdout and stderr
    :param odoo_cmd: command that starts odoo
    :param container_name: used to give a name to the container for later reference
    :paral exposed_port: if not None, the 8069 port will be exposed as exposed_port number
    """
    # build cmd
    cmd_chain = []
    cmd_chain.append('cd /data/build')
    cmd_chain.append('head -1 odoo-bin | grep -q python3 && sudo pip3 install -r requirements.txt || sudo pip install -r requirements.txt')
    cmd_chain.append(' '.join(odoo_cmd))
    run_cmd = ' && '.join(cmd_chain)
    _logger.debug('Docker run command: %s', run_cmd)
    logs = open(log_path, 'w')

    # Prepare docker image
    docker_dir = os.path.join(build_dir, 'docker')
    os.makedirs(docker_dir, exist_ok=True)
    shutil.copy(os.path.join(os.path.dirname(__file__), 'data', 'Dockerfile'), docker_dir)
    subprocess.run(['docker', 'build', '--tag', 'odoo:runbot_tests', '.'],cwd=docker_dir)

    # start tests
    docker_command = [
        'docker', 'run', '--rm',
        '--name', container_name,
        '--volume=/var/run/postgresql:/var/run/postgresql',
        '--volume=%s:/data/build' % build_dir,
    ]
    if exposed_port:
        docker_command.extend(['-p', '127.0.0.1:%s:8069' % exposed_port])
    if cpu_limit:
        docker_command.extend(['--ulimit', 'cpu=%s' % cpu_limit])
    docker_command.extend(['odoo:runbot_tests', '/bin/bash', '-c', run_cmd])
    docker_run = subprocess.Popen(docker_command, stdout=logs, stderr=logs, preexec_fn=preexec_fn, close_fds=False)
    _logger.info('Started Docker container %s', container_name)
    return docker_run.pid

def docker_stop(container_name):
    """Stops the container named container_name"""
    _logger.info('Stopping container %s', container_name)
    dstop = subprocess.run(['docker', 'stop', container_name], stderr=subprocess.PIPE, check=True)

def docker_build(docker_file_path):
    """Build the test image"""
    _logger.info('Building docker image')
    dbuild = subprocess.run(['docker', 'build', '--tag', 'odoo:runbot_tests'])

if __name__ == '__main__':
    _logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.info('Start container tests')

    if len(sys.argv) < 5:
        _logger.error('Missing arguments: "%s build_dir odoo_version odoo_port db_name"', sys.argv[0])
        sys.exit(1)
    build_dir = sys.argv[1]
    odoo_version = sys.argv[2]
    odoo_port = sys.argv[3]
    db_name = sys.argv[4]
    os.makedirs(os.path.join(build_dir, 'logs'), exist_ok=True)
    os.makedirs(os.path.join(build_dir, 'datadir'), exist_ok=True)

    # Test stopping a non running container
    _logger.info('Test killing an non existing container')
    try:
        docker_stop('xy' * 5)
    except subprocess.CalledProcessError:
        _logger.warning('Expected Docker stop failure')

    # Test testing
    odoo_cmd = ['/data/build/odoo-bin', '-d %s' % db_name, '--addons-path=/data/build/addons', '--data-dir', '/data/build/datadir', '-r %s' % os.getlogin(), '-i', 'web',  '--test-enable', '--stop-after-init', '--max-cron-threads=0']
    logfile = os.path.join(build_dir, 'logs', 'logs-partial.txt')
    container_name = 'odoo-container-test-%s' % datetime.datetime.now().microsecond
    docker_run(build_dir, logfile, odoo_cmd, container_name)

    # Test stopping the container
    _logger.info('Waiting 30 sec before killing the build')
    time.sleep(30)
    docker_stop(container_name)
    time.sleep(3)

    # Test full testing
    import fcntl
    def lock(filename):
        fd = os.open(filename, os.O_CREAT | os.O_RDWR, 0o600)
        if hasattr(os, 'set_inheritable'):
            os.set_inheritable(fd, True)  # needed since pep-446
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


    def locked(filename):
        result = False
        try:
            fd = os.open(filename, os.O_CREAT | os.O_RDWR, 0o600)
        except OSError:
            return False
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:  # since pep-3151 fcntl raises OSError and IOError is now an alias of OSError
            result = True
        finally:
            os.close(fd)
        return result

    lock_path = os.path.join(build_dir, 'logs', 'lock.txt')
    def pfn():
        os.setsid()
        # close parent files
        os.closerange(3, os.sysconf("SC_OPEN_MAX"))
        lock(lock_path)

    logfile = os.path.join(build_dir, 'logs', 'logs-full-test.txt')
    container_name = 'odoo-container-test-%s' % datetime.datetime.now().microsecond
    docker_run(build_dir, logfile, odoo_cmd, container_name, preexec_fn=pfn)
    time.sleep(1) # give time for the lock

    while locked(lock_path):
        time.sleep(10)
        _logger.info("Waiting for %s to stop", container_name)

    # Test running
    logfile = os.path.join(build_dir, 'logs', 'logs-running.txt')
    odoo_cmd = ['/data/build/odoo-bin', '-d %s' % db_name, '--db-filter', '%s.*$' % db_name, '--addons-path=/data/build/addons', '-r %s' % os.getlogin(), '-i', 'web',  '--max-cron-threads=0', '--data-dir', '/data/build/datadir']
    container_name = 'odoo-container-test-%s' % datetime.datetime.now().microsecond
    docker_run(build_dir, logfile, odoo_cmd, container_name, exposed_port=odoo_port, cpu_limit=300)
