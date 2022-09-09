import hashlib
import io
import json
import os
import re
from datetime import datetime
from io import BytesIO

import boto3
import botocore
from flask import Flask, redirect, request, jsonify
from flask.views import MethodView
from flask_httpauth import HTTPBasicAuth
from lupa import LuaRuntime
from werkzeug.utils import cached_property

app = Flask(__name__)
auth = HTTPBasicAuth()

S3_URL = os.environ.get("S3_URL")
S3_ROCKS_FOLDER = os.environ.get("S3_ROCKS_FOLDER", '')
S3_AUDIT_FOLDER = os.environ.get("S3_AUDIT_FOLDER", S3_ROCKS_FOLDER)
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_REGION = os.environ.get("S3_REGION")
ROCKS_UPLOAD_BUCKET = os.environ.get("ROCKS_UPLOAD_BUCKET")
USER = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")
PORT = os.environ.get("PORT", 5000)
TARANTOOL_IO_REDIRECT_URL = "https://www.tarantool.io/en/download/rocks"
MANIFEST_TARGETS = ['manifest-5.1']
MANIFEST = 'manifest'

MANIFEST_SCRIPT = 'make_manifest.lua'

supported_files_pattern = re.compile(r'.*(.rockspec|.src.rock|.all.rock)$')


def md5(f_obj):
    hash_md5 = hashlib.md5()
    f_obj.seek(0)
    for chunk in iter(lambda: f_obj.read(4096), b""):
        hash_md5.update(chunk)
    f_obj.seek(0)
    return hash_md5.hexdigest()


def int2byte(x):
    return bytes((x,))


_text_characters = (
        b''.join(bytes((i,)) for i in range(32, 127)) +
        b'\n\r\t\f\b')


def istextfile(fileobj, blocksize=512):
    """ Uses heuristics to guess whether the given file is text or binary,
        by reading a single block of bytes from the file.
        If more than 30% of the chars in the block are non-text, or there
        are NUL ('\x00') bytes in the block, assume this is a binary file.
    """
    block = fileobj.read(blocksize)
    if b'\x00' in block:
        # Files with null bytes are binary
        return False
    elif not block:
        # An empty file is considered a valid text file
        return True

    # Use translate's 'deletechars' argument to efficiently remove all
    # occurrences of _text_characters from the block
    nontext = block.translate(None, _text_characters)
    return float(len(nontext)) / len(block) <= 0.30


class InvalidUsage(RuntimeError):
    status_code = 400

    def __init__(self, message, status_code=None):
        RuntimeError.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self):
        rv = {'message': self.message}
        return rv

    def __str__(self):
        return self.message


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def response_message(message, status=201):
    response = jsonify({'message': message})
    response.status_code = status
    return response


@auth.verify_password
def verify_password(user, password):
    return USER == user and PASSWORD == password


lua = LuaRuntime(unpack_returned_tuples=True)

with open(MANIFEST_SCRIPT, 'r') as file:
    patch_manifest_script = file.read()

patch_manifest_func = lua.eval(patch_manifest_script)


def patch_manifest(manifest: str, filename: str, rock_content: str = '', action: str = 'add') -> tuple:
    return patch_manifest_func(manifest, filename, rock_content, action)


def file_name_is_valid(name):
    if supported_files_pattern.match(name):
        error = None
    else:
        error = f'File with name {name} is not supported. Rocks ' \
                f'server can serve .rockspec, .src.rock and .all.rock' \
                f' files only'
    return error


class S3View(MethodView):
    bucket = ROCKS_UPLOAD_BUCKET
    expires_in = 24 * 60 * 60

    @cached_property
    def client(self):
        return boto3.client(
            's3',
            endpoint_url=S3_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION
        )

    def presign_get(self, filename):
        return self.client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': self.bucket,
                'Key': f'{S3_ROCKS_FOLDER}{filename}',
            },
            ExpiresIn=self.expires_in
        )

    @auth.login_required
    def put(self):
        manifest = self.download_manifest()
        file = request.files.get('rockspec')

        if not file:
            msg = 'package file was not found in request data'
            self.audit_log(msg)
            raise InvalidUsage(msg)

        file_name = file.filename
        error = file_name_is_valid(file_name)
        if error:
            self.audit_log(error)
            raise InvalidUsage(error)

        is_text = istextfile(file)
        file.seek(0)

        package = file.read()
        rockspec = package if is_text else ''

        message, patched_manifest = patch_manifest(manifest, file_name,
                                                   rock_content=rockspec, action='add')

        if patched_manifest:
            self.upload_fileobj(BytesIO(package), file_name,
                                f'put {file_name} - {message}')
            self.upload_fileobj(BytesIO(str.encode(patched_manifest)),
                                'manifest', 'update manifest')
        else:
            self.audit_log(f'manifest update error: {message}')
            raise InvalidUsage(message)

        return response_message(message)

    def upload_fileobj(self, file_obj, file_path, message):
        err = None
        md5_hash = md5(file_obj)
        try:
            self.client.upload_fileobj(file_obj, self.bucket, f'{S3_ROCKS_FOLDER}{file_path}')
        except Exception as e:
            err = str(e)
        self.audit_log(f'Upload failure: {err} {message}' if err else message, md5_hash)

    def get(self, path='/'):
        if path == '/':
            return redirect(TARANTOOL_IO_REDIRECT_URL, code=301)

        if not self.client:
            return 'Server config does not exist'

        path = path.strip('/')

        if path in MANIFEST_TARGETS:
            path = MANIFEST

        url = self.presign_get(path)
        return redirect(url)

    def object_exists(self, filename, folder=None):
        if filename == '':
            return False

        if folder is None:
            folder = S3_ROCKS_FOLDER

        try:
            obj = self.client.get_object(
                Bucket=self.bucket,
                Key=f'{folder}{filename}'
            )
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'NoSuchKey':
                return False
            else:
                raise ex

        headers = obj['ResponseMetadata']['HTTPHeaders']

        if 'content-type' not in headers:
            return False

        return True

    def download_manifest(self):
        if not self.object_exists('manifest'):
            raise InvalidUsage('manifest file was not found in the bucket')
        manifest_io = BytesIO()
        self.client.download_fileobj(self.bucket, f'{S3_ROCKS_FOLDER}manifest', manifest_io)

        return manifest_io.getvalue().decode('utf-8')

    def audit_log(self, event: str, md5_hash=''):
        if md5_hash:
            md5_hash = f' md5hash: {md5_hash} |'
        log_data = f'{datetime.now()} | {event} |{md5_hash} ' \
                   f'{request.remote_addr} | {json.dumps(dict(request.headers))}\n'

        audit_file_name = f'{datetime.today().strftime("%y-%m")}.log'
        audit_file = BytesIO()

        exists = self.object_exists(audit_file_name, S3_AUDIT_FOLDER)
        if exists:
            self.client.download_fileobj(self.bucket, f'{S3_AUDIT_FOLDER}{audit_file_name}', audit_file)

        initial_size = audit_file.getbuffer().nbytes

        audit_file.seek(0, io.SEEK_END)
        audit_file.write(log_data.encode())
        audit_file.seek(0)

        if not exists or (exists and audit_file.getbuffer().nbytes > initial_size):
            self.client.upload_fileobj(audit_file, self.bucket, f'{S3_AUDIT_FOLDER}{audit_file_name}')


s3_view = S3View.as_view('s3_view')
app.add_url_rule('/<path>', view_func=s3_view, methods=['GET'])
app.add_url_rule('/', view_func=s3_view, methods=['GET', 'PUT'])

if __name__ == '__main__':
    app.run(port=PORT)
