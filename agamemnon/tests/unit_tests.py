# -*- encoding: ISO-8859-5 -*-
import random
from unittest import TestCase
from agamemnon import cassandra
from agamemnon.factory import load_from_settings
from agamemnon.primitives import updating_node

in_memory = False

class AgamemnonTests(TestCase):

    def set_up_cassandra(self):
        host_list = '["localhost:9160"]'
        keyspace = 'agamemnontests'
        try:
            cassandra.drop_keyspace(host_list, keyspace)
        except Exception:
            pass
        cassandra.create_keyspace(host_list, keyspace)
        self.ds = load_from_settings({
            'agamemnon.host_list': host_list,
            "agamemnon.keyspace": keyspace
        })

    def set_up_in_memory(self):
        self.ds = load_from_settings({'agamemnon.keyspace': 'memory'})
    
    def create_node(self, node_type, id):
        attributes = {
            'boolean': True,
            'integer': id,
            'long': long(1000),
            'float': 1.5434235,
            'string': 'name%s' % id,
            'unicode': 'абвгд'
        }
        key = 'node_%s' % id
        self.ds.create_node(node_type, key, attributes)
        node = self.ds.get_node(node_type, key)
        self.failUnlessEqual(key, node.key)
        self.failUnlessEqual(node_type, node.type)
        return key, attributes

    def containment(self, node_type, node):
        reference_node = self.ds.get_reference_node(node_type)
        test_reference_nodes = [rel.source_node for rel in node.instance.incoming]
        self.failUnlessEqual(1, len(test_reference_nodes))
        self.failUnlessEqual(reference_node, test_reference_nodes[0])
        ref_ref_node = self.ds.get_reference_node()
        test_reference_nodes = [rel.target_node for rel in ref_ref_node.instance.outgoing]
        self.failUnlessEqual(2, len(test_reference_nodes))
        self.failUnlessEqual(sorted([ref_ref_node, reference_node]), sorted(test_reference_nodes))
        self.failUnless(node_type in ref_ref_node.instance)
        self.failUnless(ref_ref_node.key in reference_node.instance)

    def get_set_attributes(self, node, attributes):
        self.failUnlessEqual(attributes, node.attributes)
        node['new_attribute'] = 'sample attr'
        node.commit()
        node = self.ds.get_node(node.type, node.key)
        self.failUnlessEqual('sample attr', node['new_attribute'])
        self.failIfEqual(attributes, node.attributes)
        # Test the context manager
        node = self.ds.get_node(node.type, node.key)
        with updating_node(node):
            node['new_attribute'] = 'new sample attr'
        node = self.ds.get_node(node.type, node.key)
        self.failUnlessEqual('new sample attr', node['new_attribute'])
        self.failIfEqual(attributes, node.attributes)
        with updating_node(node):
            del(node['new sample attr'])
        node = self.ds.get_node(node.type, node.key)
        try:
            attr = node['new sample attr']
            print "We should not have found 'new sample attr' = %s" % attr
            self.fail()
        except KeyError:
            pass


    def create_random_relationship(self, node, target_type, node_list):
        target_key, target_attributes = random.choice(node_list)
        while target_key == node.key and not target_key in node.is_related_to:
            target_key, target_attributes = random.choice(node_list)
        attributes = {
            'int': 10,
            'float': 2.3,
            'long': long(10),
            'boolean': True,
            'string': 'string',
            'unicode': 'абвгд'
        }
        kw_args = {
            'test_kwarg': 'kw'
        }
        target_node = self.ds.get_node(target_type, target_key)
        rel = node.is_related_to(target_node, attributes=attributes, **kw_args)
        self.failUnless(target_key in node.is_related_to)
        self.failUnless(node.key in target_node.is_related_to)
        rel_to_target = target_node.is_related_to.relationships_with(node.key)[0]
        self.failUnlessEqual(rel, rel_to_target)
        complete_attributes = {}
        complete_attributes.update(attributes)
        complete_attributes.update(kw_args)
        test_attributes = rel_to_target.attributes
        for key in complete_attributes.keys():
            self.failUnlessEqual(complete_attributes[key], test_attributes[key])
        self.failUnlessEqual(len(complete_attributes), len(test_attributes))
        self.failUnlessEqual(rel.key, rel_to_target.key)
        in_outbound_relationships = False
        for rel in node.is_related_to.outgoing:
            if rel.target_node.key == target_key:
                in_outbound_relationships = True
        self.failUnless(in_outbound_relationships)
        in_inbound_relationships = False
        for rel in target_node.is_related_to.incoming:
            if rel.source_node.key == node.key:
                in_inbound_relationships = True
        self.failUnless(in_inbound_relationships)
        rel['dummy_variable'] = 'dummy'
        rel_attributes = rel.attributes
        self.failIfEqual(attributes, rel.attributes)
        self.failUnlessEqual('dummy', rel_attributes['dummy_variable'])
        del(rel['dummy_variable'])
        try:
            rel['dummy_variable']
        except KeyError:
            pass

        rel['int'] = 20
        rel.commit()
        rel_to_target = target_node.is_related_to.relationships_with(node.key)[0]
        if rel_to_target.key == rel.key:
            self.failUnlessEqual(20, rel_to_target['int'])
        return node, target_node

    def delete_relationships(self, source, target):
        source_initial_rel_count = len(source.relationships)
        target_initial_rel_count = len(target.relationships)
        self.failUnless(target.key in source.is_related_to)
        self.failUnless(source.key in target.is_related_to)
        rel_list = source.is_related_to.relationships_with(target.key)
        self.failUnlessEqual(1, len(rel_list))
        rel = rel_list[0]
        rel.delete()
        self.failIf(target.key in source.is_related_to)
        self.failIf(source.key in target.is_related_to)
        source_post_delete_count = len(source.relationships)
        target_post_delete_count = len(target.relationships)
        self.failUnlessEqual(source_initial_rel_count - 1, source_post_delete_count)
        self.failUnlessEqual(target_initial_rel_count - 1, target_post_delete_count)
        return rel

    def test_cassandra(self):
        """
        Test the cassandra data store
        """
        self.set_up_cassandra()
        self.one_node_type_one_relationship_type()

    def test_in_memory(self):
        """
        Test the in_memory data store
        """
        self.set_up_in_memory()
        self.one_node_type_one_relationship_type()

    def one_node_type_one_relationship_type(self):
        """
        Tests for one node type and one relationship type.
        """
        node_type = "type_a"

        node_list = []
        for i in xrange(100):
            node_list.append(self.create_node(node_type, i))
        for key, attributes in node_list:
            node = self.ds.get_node(node_type, key)
            # test the basic details of the reference node including containment
            self.containment(node_type, node)
            # test updating the attributes of the node
            self.get_set_attributes(node, attributes)
        #Generate "random" network
        relationships = []
        for key, attributes in node_list:
            node = self.ds.get_node(node_type, key)
            for i in range(5):
                relationships.append(self.create_random_relationship(node, node_type, node_list))

        random_relationships = []
        for i in xrange(10):
            source, target = random.choice(relationships)
            self.delete_relationships(source, target)
            relationships.remove((source, target))

        for source, target in random_relationships: self.delete_relationships(source, target)

        #delete node
        deleted_nodes = []
        for i in xrange(10):
            source, target = random.choice(relationships)
            deleted_nodes.append(source)
            relationships_to_delete = [rel for rel in source.relationships]
            source.delete()
            for deleted_rel in relationships_to_delete:
                target_incoming_relationships = [rel for rel in target.is_related_to.incoming]
                self.failIf(source.key in target.is_related_to)
                self.failIf(deleted_rel in target_incoming_relationships)
