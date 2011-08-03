==========================
Usage
==========================

The following is an example of how to use Agamemnon in your own code


>>> from agamemnon.factory import load_from_settings

First, we can decide which kind of data store we are creating.  In this case we're creating an InMemory data store

>>> #config = {'agamemnon.keyspace':'agamemnontest', 'agamemnon.host_list':'["localhost:9160"]'}
>>> config = {'agamemnon.keyspace':'memory'}
>>> graph_db = load_from_settings(config)

In honor of The Simpsons Movie, we'll create a node called spiderpig

>>> spiderpig = graph_db.create_node('test_type', 'spiderpig', {'sound':'oink'})

Now we will retrieve the spiderpig from the graph and check that the attributes were correct.

>>> spiderpig = graph_db.get_node('test_type', 'spiderpig')
>>> spiderpig['sound']
'oink'


Now we will create a friend for the spiderpig (who also happens to be his alter ego).  Again, let's check to
confirm that the node and it's attributes were created correctly.

>>> harry_plopper = graph_db.create_node('test_type', 'Harry Plopper', {'sound':'plop'})
>>> harry_plopper = graph_db.get_node('test_type','Harry Plopper')
>>> harry_plopper['sound']
'plop'

Nodes can have different types as well.  Here we create a node of type simpson, with name Homer.  This node has
different attributes than the previous nodes.

>>> homer = graph_db.create_node('simpson', 'Homer', {'sound':'Doh', 'job':'Safety Technician'})
>>> homer = graph_db.get_node('simpson', 'Homer')
>>> homer['sound']
'Doh'
>>> homer['job']
'Safety Technician'

Nodes by themselves are not very useful.  Let's create a relationship between spiderpig and Harry Plopper.

>>> rel = spiderpig.friend(harry_plopper, key='spiderpig_harry_plopper_alliance', alter_ego=True, best=False)

This creates a relationship of type friend.  The key has been specified in this case, although it is not necessary.
If no key is supplied a uuid will be generated for the relationship.

Every node type has a "reference node".  This is a metanode for the type and functions as an index for all nodes of a
given type.

>>> reference_node = graph_db.get_reference_node('test_type')

Getting the instances from the test_type reference node should return the Harry Plopper node and the spiderpig node.

>>> sorted([rel.target_node.key for rel in reference_node.instance.outgoing])
['Harry Plopper', 'spiderpig']

The spiderpig should only have one friend at this point, and it should be Harry Plopper

>>> friends = [rel for rel in spiderpig.friend]

>>> len(friends)
1

>>> friends[0].target_node.key
'Harry Plopper'

Now let's confirm that Harry Plopper is friends with spider pig as well:

>>> 'spiderpig' in harry_plopper.friend
True

And, once more, make sure that spider pig is Harry Plopper's only friend:

>>> friends = [rel for rel in harry_plopper.friend]

>>> len(friends)
1

>>> friends[0].source_node.key
'spiderpig'

They should not be best friends.  Let's confirm this:

>>> friends[0]['best']
False

Homer is spiderpig's best friend:

>>> rel = homer.friend(spiderpig, best=True, alter_ego=False, type='love', strength=100)

Here we added additional attributes to the relationship.

Now spiderpig should have 2 friends.

>>> friends = [rel for rel in spiderpig.friend]
>>> len(friends)
2

You can get a list of all of the relationships of a particular type between a node and other nodes with a particular key

>>> homer_spiderpig_love = spiderpig.friend.relationships_with('Homer')
>>> len(homer_spiderpig_love)
1

>>> homer_spiderpig_love = spiderpig.friend.relationships_with('Homer')
>>> print homer_spiderpig_love[0]['strength']
100
