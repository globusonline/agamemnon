import json
import logging

import pycassa
from pycassa.batch import Mutator
import pycassa.columnfamily as cf
from pycassa.cassandra.ttypes import NotFoundException, InvalidRequestException, ConsistencyLevel
from thrift.transport.TTransport import TTransportException

from agamemnon.graph_constants import OUTBOUND_RELATIONSHIP_CF, INBOUND_RELATIONSHIP_CF, RELATIONSHIP_INDEX, RELATIONSHIP_CF
from agamemnon.delegate import Delegate
from agamemnon.exceptions import CassandraClusterNotFoundException

log = logging.getLogger(__name__)

class CassandraDataStore(Delegate):
    def __init__(self, 
                 keyspace='agamemnon', 
                 server_list=['localhost:9160'], 
                 replication_factor=1,
                 default_consistency_level=ConsistencyLevel.QUORUM,
                 create_keyspace = False,
                **kwargs):


        super(CassandraDataStore,self).__init__()

        self._keyspace = keyspace
        self._server_list = server_list
        self._replication_factor = replication_factor
        self._consistency_level = default_consistency_level
        self._pool_args = kwargs

        if create_keyspace:
            self.create()
        else:
            self.init_pool()

    def init_pool(self):
        self._pool = pycassa.pool.ConnectionPool(self._keyspace,
                                                 self._server_list,
                                                 self._pool_args)

        self._cf_cache = {}
        self._index_cache = {}
        self._batch = None
        self.in_batch = False
        self.batch_count = 0
        if not self.cf_exists(OUTBOUND_RELATIONSHIP_CF):
            self.create_cf(OUTBOUND_RELATIONSHIP_CF, super=True)
        if not self.cf_exists(INBOUND_RELATIONSHIP_CF):
            self.create_cf(INBOUND_RELATIONSHIP_CF, super=True)
        if not self.cf_exists(RELATIONSHIP_INDEX):
            self.create_cf(RELATIONSHIP_INDEX, super=True)
        if not self.cf_exists(RELATIONSHIP_CF):
            self.create_cf(RELATIONSHIP_CF, super=False)

    @property
    def system_manager(self):
        for server in self._server_list:
            try:
                return pycassa.system_manager.SystemManager(server)
            except TTransportException as e:
                log.warning("Could not connect to Cassandra server {0}".format(server))
        raise CassandraClusterNotFoundException("Could not connect to any Cassandra server in list")

    @property
    def keyspace(self):
        return self._keyspace

    def create(self):
        if self._keyspace not in self.system_manager.list_keyspaces():
            strategy_options = { 'replication_factor': str(self._replication_factor) } 
            self.system_manager.create_keyspace(self._keyspace, 
                                                strategy_options = strategy_options )
        self.init_pool()

    def drop(self):
        self.system_manager.drop_keyspace(self._keyspace)
        self._pool.dispose()
        self._pool = None

    def truncate(self):
        try:
            self.drop()
        except InvalidRequestException:
            pass
        self.create()
        self.init_pool()

    def get_count(self, type, row, columns=None, column_start=None, super_column=None, column_finish=None):
        args = {}
        if columns is not None:
            args['columns'] = columns
        if column_start is not None:
            args['column_start'] = column_start
        if column_finish is not None:
            args['column_finish'] = column_finish
        if super_column is not None:
            args['super_column'] = super_column
        return self.get_cf(type).get_count(row, **args)

    def create_cf(self, type, column_type=pycassa.system_manager.ASCII_TYPE, super=False, index_columns=list()):
        self.system_manager.create_column_family(self._keyspace, type, super=super, comparator_type=column_type)
        for column in index_columns:
            self.create_secondary_index(type, column, column_type)
        return cf.ColumnFamily(self._pool, type, autopack_names=False, autopack_values=False,
                               read_consistency_level=self._consistency_level,
                               write_consistency_level=self._consistency_level)

    def create_secondary_index(self, type, column, column_type=pycassa.system_manager.ASCII_TYPE):
        self.system_manager.create_index(self._keyspace, type, column, column_type,
                                          index_name='%s_%s_index' % (type, column))
    
    def cf_exists(self, type):
        if type in self._cf_cache:
            return True
        try:
            cf.ColumnFamily(self._pool, type, autopack_names=False, autopack_values=False)
        except NotFoundException:
            return False
        return True

    def get_cf(self, type, create=True):

        column_family = None
        if type in self._cf_cache:
            return self._cf_cache[type]
        try:
            column_family = cf.ColumnFamily(self._pool, type, autopack_names=False, autopack_values=False)
            self._cf_cache[type] = column_family
        except NotFoundException:
            if create:
                column_family = self.create_cf(type)
        return column_family



    def insert(self, column_family, key, columns):
        if self._batch is not None:
            self._batch.insert(column_family, key, columns)
        else:
            with Mutator(self._pool) as b:
                b.insert(column_family, key, columns)

    def remove(self,column_family, key, columns=None, super_column=None):
        if self._batch is not None:
            self._batch.remove(column_family, key, columns=columns, super_column=super_column)
        else:
            column_family.remove(key, columns=columns, super_column=super_column)

    def start_batch(self, queue_size = 0):
        if self._batch is None:
            self.in_batch = True
            self._batch = Mutator(self._pool,queue_size)
        self.batch_count += 1


    def commit_batch(self):
        self.batch_count -= 1
        if not self.batch_count:
            self._batch.send()
            self._batch = None

def create_keyspace(host_list, keyspace, **create_options):
    system_manager = pycassa.SystemManager(json.loads(host_list)[0])

    print create_options
    if "strategy_options" not in create_options:
        create_options["strategy_options"] = { 'replication_factor' : '1' }

    system_manager.create_keyspace(keyspace, **create_options)
