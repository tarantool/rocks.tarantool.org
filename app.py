import json
import os
import re
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
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_REGION = os.environ.get("S3_REGION")
ROCKS_UPLOAD_BUCKET = os.environ.get("ROCKS_UPLOAD_BUCKET")
USER = os.environ.get("USER")
PASSWORD = os.environ.get("PASSWORD")
PORT = os.environ.get("PORT", 5000)
TARANTOOL_IO_REDIRECT_URL = "https://www.tarantool.io/en/download/rocks"

MANIFEST_SCRIPT = 'make_manifest.lua'

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


def patch_manifest(manifest: str, filename: str, rock_content: str = '', action: str = 'add') -> tuple:
    lua = LuaRuntime(unpack_returned_tuples=True)

    with open(MANIFEST_SCRIPT, 'r') as file:
        patch_manifest_script = file.read()

    patch_manifest_func = lua.eval(patch_manifest_script)

    msg, manifest = patch_manifest_func(manifest, filename, rock_content, action)

    if not manifest:
        raise InvalidUsage(msg)

    return msg, manifest


def file_name_is_valid(name):
    pattern = re.compile(r'.*(.rockspec|.src.rock|.all.rock)$')
    if pattern.match(name):
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
            raise InvalidUsage('package file was not found in request data')

        file_name = file.filename
        error = file_name_is_valid(file_name)
        if error:
            raise InvalidUsage(error)

        is_text = istextfile(file)
        file.seek(0)

        package = file.read()
        rockspec = package if is_text else ''

        message, patched_manifest = patch_manifest(manifest, file_name,
                                                   rock_content=rockspec, action='add')

        self.client.upload_fileobj(BytesIO(package), self.bucket, f'{S3_ROCKS_FOLDER}{file_name}')

        self.client.upload_fileobj(BytesIO(str.encode(patched_manifest)), self.bucket, f'{S3_ROCKS_FOLDER}manifest')

        return response_message(message)

    @auth.login_required
    def delete(self):
        manifest = self.download_manifest()

        if not request.content_type == 'application/json':
            return response_message('Rocks server supports application/json only', 400)

        try:
            payload = json.loads(request.data.decode('utf-8'))
        except json.JSONDecodeError:
            return response_message("could not decode json form request", 400)

        file_name = payload.get('file_name')

        if not file_name:
            return response_message('file_name to delete was not found', 400)

        message, patched_manifest = patch_manifest(manifest, file_name, '', 'remove')

        if not self.object_exists(file_name):
            self.client.upload_fileobj(BytesIO(str.encode(patched_manifest)), self.bucket, f'{S3_ROCKS_FOLDER}manifest')
            raise InvalidUsage('rockspec {} does not exist'.format(file_name))
        self.client.delete_object(
            Bucket=self.bucket,
            Key=f'{S3_ROCKS_FOLDER}{file_name}'
        )

        self.client.upload_fileobj(BytesIO(str.encode(patched_manifest)), self.bucket, f'{S3_ROCKS_FOLDER}manifest')

        return response_message(message)

    def get(self, path='/'):

        if path == '/':
            return redirect(TARANTOOL_IO_REDIRECT_URL, code=301)

        if not self.client:
            return 'Server config does not exist'

        path = path.strip('/')

        url = self.presign_get(path)
        return redirect(url)

    def object_exists(self, filename):
        if filename == '':
            return False

        try:
            obj = self.client.get_object(
                Bucket=self.bucket,
                Key=f'{S3_ROCKS_FOLDER}{filename}'
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


s3_view = S3View.as_view('s3_view')
app.add_url_rule('/<path>', view_func=s3_view, methods=['GET'])
app.add_url_rule('/', view_func=s3_view, methods=['GET', 'PUT', 'DELETE'])

if __name__ == '__main__':
    app.run(port=PORT)
