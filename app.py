import os
from io import BytesIO

import boto3
import botocore
from flask import Flask, redirect, abort, request
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


@auth.verify_password
def verify_password(user, password):
    return USER == user and PASSWORD == password


def patch_manifest(manifest: str, rockspec: str, action: str = 'add') -> tuple:
    lua = LuaRuntime(unpack_returned_tuples=True)

    with open(MANIFEST_SCRIPT, 'r') as file:
        patch_manifest_script = file.read()

    patch_manifest_func = lua.eval(patch_manifest_script)

    return patch_manifest_func(manifest, rockspec, action)


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

        rockspec = rockspec_file.read()
        rockspec_name = rockspec_file.filename

        message, patched_manifest = patch_manifest(manifest, str(rockspec), action)

        self.client.upload_fileobj(BytesIO(str.encode(patched_manifest)), self.bucket, 'manifest')

        if action == 'add':
            self.client.upload_fileobj(rockspec_file, self.bucket, rockspec_name)
        elif action == 'remove':
            self.client.delete_object(
                Bucket=self.bucket,
                Key=rockspec_name
            )

        return message

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
