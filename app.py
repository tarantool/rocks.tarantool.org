import os
from io import BytesIO

import boto3
import botocore
from flask import Flask, redirect, abort, request, jsonify
from flask.views import MethodView
from flask_httpauth import HTTPBasicAuth
from lupa import LuaRuntime
from werkzeug.utils import cached_property

app = Flask(__name__)
auth = HTTPBasicAuth()

S3_URL = os.environ.get("S3_URL")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_REGION = os.environ.get("S3_REGION")
ROCKS_UPLOAD_BUCKET = os.environ.get("ROCKS_UPLOAD_BUCKET")
USER = os.environ.get("USER")
PASSWORD = os.environ.get("PASSWORD")
PORT = os.environ.get("PORT", 5000)

MANIFEST_SCRIPT = 'make_manifest.lua'


class Error(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.errorhandler(Error)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def response_message(message):
    response = jsonify({'message': message})
    response.status_code = 201
    return response


@auth.verify_password
def verify_password(user, password):
    return USER == user and PASSWORD == password


def patch_manifest(manifest: str, rockspec: str, action: str = 'add') -> tuple:
    lua = LuaRuntime(unpack_returned_tuples=True)

    with open(MANIFEST_SCRIPT, 'r') as file:
        patch_manifest_script = file.read()

    patch_manifest_func = lua.eval(patch_manifest_script)

    msg, man = patch_manifest_func(manifest, rockspec, action)

    if not man:
        Error('manifest patch error')

    return msg, man


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
                'Key': filename,
            },
            ExpiresIn=self.expires_in
        )

    def process_manifest(self, action):
        manifest = self.download_manifest()
        rockspec_file = request.files.get('rockspec')

        if not rockspec_file:
            raise Error('.rockspec file was not found in request data')

        rockspec = rockspec_file.read()
        rockspec_name = rockspec_file.filename

        if action == 'add':
            self.client.upload_fileobj(rockspec_file, self.bucket, rockspec_name)
        elif action == 'remove':
            if not self.object_exists(rockspec_name):
                raise Error('rockspec {} does not exist'.format(rockspec_name))
            self.client.delete_object(
                Bucket=self.bucket,
                Key=rockspec_name
            )

        message, patched_manifest = patch_manifest(manifest, str(rockspec), action)

        self.client.upload_fileobj(BytesIO(str.encode(patched_manifest)), self.bucket, 'manifest')

        return response_message(message)

    @auth.login_required
    def put(self):
        return self.process_manifest('add')

    @auth.login_required
    def delete(self):
        return self.process_manifest('remove')

    def get(self, path='/'):

        if not self.client:
            return 'Server config does not exist'

        path = path.strip('/')

        if self.object_exists(path):
            url = self.presign_get(path)
            return redirect(url)

        abort(404)

    def object_exists(self, filename):
        if filename == '':
            return False

        try:
            obj = self.client.get_object(
                Bucket=self.bucket,
                Key=filename
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
            raise Error('manifest file was not found in the bucket')
        manifest_io = BytesIO()
        self.client.download_fileobj(self.bucket, 'manifest', manifest_io)

        return manifest_io.getvalue().decode('utf-8')


s3_view = S3View.as_view('s3_view')
app.add_url_rule('/<path>', view_func=s3_view, methods=['GET'])
app.add_url_rule('/', view_func=s3_view, methods=['GET', 'PUT', 'DELETE'])

if __name__ == '__main__':
    if all((
            S3_URL,
            S3_ACCESS_KEY,
            S3_SECRET_KEY,
            S3_REGION,
            ROCKS_UPLOAD_BUCKET,
            USER,
            PASSWORD,
    )):
        app.run(port=PORT)
