# -*- encoding: ISO-8859-5 -*-
import random
from unittest import TestCase, SkipTest
from agamemnon.exceptions import NodeNotFoundException
from agamemnon.factory import load_from_file
from agamemnon.primitives import updating_node
from pycassa import TTransport
from os import path
import socket

from nose.plugins.attrib import attr

TEST_CONFIG_FILE = path.join(path.dirname(__file__),'test_config.yml')

class AgamemnonTests(object):
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
        self.assertEqual(key, node.key)
        self.assertEqual(node_type, node.type)
        return key, attributes
    

    def containment(self, node_type, node):
        reference_node = self.ds.get_reference_node(node_type)
        test_reference_nodes = [rel.source_node for rel in node.instance.incoming]
        self.assertEqual(1, len(test_reference_nodes))
        self.assertEqual(reference_node, test_reference_nodes[0])
        ref_ref_node = self.ds.get_reference_node()
        test_reference_nodes = [rel.target_node for rel in ref_ref_node.instance.outgoing]
        self.assertEqual(2, len(test_reference_nodes))
        self.assertEqual(sorted([ref_ref_node, reference_node]), sorted(test_reference_nodes))
        self.assertTrue(node_type in ref_ref_node.instance)
        self.assertTrue(ref_ref_node.key in reference_node.instance)

    def get_set_attributes(self, node, attributes):
        self.assertEqual(attributes, node.attributes)
        node['new_attribute'] = 'sample attr'
        node.commit()
        node = self.ds.get_node(node.type, node.key)
        self.assertEqual('sample attr', node['new_attribute'])
        self.assertNotEqual(attributes, node.attributes)
        # Test the context manager
        node = self.ds.get_node(node.type, node.key)
        with updating_node(node):
            node['new_attribute'] = 'new sample attr'
        node = self.ds.get_node(node.type, node.key)
        self.assertEqual('new sample attr', node['new_attribute'])
        self.assertNotEqual(attributes, node.attributes)
        with updating_node(node):
            del(node['new_attribute'])
        node = self.ds.get_node(node.type, node.key)
        if 'new_attribute' in node:
            print "We should not have found 'new_attribute' = %s" % node['new_attribute']
            self.fail()


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
        self.assertTrue(target_key in node.is_related_to)
        self.assertTrue(node.key in target_node.is_related_to)
        rel_to_target = target_node.is_related_to.relationships_with(node.key)[0]
        self.assertEqual(rel, rel_to_target)
        complete_attributes = {}
        complete_attributes.update(attributes)
        complete_attributes.update(kw_args)
        test_attributes = rel_to_target.attributes
        for key in complete_attributes.keys():
            self.assertEqual(complete_attributes[key], test_attributes[key])
        self.assertEqual(len(complete_attributes), len(test_attributes))
        self.assertEqual(rel.key, rel_to_target.key)
        self.assertTrue(self.ds.get_relationship(rel.type, rel.key) is not None)
        self.assertEqual(len(complete_attributes), len(self.ds.get_relationship(rel.type, rel.key).attributes))
        in_outbound_relationships = False
        for rel in node.is_related_to.outgoing:
            if rel.target_node.key == target_key:
                in_outbound_relationships = True
        self.assertTrue(in_outbound_relationships)
        in_inbound_relationships = False
        for rel in target_node.is_related_to.incoming:
            if rel.source_node.key == node.key:
                in_inbound_relationships = True
        self.assertTrue(in_inbound_relationships)
        rel['dummy_variable'] = 'dummy'
        rel_attributes = rel.attributes
        self.assertNotEqual(attributes, rel.attributes)
        self.assertEqual('dummy', rel_attributes['dummy_variable'])
        del(rel['dummy_variable'])
        try:
            rel['dummy_variable']
        except KeyError:
            pass

        rel['int'] = 20
        rel.commit()
        rel_to_target = target_node.is_related_to.relationships_with(node.key)[0]
        if rel_to_target.key == rel.key:
            self.assertEqual(20, rel_to_target['int'])
        return node, target_node


    def delete_relationships(self, source, target):
        source_initial_rel_count = len(source.relationships)
        target_initial_rel_count = len(target.relationships)
        self.assertTrue(target.key in source.is_related_to)
        self.assertTrue(source.key in target.is_related_to)
        rel_list = source.is_related_to.relationships_with(target.key)
        self.assertEqual(1, len(rel_list))
        rel = rel_list[0]
        rel.delete()
        self.assertFalse(target.key in source.is_related_to)
        self.assertFalse(source.key in target.is_related_to)
        source_post_delete_count = len(source.relationships)
        target_post_delete_count = len(target.relationships)
        self.assertEqual(source_initial_rel_count - 1, source_post_delete_count)
        self.assertEqual(target_initial_rel_count - 1, target_post_delete_count)
        return rel

    def test_multi_get(self):
        for i in range(0, 1000):
            self.ds.create_node("test", str(i))

        nodes = self.ds.get_nodes("test", [str(i) for i in range(200, 400)])
        self.assertEqual(len(nodes), 200)


    def test_indexed_get(self):
        self.ds.create_cf("indexed")
        self.ds.create_secondary_index("indexed","color")
        self.ds.create_secondary_index("indexed","size")

        self.ds.create_node("indexed", "a", { "color": "red", "size": "small" , "num" : 1.0})
        self.ds.create_node("indexed", "b", { "color": "black", "size": "small" , "num" : 1.0 })
        self.ds.create_node("indexed", "c", { "color": "green", "size": "small" , "num" : 1.0 })
        self.ds.create_node("indexed", "e", { "color": "red", "size": "big" , "num" : 1.0 })
        self.ds.create_node("indexed", "f", { "color": "black", "size": "big" , "num" : 1.0 })
        self.ds.create_node("indexed", "g", { "color": "green", "size": "big" , "num" : 1.0 })
        

        nodes = self.ds.get_nodes_by_attr("indexed", {"color": "red"})
        self.assertEqual(len(nodes), 2)
        for node in nodes:
            self.assertTrue(node.key in ["a","e"])
            self.assertEqual(type(node["num"]), type(1.0))

        nodes = self.ds.get_nodes_by_attr("indexed", {"size": "big"})
        self.assertEqual(len(nodes), 3)
        for node in nodes:
            self.assertTrue(node.key in ["e","f","g"])
            self.assertEqual(type(node["num"]), type(1.0))

        nodes = self.ds.get_nodes_by_attr("indexed", {"size": "big", "color":"red"})
        self.assertEqual(len(nodes), 1)
        for node in nodes:
            self.assertTrue(node.key in ["e"])
            self.assertEqual(type(node["num"]), type(1.0))

    def test_update_relationship_indexes(self):
        self.ds.create_node("source", "A")
        self.ds.create_node("target", "B")
        node_a = self.ds.get_node("source", "A")
        node_b = self.ds.get_node("target", "B")

        rel = node_a.related(node_b)
        key = rel.key
        rel_key = rel.rel_key

        self.assertEqual(len(node_a.related.outgoing), 1)
        self.assertEqual(len(node_b.related.incoming), 1)

        rel["foo"] = "bar"
        rel.commit()

        # update targets so we know the denormalized 
        # indexes are being updated correctly
        node_a['fuu'] = 'fuu'
        node_a.commit()
        node_b['fee'] = 'fee'
        node_b.commit()

        self.assertEqual(len(node_a.related.outgoing), 1)
        self.assertEqual(len(node_b.related.incoming), 1)
        self.assertEqual(rel.key,  key)
        self.assertEqual(rel.rel_key,  rel_key)
        self.assertEqual(rel.source_node, node_a)
        self.assertEqual(rel.source_node.attributes, node_a.attributes)
        self.assertEqual(rel.target_node, node_b)
        self.assertEqual(rel.target_node.attributes, node_b.attributes)

        rel = node_a.related.outgoing.single


        self.assertEqual(rel['foo'], 'bar')
        rel["foo"] = "buzz"
        rel.commit()

        self.assertEqual(len(node_a.related.outgoing), 1)
        self.assertEqual(len(node_b.related.incoming), 1)
        self.assertEqual(rel.key,  key)
        self.assertEqual(rel.rel_key,  rel_key)
        self.assertEqual(rel.source_node, node_a)
        self.assertEqual(rel.source_node.attributes, node_a.attributes)
        self.assertEqual(rel.target_node, node_b)
        self.assertEqual(rel.target_node.attributes, node_b.attributes)

        node_b.related.incoming.single

        self.assertEqual(rel['foo'], 'buzz')
        rel["foo"] = "bazz"
        rel.commit()

        self.assertEqual(len(node_a.related.outgoing), 1)
        self.assertEqual(len(node_b.related.incoming), 1)
        self.assertEqual(rel.key,  key)
        self.assertEqual(rel.rel_key,  rel_key)
        self.assertEqual(rel.source_node, node_a)
        self.assertEqual(rel.source_node.attributes, node_a.attributes)
        self.assertEqual(rel.target_node, node_b)
        self.assertEqual(rel.target_node.attributes, node_b.attributes)

        rel = self.ds.get_relationship('related', key)

        self.assertEqual(rel['foo'], 'bazz')
        rel["foo"] = "bizz"
        rel.commit()

        self.assertEqual(len(node_a.related.outgoing), 1)
        self.assertEqual(len(node_b.related.incoming), 1)
        self.assertEqual(rel.key,  key)
        self.assertEqual(rel.rel_key,  rel_key)
        self.assertEqual(rel.source_node, node_a)
        self.assertEqual(rel.source_node.attributes, node_a.attributes)
        self.assertEqual(rel.target_node, node_b)
        self.assertEqual(rel.target_node.attributes, node_b.attributes)


    def test_one_node_type_one_relationship_type(self):
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
                self.assertFalse(source.key in target.is_related_to)
                self.assertFalse(deleted_rel in target_incoming_relationships)


    def test_large_relationship_sets(self):
        num = 1002
        node_type = "type_a"

        root = self.ds.create_node('root', 'root')
        node_list = [
            self.ds.create_node(node_type, str(i))
            for i in xrange(num)
        ]


        for node in node_list:
            node.into(root)
            root.outof(node)

        self.assertEqual(1, len(root.instance.incoming))

        self.assertEqual(num, len([rel for rel in root.outof.outgoing]))
        self.assertEqual(num, len([rel for rel in root.into.incoming]))
        self.assertEqual(num, len(root.outof.outgoing))
        self.assertEqual(num, len(root.into.incoming))

        self.assertEqual(num, len([rel for rel in root.outof]))
        self.assertEqual(num, len([rel for rel in root.into]))
        self.assertEqual(num, len(root.outof))
        self.assertEqual(num, len(root.into))

        self.assertEqual(num, len([rel for rel in root.relationships.outgoing]))
        self.assertEqual(num + 1, len([rel for rel in root.relationships.incoming]))
        self.assertEqual(num, len(root.relationships.outgoing))
        self.assertEqual(num + 1, len(root.relationships.incoming))

        self.assertEqual(2*num + 1, len([rel for rel in root.relationships]))
        self.assertEqual(2*num + 1, len(root.relationships))


@attr(backend="cassandra")
class CassandraTests(TestCase, AgamemnonTests):
    def setUp(self):
        try:
            self.ds = load_from_file(TEST_CONFIG_FILE, 'cassandra_config_1')
            self.ds.truncate()
        except TTransport.TTransportException:
            raise SkipTest("Could not connect to cassandra.")


@attr(backend="memory")
class InMemoryTests(TestCase, AgamemnonTests):
    def setUp(self):
        self.ds = load_from_file(TEST_CONFIG_FILE, 'memory_config_1')


@attr(backend="memory")
@attr(plugin="elastic_search")
class ElasticSearchTests(TestCase, AgamemnonTests):

    TEST_NODES = {
        "test_type_1": {
            "test1": {
                "full_text": "This is a sentence worth searching.",
                "author": "me",
            },
            "test2": {
                "full_text": "Four score and seven years ago...",
                "author": "lincoln",
            },
            "test3": {
                "full_text": "We hold these truths to be self-evident, that all men are created equal...",
                "author": "jefferson",
            },
        },
        "test_type_2": {
            "test1": {
                "other_text": "something and something",
            },
            "test2": {
                "other_text": "One fish, two fish, red fish, blue fish",
            },
            "test3": {
                "other_text": "I don't like green eggs and ham, I don't like them sam I am",
            },
        }
    }

    def setUp(self):
        self.ds = load_from_file(TEST_CONFIG_FILE, 'elastic_search_config')
        self.ds.truncate()
        try:
            self.ds.conn.collect_info()
        except socket.error:
            raise SkipTest("Can't connect to Elastic Search")

    def tearDown(self):
        self.ds.truncate()
        for index in self.ds.indices.keys():
            self.ds.delete_index(index)

    def _create_es_nodes(self):
        for type, node_data in self.TEST_NODES.items():
            for key, attr in node_data.items():
                self.ds.create_node(type, key, attr)

    def test_create_index(self):
        self.ds.create_index("test_type_1", ["full_text"], "test_index")
        #test to see if the index exists
        self.assertIn("test_index", self.ds.conn.indices.get_indices())
        self.assertIn("test_index", self.ds.get_indices_of_type("test_type_1"))
        self.assertNotIn("test_index", self.ds.get_indices_of_type("test_type_2"))

    def test_simple_text_search(self):
        self._create_es_nodes()
        self.ds.create_index("test_type_1", ["full_text","author"], "test_index")
        nodes = self.ds.search_index_text("lincoln")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].key, "test2")
        self.assertEqual(nodes[0].type, "test_type_1")


    def test_update_indices(self): 
        self._create_es_nodes()
        self.ds.create_index("test_type_1", ["full_text","author"], "test_index")
        node = self.ds.get_node("test_type_1", "test2")
        node['author'] = 'joshbryan'
        node.commit()
        nodes = self.ds.search_index_text("lincoln")
        self.assertEqual(len(nodes), 0)

        self.ds.create_node("test_type_1", "new_node", {"full_text": "Lincoln is cool"})
        nodes = self.ds.search_index_text("lincoln")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].key, "new_node")
        self.assertEqual(nodes[0].type, "test_type_1")

    def test_delete_nodes(self):
        self._create_es_nodes()
        self.ds.create_index("test_type_1", ["full_text","author"], "test_index")
        for type, node_data in self.TEST_NODES.items():
            for key in node_data.keys():
                self.ds.get_node(type, key).delete()

        stats = self.ds.conn.get_indices()
        self.assertEqual(stats['test_index']['num_docs'], 0)


    def test_multiple_types_one_index(self):
        self._create_es_nodes()
        self.ds.create_index("test_type_1", ["full_text"], "test_index")
        self.ds.create_index("test_type_2", ["other_text"], "test_index")
        nodes = self.ds.search_index_text("green truths", indices=["test_index"])
        self.assertEqual(len(nodes), 2)
        type_key_list = [(node.type, node.key) for node in nodes]
        self.assertIn(("test_type_1", "test3"), type_key_list)
        self.assertIn(("test_type_2", "test3"), type_key_list)

        nodes = self.ds.search_index_text("green truths", node_type='test_type_1')
        self.assertEqual(len(nodes), 1)

    def test_multiple_indices(self):
        self._create_es_nodes()
        self.ds.create_index("test_type_1", ["full_text"], "test_index1")
        self.ds.create_index("test_type_1", ["author"], "test_index2")
        nodes = self.ds.search_index_text("lincoln", indices=["test_index1"])
        self.assertEqual(len(nodes), 0)

        nodes = self.ds.search_index_text("lincoln", indices=["test_index2"])
        self.assertEqual(len(nodes), 1)

        nodes = self.ds.search_index_text("lincoln")
        self.assertEqual(len(nodes), 1)

    def test_node_missing_fields(self):
        self.ds.create_index("test_type_1", ["full_text", "missing"], "test_index1")
        self._create_es_nodes()

