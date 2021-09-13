import logging
import os.path
import re
import sys
from textwrap import dedent

import botocore as botocore
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import patch_manifest_func

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

        content_disposition = Params.get('ResponseContentDisposition')
        if content_disposition:
            key = re.match(r'.*=?\s(.*)', content_disposition).groups()[0]

        return 'https://hb.bizmrd.ru/tarantool/%s' % key

    def get_object(self, Bucket, Key):
        if Key in self.files:
            return {
                'ResponseMetadata': {'HTTPHeaders': ['content-type']}
            }
        else:
            raise botocore.exceptions.ClientError(
                error_response={'Error': {'Code': 'NoSuchKey'}},
                operation_name=None
            )

    def download_fileobj(self, Bucket, Key, Bytes):
        Bytes.write(self.files[Key])

    def upload_fileobj(self, Data, Bucket, Key):
        logging.info('PUT %s' % Key)
        self.files[Key] = Data.read()

    def delete_object(self, Bucket, Key):
        logging.info('DELETE %s' % Key)
        del self.files[Key]


def patch_manifest_func_mock(*args, **kwargs):
    if args[1] == 'fizz-buzz-1.13.666-1.rockspec':
        # return an empty manifest to raise an error
        return 'Some unexpected error', None
    return patch_manifest_func(*args, **kwargs)
