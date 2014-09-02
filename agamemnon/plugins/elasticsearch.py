from pyes.es import ES
from pyes import exceptions
from pyes import query
from itertools import groupby
from operator import itemgetter
import logging

# pyes exceptions don't all inherit from a common base class.
ELASTIC_SEARCH_EXCEPTIONS = tuple(exceptions.__dict__[ex] for ex in exceptions.__all__)

log = logging.getLogger(__name__)


class FullTextSearch(object):
    def __init__(self, server, settings=None):
        self.conn = ES(server)
        if settings:
            self.settings = settings
        else:
            self.settings = {
                'index': {
                    'analysis': {
                        'analyzer': {
                            'ngram_analyzer': {
                                'tokenizer': 'keyword',
                                'filter': ['lowercase', 'filter_ngram'],
                                'type': 'custom'
                            }
                        },
                        'filter': {
                            'filter_ngram': {
                                'type': 'nGram',
                                'max_gram': 30,
                                'min_gram': 1
                            }
                        }
                    }
                }
            }
        self.refresh_index_cache()

    def search_index_text(self, query_string, fields="_all", **args):
        q = query.MatchQuery(fields, query_string)
        return self.search_index(q, **args)

    def search_index(self, query, indices=None, num_results=None, node_type=None):
        results = self.conn.search(
            query=query, indices=indices, doc_types=node_type)
        meta_list = [r.get_meta() for r in results[0:num_results]]
        node_dict = {}

        # fetch nodes grouped by type to reduce number of db calls
        key = itemgetter('type')
        for t, grouped_list in groupby(sorted(meta_list, key=key), key=key):
            ids = [meta['id'] for meta in grouped_list]
            for node in self.datastore.get_nodes(t, ids):
                node_dict[(node.type, node.key)] = node

        # return nodes in original order
        nodelist = [node_dict[(meta['type'], meta['id'])]
                    for meta in meta_list]

        return nodelist

    def create_index(self, type, indexed_variables, index_name):
        self.conn.indices.create_index_if_missing(index_name, self.settings)
        mapping = {}
        for arg in indexed_variables:
            mapping[arg] = {'boost': 1.0,
                            'analyzer': 'ngram_analyzer',
                            'type': 'string',
                            'term_vector': 'with_positions_offsets'}
        index_settings = {'index_analyzer': 'ngram_analyzer',
                          'search_analyzer': 'standard',
                          'properties': mapping}
        self.conn.indices.put_mapping(str(type), index_settings, [index_name])
        self.refresh_index_cache()
        self.populate_index(type, index_name)

    def refresh_index_cache(self):
        try:
            indices = self.conn.indices.get_mapping(raw=True)
        except exceptions.IndexMissingException:
            indices = {}
        else:
            indices = dict((k, v.get('mappings', {})) for k, v in indices.items())
        self.indices = indices

    def delete_index(self, index_name):
        self.conn.indices.delete_index_if_exists(index_name)
        self.refresh_index_cache()

    def populate_index(self, type, index_name):
        #add all the currently existing nodes into the index
        ref_node = self.datastore.get_reference_node(type)
        node_list = [rel.target_node for rel in ref_node.instance.outgoing]

        for node in node_list:
            key = node.key
            index_dict = self.populate_index_document(node, index_name)
            try:
                self.conn.delete(index_name, type, key)
            except ELASTIC_SEARCH_EXCEPTIONS as err:
                log.exception(err)
                pass
            self.conn.index(index_dict, index_name, type, key)
        self.conn.indices.refresh([index_name])

    def on_create(self, node):
        type_indices = self.get_indices_of_type(node.type)
        for index_name in type_indices:
            index_dict = self.populate_index_document(node, index_name)
            try:
                self.conn.index(index_dict, index_name, node.type, node.key)
                self.conn.indices.refresh([index_name])
            except ELASTIC_SEARCH_EXCEPTIONS as err:
                log.exception(err)
                pass

    def on_delete(self, node):
        type_indices = self.get_indices_of_type(node.type)
        for index_name in type_indices:
            try:
                self.conn.delete(index_name, node.type, node.key)
                self.conn.indices.refresh([index_name])
            except ELASTIC_SEARCH_EXCEPTIONS as err:
                log.exception(err)
                pass

    def on_modify(self, node):
        type_indices = self.get_indices_of_type(node.type)
        for index_name in type_indices:
            index_dict = self.populate_index_document(node, index_name)
            try:
                self.conn.delete(index_name, node.type, node.key)
                self.conn.index(index_dict, index_name, node.type, node.key)
                self.conn.indices.refresh([index_name])
            except ELASTIC_SEARCH_EXCEPTIONS as err:
                log.exception(err)
                pass

    def get_indices_of_type(self, type):
        type_indices = [
            key for key, value in self.indices.items()
            if type in value
        ]
        return type_indices

    def populate_index_document(self, node, index_name):
        indexed_variables = self.indices[index_name][node.type]['properties'].keys()
        index_dict = {
            field: node[field] for field in indexed_variables
        }
        return index_dict
