import json

from dataclasses import dataclass
from graphtypes import Edge
from graphtypes import Node

@dataclass
class InterfaceInput:
    connect_to: list[str]


@dataclass
class InterfaceOutput:
    connect_from: list[str]
    key_required: bool = False
    
@dataclass
class Interface:
    inputs: list[InterfaceInput]
    outputs: list[InterfaceOutput]
    
@dataclass
class Replacement:
    nodes: list[Node]
    edges: list[Edge]
    
@dataclass
class GrammarRule:
    id: str
    from_type: str
    replacement: Replacement
    interface: Interface
    cost: int
    weight: float
    required_outputs: int | None = None
    required_inputs: int | None = None
    
class Grammar:

    def __init__(self, rules: list[GrammarRule]):
        self.rules = rules

    def get_rules(self, node_type: str) -> list[GrammarRule]:
        return [
            rule
            for rule in self.rules
            if rule.from_type == node_type
        ]
        
    @staticmethod
    def _parse_rule(data: dict) -> GrammarRule:
        replacement_data = data["replacement"]
        interface_data = data["interface"]

        replacement = Replacement(
            nodes=[
                Node(
                    id=node["id"],
                    type=node["type"],
                    allow_puzzle=node.get("allow_puzzle", "inherit")
                )
                for node in replacement_data["nodes"]
            ],
            edges=[
                Edge(
                    from_node=edge["from"],
                    to_node=edge["to"],
                    key_required=edge.get("key_required", False)
                )
                for edge in replacement_data.get("edges", [])
            ]
        )

        interface = Interface(
            inputs=[
                InterfaceInput(
                    connect_to=item["connect_to"]
                )
                for item in interface_data.get("inputs", [])
            ],
            outputs=[
                InterfaceOutput(
                    connect_from=item["connect_from"],
                    key_required=item.get("key_required", False)
                )
                for item in interface_data.get("outputs", [])
            ]
        )

        return GrammarRule(
            id=data["id"],
            from_type=data["from"],
            replacement=replacement,
            interface=interface,
            cost=data["cost"],
            weight=data["weight"],
            required_outputs=data.get("required_outputs"),
            required_inputs=data.get("required_inputs")
        )
        
    @classmethod
    def from_json(cls, path: str) -> "Grammar":
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        rules = [
            cls._parse_rule(rule_data)
            for rule_data in data["grammar"]["rules"]
        ]

        return cls(rules)