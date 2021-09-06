import json
import logging
import os
import random
import socket
import string
import sys
import time
from io import StringIO, BytesIO
from textwrap import dedent
from threading import Thread

import pytest
import requests

from conftest import S3Mock, patch_manifest_func_mock
from requests.auth import HTTPBasicAuth

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
logging.basicConfig(format='%(name)s > %(message)s', level=logging.INFO)


def random_string(length=10):
    letters = string.ascii_letters
    return ''.join([random.choice(letters) for _ in range(length)])


USER = random_string()
PASSWORD = random_string()
SERVER_MOCK = 'http://0.0.0.0:5000'


@pytest.fixture
def app(monkeypatch):
    import app
    S3Mock.instance = None
    monkeypatch.setattr(app.boto3, 'client', S3Mock)
    monkeypatch.setattr(app, 'USER', USER)
    monkeypatch.setattr(app, 'PASSWORD', PASSWORD)
    monkeypatch.setattr(app, 'patch_manifest_func', patch_manifest_func_mock)

    def run_server():
        server_is_ready = False
        while not server_is_ready:
            try:
                app.app.run(host='0.0.0.0', port=5000)
            except OSError:
                time.sleep(0.1)
            finally:
                server_is_ready = False

    thread = Thread(target=run_server)
    thread.daemon = True
    thread.start()
    logging.info("New server thread started")

    while True:
        try:
            s = socket.socket()
            s.connect(('127.0.0.1', 5000))
        except socket.error as e:
            time.sleep(0.5)
        else:
            break
        finally:
            s.close()

def get(rock):
    return requests.get(SERVER_MOCK + '/' + rock,
                        auth=HTTPBasicAuth(USER, PASSWORD),
                        allow_redirects=False)


def put(rock, filename, binary=False):
    file = BytesIO(rock) if binary else StringIO(rock)
    file.name = filename
    return requests.put(SERVER_MOCK,
                        files={'rockspec': file},
                        auth=HTTPBasicAuth(USER, PASSWORD))


def put_empty():
    return requests.put(SERVER_MOCK,
                        auth=HTTPBasicAuth(USER, PASSWORD))


def test_get(app):
    response = get('')

    assert response.status_code == 301
    assert response.url == SERVER_MOCK + "/"

    response = get('manifest')

    assert response.status_code == 302
    assert response.url == SERVER_MOCK + "/manifest"
    assert response.is_redirect is True
    assert response.headers.get('Location') == 'https://hb.bizmrd.ru/tarantool/manifest'

    response = get('manifest-5.1')

    assert response.status_code == 302
    assert response.url == SERVER_MOCK + "/manifest-5.1"
    assert response.is_redirect is True
    assert response.headers.get('Location') == 'https://hb.bizmrd.ru/tarantool/manifest'

    response = get('fiz-buzz-scm-3.rockspec')

    assert response.status_code == 302
    assert response.url == SERVER_MOCK + "/fiz-buzz-scm-3.rockspec"
    assert response.is_redirect is True
    assert response.headers.get('Location') == 'https://hb.bizmrd.ru/tarantool/fiz-buzz-scm-3.rockspec'


def test_put(app):
    rockspec = """\
        package = 'fizz-buzz'
        version = 'scm-1'
    """

    response = put(rockspec, 'fizz-buzz-scm-1.rockspec')
    answer = json.loads(response.content)
    assert response.status_code == 201
    assert answer.get('message') == 'rock entry was successfully added to manifest'
    assert list(S3Mock.instance.files.keys()) == ['manifest', 'fizz-buzz-scm-1.rockspec']
    assert S3Mock.instance.files['fizz-buzz-scm-1.rockspec'].decode('utf-8') == rockspec
    assert S3Mock.instance.files['manifest'].decode('utf-8') == dedent("""\
            commands = {}
            modules = {}
            repository = {
                ["fizz-buzz"] = {
                    ["scm-1"] = {
                        {
                            arch = "rockspec"
                        }
                    }
                }
            }
        """)

    response = put(rockspec, 'fizz-buzz-scm-1.rockspec')
    answer = json.loads(response.content)
    assert response.status_code == 201
    assert answer.get('message') == 'rock entry was successfully added to manifest'

    response = put(rockspec, 'fiz-buzz-scm-3.rockspec')
    answer = json.loads(response.content)
    assert response.status_code == 400
    assert answer.get('message') == 'rockspec name does not match package or version'
    assert list(S3Mock.instance.files.keys()) == ['manifest', 'fizz-buzz-scm-1.rockspec']

    rock_binary = b'fizz-buzz-1.0.1-1.zip'

    response = put(rock_binary, 'fizz-buzz-1.0.1-1.all.rock', binary=True)
    answer = json.loads(response.content)
    assert response.status_code == 201
    assert answer.get('message') == 'rock entry was successfully added to manifest'
    assert list(S3Mock.instance.files.keys()) == ['manifest',
        'fizz-buzz-scm-1.rockspec', 'fizz-buzz-1.0.1-1.all.rock']

    response = put(rock_binary, 'fizz-buzz-1.0.1-1.all.rock', binary=True)
    answer = json.loads(response.content)
    assert response.status_code == 400
    assert answer.get('message') == 'the rock already exists'

    response = put_empty()
    answer = json.loads(response.content)
    assert response.status_code == 400
    assert answer.get('message') == 'package file was not found in request data'
    assert list(S3Mock.instance.files.keys()) == ['manifest',
        'fizz-buzz-scm-1.rockspec', 'fizz-buzz-1.0.1-1.all.rock']

    response = put(rock_binary, 'fizz-buzz-1.0.1-1.x86.rock', binary=True)
    answer = json.loads(response.content)
    assert response.status_code == 400
    assert answer.get('message') == 'File with name fizz-buzz-1.0.1-1.x86.rock is not supported. Rocks server can ' \
                                    'serve .rockspec, .src.rock and .all.rock files only'


def test_brake_manifest(app):
    rockspec = """\
        package = 'fizz-buzz'
        version = '1.13.666-1'
    """

    # The mock simulates fizz-buzz-1.13.666-1.rockspec
    # was not added in the manifest properly. The patch_manifest_func
    # returns an empty manifest. Testcase checks if the manifest is
    # not being updated when patch_manifest_func returns an empty output.
    response = put(rockspec, 'fizz-buzz-1.13.666-1.rockspec')
    answer = json.loads(response.content)
    assert response.status_code == 400
    assert answer.get('message') == None
    assert list(S3Mock.instance.files.keys()) == ['manifest']
    assert S3Mock.instance.files['manifest'].decode('utf-8') == dedent("""\
            commands = {}
            modules = {}
            repository = {}
        """)
