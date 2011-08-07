# Copyright 2010 University of Chicago
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from contextlib import contextmanager
from UserDict import DictMixin

from pycassa.cassandra.ttypes import NotFoundException

__author__ = 'trhowe'

DEFAULT_COLUMN_COUNT = 1000

@contextmanager
def updating_node(node):
    yield node
    node.commit()


class Relationship(object):
    """
    Represents a directed connection between two nodes
    """

    def __init__(self, rel_id, source_node, target_node, data_store, type, args=dict()):
        """
        Create relationship.
        """
        self._rel_id = rel_id
        self.data_store = data_store
        self._type = type
        self.old_values = args
        self.new_values = {}
        self.new_values.update(self.old_values)
        self.relationship_factories = {}
        self._source_node = source_node
        self._target_node = target_node
        self.dirty = False

    @property
    def key(self):
        return self.old_values['rel_key']

    @property
    def rel_key(self):
        return self._rel_id

    @property
    def type(self):
        return self._type

    @property
    def source_node(self):
        return self._source_node

    @property
    def target_node(self):
        return self._target_node

    @property
    def attributes(self):
        for key in self.new_values:
            self.old_values[key] = self.new_values[key]

        class RelationshipFilteredDict(DictMixin):
            def __init__(self, delegate):
                self._delegate = delegate

            def _is_node_key(self, item):
                return item.startswith('target__') or item.startswith('source__')

            def _is_rel_key(self, item):
                return item.startswith('rel_key') or item.startswith('rel_type')

            def __getitem__(self, item):
                if  self._is_node_key(item) or self._is_rel_key(item):
                    raise KeyError
                else:
                    return self._delegate[item]

            def keys(self):
                return [
                    key for key in self._delegate.keys()
                    if not self._is_node_key(key) and not self._is_rel_key(key)
                ]

        return RelationshipFilteredDict(self.old_values)

    def __getitem__(self, item):
        if item in self.new_values:
            return self.new_values[item]
        else:
            return self.old_values[item]

    def __contains__(self, item):
        return item in self.new_values.keys() or item in self.old_values.keys()

    def __setitem__(self, key, value):
        self.new_values[key] = value
        self.dirty = True

    def __delitem__(self, key):
        if key in self.new_values.keys():
            del(self.new_values[key])
        
    def delete(self):
        self.data_store.delete_relationship(self._type, self._rel_id, self.source_node.type, self.source_node.key,
                                            self.target_node.type, self.target_node.key)

    #TODO: fix this
    def commit(self):
        self.data_store.create_relationship(self.type, self.source_node, self.target_node,
                                            key=self._rel_id, args=self.new_values)

    def clear(self):
        self.new_values = {}
        self.new_values.update(self.old_values)
        self.dirty = False
    def __str__(self):
        return '%s: %s:%s -> %s:%s' % (
            self._type, self.source_node.type, self.source_node.key, self.target_node.type, self.target_node.key)

    def __eq__(self, other):
        if not isinstance(other, Relationship):
            return False
        return other.rel_key == self.rel_key and other.type == other.type

    def __cmp__(self, other):
        if not isinstance(other, Relationship):
            return -1
        return other.rel_key == self.rel_key and other.type == other.type


class RelationshipList(object):
    def __init__(self, relationships):
        self._relationships = relationships

    @property
    def single(self):
        if len(self._relationships) > 0:
            return self._relationships[0]
        else:
            return None

    def __len__(self):
        return len(self._relationships)

    def __iter__(self):
        for rel in self._relationships:
            yield rel


class RelationshipFactory(object):
    def __init__(self, data_store, parent_node, rel_type):
        self._rel_type = rel_type
        self._data_store = data_store
        self._parent_node = parent_node

    #TODO: specify order as from key vs timestamp
    def __call__(self, node, key=None, attributes=dict(), **kwargs):
        complete_attributes = {}
        complete_attributes.update(attributes)
        complete_attributes.update(kwargs)
        return self._data_store.create_relationship(self._rel_type, self._parent_node, node, key, complete_attributes)

    #TODO: Implement indexing solution here
    def __getitem__(self, item):
        try:
            relationships = []
            for relationship in self:
                if relationship.to_node.key == item:
                    relationships.append(relationship)
            return relationships
        except NotFoundException:
            return []

    def __contains__(self, item):
        return len(self.relationships_with(item)) > 0

    def relationships_with(self, node_key):
        return self._data_store.has_relationship(self._parent_node, node_key, self._rel_type)

    def get_outgoing(self, count):
        try:
            rels = self._data_store.get_outgoing_relationships(self._parent_node, self._rel_type, count=count)
        except NotFoundException:
            rels = []
        return RelationshipList(rels)

    def get_incoming(self, count):
        try:
            rels = self._data_store.get_incoming_relationships(self._parent_node, self._rel_type, count=count)
        except NotFoundException:
            rels = []
        return RelationshipList(rels)

    @property
    def parent_node(self):
        return self._parent_node

    @property
    def outgoing(self):
        try:
            rels = self._data_store.get_outgoing_relationships(self._parent_node, self._rel_type)
        except NotFoundException:
            rels = []
        return RelationshipList(rels)

    @property
    def incoming(self):
        try:
            rels = self._data_store.get_incoming_relationships(self._parent_node, self._rel_type)
        except NotFoundException:
            rels = []
        return RelationshipList(rels)


    def __len__(self):
        return len(self.outgoing) + len(self.incoming)

    def __iter__(self):
        for rel in self.outgoing:
            yield rel
        for rel in self.incoming:
            yield rel


class Node(object):
    def __init__(self, data_store, type, key, args=None):
        self._key = key
        self._data_store = data_store
        self._type = type
        self.old_values = args
        self.new_values = {}
        self.relationship_factories = {}
        self.dirty = False
        self._delete = False

    @property
    def key(self):
        return self._key

    @property
    def type(self):
        return self._type

    @property
    def relationships(self):
        class RelationshipsHolder(object):
            def __init__(self, data_store, node):
                self._data_store = data_store
                self._node = node

            @property
            def outgoing(self):
                return self._data_store.get_all_outgoing_relationships(self._node, DEFAULT_COLUMN_COUNT)

            @property
            def incoming(self):
                return self._data_store.get_all_incoming_relationships(self._node, DEFAULT_COLUMN_COUNT)

            def __len__(self):
                return len(self.outgoing) + len(self.incoming)

            def __iter__(self):
                rels = []
                rels.extend(self.outgoing)
                rels.extend(self.incoming)
                for rel in rels:
                    yield rel

        return RelationshipsHolder(self._data_store, self)


    def __getattr__(self, item):
        if hasattr(self.__dict__, item):
            return self.__dict__[item]
        else:
            relationship_factory = RelationshipFactory(self._data_store, self, item)
            self.relationship_factories[item] = relationship_factory
            return relationship_factory

    def __getitem__(self, item):
        if item in self.new_values:
            return self.new_values[item]
        else:
            return self.old_values[item]

    def __setitem__(self, key, value):
        self.new_values[key] = value
        self.dirty = True

    def __delitem__(self, key):
        if key in self.new_values.keys():
            del(self.new_values[key])
        if key in self.old_values.keys():
            del(self.old_values[key])
        self.dirty = True

    @property
    def attributes(self):
        attr = {}
        if self.old_values is not None:
            attr.update(self.old_values)
        if self.new_values is not None:
            attr.update(self.new_values)
        return attr

    def delete(self):
        self._data_store.delete_node(self)
        self.node = None

    def commit(self):
        for key in self.new_values:
            self.old_values[key] = self.new_values[key]
        self._data_store.save_node(self)

    def __str__(self):
        return 'Node: %s => %s' % (self.type, self.key)

    def __cmp__(self, other):
        if not isinstance(other, Node):
            return False
        return other.type == self.type and other.key == self.key

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return other.type == self.type and other.key == self.key


