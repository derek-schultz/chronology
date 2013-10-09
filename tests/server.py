import json
import unittest

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

from kronos.server import wsgi_application

VERSION = 1.0
BASE_PATH = '/%s/events' % VERSION


class KronosServerTestCase(unittest.TestCase):
  """ Wrapper `TestCase` class which be used by all server tests because it
  provides a clean API to Kronos and performs all necessary clean up logic.
  """

  def setUp(self):
    self.http_client = Client(wsgi_application, BaseResponse)
    self.get_path = '%s/get' % BASE_PATH
    self.put_path = '%s/put' % BASE_PATH
    self.delete_path = '%s/delete' % BASE_PATH
    self.streams_path = '/%s/streams' % VERSION

  def put(self, stream_or_mapping, events=None):
    if isinstance(stream_or_mapping, dict):
      data = json.dumps(stream_or_mapping)
    else:
      self.assertTrue(events is not None)
      data = json.dumps({stream_or_mapping: events})
    response = self.http_client.post(path=self.put_path,
                                     data=data,
                                     buffered=True)
    self.assertEqual(response.status_code, 200)
    return json.loads(response.data)

  def get(self, stream, start_time, end_time, start_id=None, limit=None,
          order=None):
    data = {'stream': stream, 'end_time': end_time}
    if start_id:
      data['start_id'] = start_id
    else:
      data['start_time'] = start_time
    if limit is not None:
      data['limit'] = limit
    if order is not None:
      data['order'] = order
    response = self.http_client.post(path=self.get_path,
                                     data=json.dumps(data),
                                     buffered=True)
    self.assertEqual(response.status_code, 200)
    return map(json.loads, response.data.splitlines())

  def delete(self, stream, start_time, end_time, start_id=None):
    data = {'stream': stream, 'end_time': end_time}
    if start_id:
      data['start_id'] = start_id
    else:
      data['start_time'] = start_time
    response = self.http_client.post(path=self.delete_path,
                                     data=json.dumps(data),
                                     buffered=True)
    self.assertEqual(response.status_code, 200)
    return json.loads(response.data)
    
  def get_streams(self):
    response = self.http_client.get(self.streams_path,
                                    buffered=True)
    self.assertEqual(response.status_code, 200)
    return dict(map(json.loads, response.data.splitlines()))