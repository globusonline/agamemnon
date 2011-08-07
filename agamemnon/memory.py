import operator
from ordereddict import OrderedDict
from pycassa.cassandra.ttypes import NotFoundException
from agamemnon.graph_constants import ASCII
import logging

log = logging.getLogger()

class InMemoryDataStore(object):
    def __init__(self):
        self.tables = {}
        self.transactions = {}
        self.batch_count = 0
        self.in_batch = False

    def get_cf(self, cf_name):
        if not cf_name in self.tables:
            self.tables[cf_name] = self.create_cf(cf_name)
        return self.tables[cf_name]

    def create_cf(self, type, column_type=ASCII, super=False, index_columns=list()):
        self.tables[type] = ColumnFamily(type, column_type)
        return self.tables[type]

    def cf_exists(self, type):
        return type in self.tables.keys()

    def insert(self, cf, row, columns):
        def execute():
            cf.insert(row, columns)

        if self.in_batch:
            self.transactions[('insert', cf.name, row, tuple(columns.keys()))] = execute
        else:
            execute()

    def remove(self, cf, row, columns=None, super_column=None):
        def execute():
            cf.remove(row, columns=columns, super_column=super_column)
            
        if self.in_batch:
            if columns is not None and super_column is not None\
            and not ('remove', cf.name, row, super_column) in self.transactions.keys():
                key = ('remove', cf.name, row, tuple(columns), super_column)
            elif columns is not None and not ('remove', cf.name, row) in self.transactions.keys():
                key = ('remove', cf.name, row, tuple(columns))
            elif super_column is not None:
                key = ('remove', cf.name, row, super_column)
            else:
                key = ('remove', cf.name, row)
            if not key in self.transactions.keys() and not ('remove', cf.name, row) in self.transactions.keys():
                self.transactions[key] = execute
        else:
            execute()

    def start_batch(self):
        self.in_batch = True
        self.batch_count += 1

    def commit_batch(self):
        self.batch_count -= 1
        if not self.batch_count:
            for key, value in self.transactions.items():
                value()
            self.transactions.clear()
            self.in_batch = False


class ColumnFamily(object):
    def __init__(self, name, sort, super=False):
        self.data = OrderedDict()
        self.sort = sort
        self.name = name
        self.super = super

    def get(self, row, columns=None, column_start=None, super_column=None, column_finish=None, column_count=100):
        try:
            if columns is None and column_start is None and super_column is None:
                results = self.data[row]
            else:
                if super_column is None:
                    data_columns = self.data[row]
                else:
                    data_columns = self.data[row][super_column]
                results = {}
                count = 0
                if columns is not None:
                    for c in columns:
                        results[c] = data_columns[c]
                else:
                    for c in data_columns.keys():
                        count += 1
                        if count > column_count:
                            break
                        if column_start is not None and column_finish is not None:
                            if ((cmp(c, column_start) > 0
                                and cmp(c, column_finish) < 0)
                                or cmp(c, column_finish) == 0
                                or cmp(c, column_start) == 0):

                                results[c] = data_columns[c]
                        else:
                            results[c] = data_columns[c]
            if not len(results):
                raise NotFoundException
            for key, value in results.items():
                if isinstance(value, dict) and len(value) == 0:
                    del(results[key])
                if value is None:
                    del(results[key])
            return results
        except KeyError:
            raise NotFoundException

    def insert(self, row, columns, ttl=None):
        if not row in self.data:
            self.data[row] = OrderedDict()
        if self.sort == ASCII:
            sorted_columns = sorted(columns.iteritems(), key=operator.itemgetter(0))
            for column in sorted_columns:
                self.data[row][column[0]] = column[1]

                #        if ttl is not None:
                #            def delete():
                #                for c in columns.keys():
                #                    del(self.data[row][c])
                #            Timer(ttl, delete, ()).start()

    def remove(self, row, columns=None, super_column=None):
        try:
            if columns is None and super_column is None:
                row_data = self.data[row]
                for key, value in row_data.items():
                    if isinstance(value, OrderedDict):
                        value.clear()
                    else:
                        del(row_data[key])
            elif columns is not None and super_column is None:
                row_data = self.data[row]
                for c in columns:
                    if c in row_data:
                        value = row_data[c]
                        if isinstance(value, OrderedDict):
                            value.clear()
                        else:
                            del(row_data[c])
            elif columns is None and super_column is not None:
                for key, value in self.data[row][super_column].items():
                    if isinstance(value, dict):
                        value.clear()
                    else:
                        del(self.data[row][super_column][key])
            else:
                sc = self.data[row][super_column]
                for c in columns:
                    if c in sc:
                        del(sc[c])
        except KeyError:
            raise NotFoundException

    def get_indexed_slices(self, index_clause):
        expression = index_clause.expressions[0]
        column_name = expression.column_name
        value = expression.value
        for i in self.data.items():
            if i[1][column_name] == value:
                yield i[0], i[1]
  