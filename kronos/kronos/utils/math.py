from __future__ import absolute_import

import binascii

from datetime import datetime
from dateutil.tz import tzutc
from uuid import UUID
from uuid import uuid4

from kronos.utils.uuid import TimeUUID
from kronos.utils.uuid import UUIDType


# Kronos time is the number of 100ns intervals since the UTC epoch.

def time_to_kronos_time(time):
  """
  Takes a unix timestamp or a datetime object and returns a Kronos timestamp.
  """
  if isinstance(time, datetime):
    time = (time.replace(tzinfo=tzutc()) -
            datetime.utcfromtimestamp(0)).total_seconds()
  return int(float(time) * 1e7)

def kronos_time_to_datetime(time, round_up=False):
  time = int(time / 1e7)
  if round_up:
    time += 1
  return datetime.utcfromtimestamp(time)

def kronos_time_to_time(kronos_time):
  return float(kronos_time) / 1e7

def uuid_to_kronos_time(uuid):
  """
  UUIDs contain a time field. Convert it to kronos time and return.
  """
  if not isinstance(uuid, UUID):
    raise Exception("Expected type UUID")
  return uuid.time - 0x01b21dd213814000L

uuid_to_time = lambda _id: kronos_time_to_time(uuid_to_kronos_time(_id))

def uuid_from_kronos_time(time, _type=UUIDType.RANDOM):
  """
  Generate a UUID with the specified time.
  If `lowest` is true, return the lexicographically first UUID for the specified
  time.
  """
  # Bit-flipping logic from uuid1 implementation described in:
  # http://stackoverflow.com/questions/7153844/uuid1-from-utc-timestamp-in-python
  # except we use a random UUID to seed the clock sequence to minimize the
  # probability of two calls to this function with the same time getting the
  # same ID.
  timestamp = int(time) + 0x01b21dd213814000L
  time_low = timestamp & 0xffffffffL
  time_mid = (timestamp >> 32L) & 0xffffL
  time_hi_version = (timestamp >> 48L) & 0x0fffL
  if _type == UUIDType.LOWEST:
    clock_seq_low = 0 & 0xffL
    clock_seq_hi_variant = 0 & 0x3fL
    node = 0 & 0xffffffffffffL
  elif _type == UUIDType.HIGHEST:
    clock_seq_low = 0xffL
    clock_seq_hi_variant = 0x3fL
    node = 0xffffffffffffL
  else:
    randomuuid = uuid4()
    clock_seq_low = randomuuid.clock_seq_low
    clock_seq_hi_variant = randomuuid.clock_seq_hi_variant
    node = randomuuid.node
  return TimeUUID(fields=(time_low,
                          time_mid,
                          time_hi_version,
                          clock_seq_hi_variant,
                          clock_seq_low,
                          node))

uuid_from_time =  lambda time, _type=UUIDType.RANDOM: uuid_from_kronos_time(
  time_to_kronos_time(time), _type)

def round_down(value, base):
  """
  Round `value` down to the nearest multiple of `base`.
  Expects `value` and `base` to be non-negative.
  """
  return int(value - (value % base))

def bytearray_to_hex(_bytearray):
  return binascii.hexlify(_bytearray)

def hex_to_bytearray(_hex):
  return bytearray(_hex.decode('hex'))
