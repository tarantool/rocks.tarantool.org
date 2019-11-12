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
from requests.auth import HTTPBasicAuth

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
logging.basicConfig(format='%(name)s > %(message)s', level=logging.INFO)


def random_string(length=10):
    letters = string.ascii_letters
    return ''.join([random.choice(letters) for _ in range(length)])


USER = random_string()
PASSWORD = random_string()
SERVER_MOCK = 'http://0.0.0.0:5000'


class S3Mock:
    instance = None
    def __init__(self, *args, **kwargs):
        if S3Mock.instance == None:
            S3Mock.instance = self
            self.files = {
                'manifest': dedent("""\
                    commands = {}
                    modules = {}
                    repository = {}
                """).encode('utf-8')
            }
        else:
            self.files = S3Mock.instance.files

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        key = Params.get('Key')
        if key == '/':
            key = ''

        return 'https://hb.bizmrd.ru/tarantool/%s' % key

    def get_object(self, Bucket, Key):
        return {
            'ResponseMetadata': {'HTTPHeaders': ['content-type']}
        }

    def download_fileobj(self, Bucket, Key, Bytes):
        Bytes.write(self.files[Key])

    def upload_fileobj(self, Data, Bucket, Key):
        logging.info('PUT %s' % Key)
        self.files[Key] = Data.read()
        pass

    def delete_object(self, Bucket, Key):
        logging.info('DELETE %s' % Key)
        del self.files[Key]
        pass


@pytest.fixture
def app(monkeypatch):
    import app
    S3Mock.instance = None
    monkeypatch.setattr(app.boto3, 'client', S3Mock)
    monkeypatch.setattr(app, 'USER', USER)
    monkeypatch.setattr(app, 'PASSWORD', PASSWORD)

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


def delete(rock):
    return requests.delete(SERVER_MOCK,
                           json={'file_name': rock},
                           auth=HTTPBasicAuth(USER, PASSWORD))


def delete_non_json(rock):
    return requests.delete(SERVER_MOCK,
                           data={'file_name': rock},
                           auth=HTTPBasicAuth(USER, PASSWORD))


def delete_empty():
    return requests.delete(SERVER_MOCK,
                           headers={"Content-type": "application/json"},
                           auth=HTTPBasicAuth(USER, PASSWORD))


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

    response = put_empty()
    answer = json.loads(response.content)
    assert response.status_code == 400
    assert answer.get('message') == 'package file was not found in request data'
    assert list(S3Mock.instance.files.keys()) == ['manifest',
        'fizz-buzz-scm-1.rockspec', 'fizz-buzz-1.0.1-1.all.rock']


def test_delete(app):
    response = put(b'', 'cartridge-6.6.6-1.src.rock', binary=True)
    response = put(b'', 'cartridge-6.6.6-2.src.rock', binary=True)
    assert list(S3Mock.instance.files.keys()) == ['manifest',
        'cartridge-6.6.6-1.src.rock', 'cartridge-6.6.6-2.src.rock']

    response = delete('cartridge-6.6.6-1.src.rock')

    answer = json.loads(response.content.decode('utf-8'))
    assert answer['message'] == "rock was successfully removed from manifest"
    assert response.status_code == 201
    assert list(S3Mock.instance.files.keys()) == ['manifest',
        'cartridge-6.6.6-2.src.rock']

    response = delete('cartridge-6.6.6-0.src.rock')

    answer = json.loads(response.content.decode('utf-8'))
    assert answer['message'] == "rock version was not found in manifest"
    assert response.status_code == 400
    assert list(S3Mock.instance.files.keys()) == ['manifest',
        'cartridge-6.6.6-2.src.rock']

    response = delete_empty()
    answer = json.loads(response.content.decode('utf-8'))
    assert answer['message'] == 'could not decode json form request'
    assert response.status_code == 400

    response = delete_non_json('cartridge-6.6.6-1.src.rock')
    answer = json.loads(response.content.decode('utf-8'))
    assert answer['message'] == 'Rocks server supports application/json only'
    assert response.status_code == 400
