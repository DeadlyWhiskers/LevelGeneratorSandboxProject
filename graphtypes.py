from dataclasses import dataclass

@dataclass
class Node:
    id: str
    type: str
    allow_puzzle: str = "allow"

@dataclass
class Edge:
    from_node: str
    to_node: str
    key_required: bool = False
    
@dataclass
class LevelGraph:
    nodes: dict[str, Node]
    edges: list[Edge]