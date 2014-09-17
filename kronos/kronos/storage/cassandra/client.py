import atexit
import logging

from cassandra.cluster import Cluster

from kronos.common.time import epoch_time_to_kronos_time
from kronos.conf.constants import ResultOrder
from kronos.storage.base import BaseStorage
from kronos.storage.cassandra.internal import Namespace
from kronos.storage.cassandra.internal import Stream
from kronos.utils.uuid import uuid_from_kronos_time
from kronos.utils.uuid import UUIDType
from kronos.utils.validate import is_list
from kronos.utils.validate import is_non_empty_str
from kronos.utils.validate import is_pos_int

log = logging.getLogger(__name__)

CASSANDRA_PROTOCOL_VERSION = 2  # Change to 1 for Cassandra < 2.0


class CassandraStorageException(Exception):
  pass


class CassandraStorage(BaseStorage):
  SETTINGS_VALIDATORS = {
    'timewidth_seconds':
      lambda x: (is_pos_int(x) and  # noqa
                 epoch_time_to_kronos_time(int(x)) <= Stream.MAX_WIDTH),
    'shards_per_bucket': is_pos_int,
    'hosts': is_list,
    'keyspace_prefix': is_non_empty_str,
    'replication_factor': is_pos_int,
    'read_size': is_pos_int
  }

  def __init__(self, name, namespaces, **settings):
    """
    Check that settings contains all of the required parameters in the right
    format, then setup a connection to the specified Cassandra instance.
    """
    super(CassandraStorage, self).__init__(name, namespaces, **settings)
    self.namespaces = {}
    self.setup_cassandra(namespaces)

  def setup_cassandra(self, namespaces):
    """
    Set up a connection to the specified Cassandra cluster and create the
    specified keyspaces if they dont exist.
    """
    connections_to_shutdown = []
    self.cluster = Cluster(self.hosts)

    for namespace_name in namespaces:
      keyspace = '%s_%s' % (self.keyspace_prefix, namespace_name)
      namespace = Namespace(self.cluster, keyspace,
                            self.replication_factor, self.read_size)
      connections_to_shutdown.append(namespace.session)
      self.namespaces[namespace_name] = namespace

    # Shutdown Cluster instance after shutting down all Sessions.
    connections_to_shutdown.append(self.cluster)

    # Shutdown all connections to Cassandra before exiting Python interpretter.
    atexit.register(lambda: map(lambda c: c.shutdown(),
                                connections_to_shutdown))

  def is_alive(self):
    """
    Is our connection to Cassandra alive?
    """
    return not bool(self.cluster.is_shutdown)

  def get_stream(self, namespace, stream, configuration):
    namespace = self.namespaces[namespace]
    width = epoch_time_to_kronos_time(configuration['timewidth_seconds'])
    return namespace.get_stream(stream, width,
                                int(configuration['shards_per_bucket']))

  def _insert(self, namespace, stream, events, configuration):
    """
    Store the specified events for the named stream.
    `stream` : The name of a stream.
    `events` : A list of events to store for the named stream.
    `configuration` : A dictionary of settings to override any default settings,
                      such as number of shards or width of a time interval.
    """
    stream = self.get_stream(namespace, stream, configuration)
    stream.insert(events)

  def _delete(self, namespace, stream, start_id, end_time, configuration):
    """
    Delete events for `stream` between `start_id` and `end_time`.
    `stream` : The stream to delete events for.
    `start_id` : Delete events with id >= `start_id`.
    `end_time` : Delete events ending <= `end_time`.
    `configuration` : A dictionary of settings to override any default
                      settings, such as number of shards or width of a
                      time interval.
    """
    stream = self.get_stream(namespace, stream, configuration)
    return stream.delete(start_id,
                         uuid_from_kronos_time(end_time,
                                               _type=UUIDType.HIGHEST))

  def _retrieve(self, namespace, stream, start_id, end_time, order, limit,
                configuration):
    """
    Retrieve events for `stream` between `start_id` and `end_time`.
    `stream` : The stream to return events for.
    `start_id` : Return events with id > `start_id`.
    `end_time` : Return events ending <= `end_time`.
    `order` : Whether to return the results in ResultOrder.ASCENDING
              or ResultOrder.DESCENDING time-order.
    `configuration` : A dictionary of settings to override any default
                      settings, such as number of shards or width of a
                      time interval.
    """
    stream = self.get_stream(namespace, stream, configuration)
    events = stream.iterator(start_id,
                             uuid_from_kronos_time(end_time,
                                                   _type=UUIDType.HIGHEST),
                             order == ResultOrder.DESCENDING, limit)
    events = events.__iter__()
    event = events.next()
    # If first event's ID is equal to `start_id`, skip it.
    if event.id != start_id:
      yield event.json
    while True:
      yield events.next().json

  def _streams(self, namespace):
    for stream_name in self.namespaces[namespace].list_streams():
      yield stream_name

  def _clear(self):
    for namespace in self.namespaces.itervalues():
      namespace.drop()
      namespace.create_session()
