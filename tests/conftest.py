import logging
import re
from textwrap import dedent

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
        return {
            'ResponseMetadata': {'HTTPHeaders': ['content-type']}
        }

    def download_fileobj(self, Bucket, Key, Bytes):
        Bytes.write(self.files[Key])

    def upload_fileobj(self, Data, Bucket, Key):
        logging.info('PUT %s' % Key)
        self.files[Key] = Data.read()

    def delete_object(self, Bucket, Key):
        logging.info('DELETE %s' % Key)
        del self.files[Key]
