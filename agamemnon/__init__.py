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
import logging
from agamemnon.factory import load_from_settings
from agamemnon.exceptions import NoTransactionError, NodeNotFoundException

log = logging.getLogger(__name__)

def DFS(node, relationship_type, return_predicate=None):
    visited = set([node.key])
    S = [relationship for relationship in getattr(node, relationship_type)]
    while S:
        p = S.pop()
        relationship = p
        child = relationship.target_node
        if child.key not in visited:
            if return_predicate is not None and return_predicate(relationship, child):
                visited.add(child.key)
                yield child
            elif return_predicate is None:
                visited.add(child.key)
                yield child
            if hasattr(child, relationship_type):
                visited.add(child.key)
                S.extend([relationship for relationship in getattr(child, relationship_type)])

