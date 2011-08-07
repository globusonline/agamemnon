import json
from pycassa import system_manager
import pycassa
from pycassa.batch import Mutator
from pycassa.cassandra.ttypes import NotFoundException
from agamemnon.graph_constants import OUTBOUND_RELATIONSHIP_CF, INBOUND_RELATIONSHIP_CF, RELATIONSHIP_INDEX
import pycassa.columnfamily as cf

class CassandraDataStore(object):
    def __init__(self, keyspace, pool, system_manager):
        self._cf_cache = {}
        self._index_cache = {}
        self._system_manager = system_manager
        self._pool = pool
        self._keyspace = keyspace
        self._batch = None
        self.in_batch = False
        self.batch_count = 0
        if not self.cf_exists(OUTBOUND_RELATIONSHIP_CF):
            self.create_cf(OUTBOUND_RELATIONSHIP_CF, super=True)
        if not self.cf_exists(INBOUND_RELATIONSHIP_CF):
            self.create_cf(INBOUND_RELATIONSHIP_CF, super=True)
        if not self.cf_exists(RELATIONSHIP_INDEX):
            self.create_cf(RELATIONSHIP_INDEX, super=True)

    def create_cf(self, type, column_type=system_manager.ASCII_TYPE, super=False, index_columns=list()):
        self._system_manager.create_column_family(self._keyspace, type, super=super, comparator_type=column_type)
        for column in index_columns:
            self._system_manager.create_index(self._keyspace, type, column, column_type,
                                              index_name='%s_%s_index' % (type, column))
        return cf.ColumnFamily(self._pool, type)
    
    def cf_exists(self, type):
        try:
            cf.ColumnFamily(self._pool, type)
        except NotFoundException:
            return False
        return True

    def get_cf(self, type, create=True):

        column_family = None
        try:
            column_family = cf.ColumnFamily(self._pool, type)
            self._cf_cache[type] = column_family
        except NotFoundException:
            if create:
                column_family = self.create_cf(type)
        return column_family



    def insert(self, column_family, key, columns):
        if self._batch is not None:
            self._batch.insert(column_family, key, columns)
        with Mutator(self._pool) as b:
            b.insert(column_family, key, columns)

    def remove(self,column_family, key, columns=None, super_column=None):
        if self._batch is not None:
            self._batch.remove(column_family, key, columns=columns, super_column=super_column)
        else:
            column_family.remove(key, columns=columns, super_column=super_column)

    def start_batch(self):
        if self._batch is None:
            self.in_batch = True
            self._batch = Mutator(self._pool)
        self.batch_count += 1


    def commit_batch(self):
        self.batch_count -= 1
        if not self.batch_count:
            self._batch.send()
            self._batch = None

def drop_keyspace(host_list, keyspace):
    system_manager = pycassa.SystemManager(json.loads(host_list)[0])
    system_manager.drop_keyspace(keyspace)

def create_keyspace(host_list, keyspace, replication_factor=1):
    system_manager = pycassa.SystemManager(json.loads(host_list)[0])
    system_manager.create_keyspace(keyspace, replication_factor=replication_factor)
