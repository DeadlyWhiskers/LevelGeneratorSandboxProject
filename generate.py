from dataclasses import dataclass
from grammar import GrammarRule
from grammar import Grammar
from graphtypes import Node, Edge
from random import Random
import sys
import copy

@dataclass
class Placement:
    rows: int
    cols: int
    positions: dict[str, tuple[int, int]]

    def make_grid(self) -> list[list[str | None]]:
        grid = [
            [None for _ in range(self.cols)]
            for _ in range(self.rows)
        ]

        for node_id, (row, col) in self.positions.items():
            grid[row][col] = node_id

        return grid

class LevelGraph:
    nodes: dict[str, Node]
    edges: list[Edge]
    node_counters: dict[str, int]
    
    def generate_node_id(self, node_type: str) -> str:
        counter = self.node_counters.get(node_type, 0) + 1
        self.node_counters[node_type] = counter
        return f"{node_type}_{counter}"
    
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.node_counters: dict[str, int] = {}
        
    # nodes
    def add_node(self, node_type: str, allow_puzzle: str = "allow") -> Node:
        node_id = self.generate_node_id(node_type)
        node = Node(
            id=node_id,
            type=node_type,
            allow_puzzle=allow_puzzle
        )

        self.nodes[node_id] = node

        return node
        
    def remove_node(self, node_id):
        del self.nodes[node_id]
        
        self.edges = [
        edge
        for edge in self.edges
        if edge.from_node != node_id
        and edge.to_node != node_id
    ]
    
    def get_node(self, node_id: str) -> Node:
        return self.nodes[node_id]
    
    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes
    
    # get_nodes_by_type(node_type)

    # edges
    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def remove_edge(self, edge: Edge):
        self.edges.remove(edge)
        
    def incoming_edges(self, node_id: str) -> list[Edge]:
        return [
            edge
            for edge in self.edges
            if edge.to_node == node_id
        ]
        
    def outgoing_edges(self, node_id: str) -> list[Edge]:
        return [
            edge
            for edge in self.edges
            if edge.from_node == node_id
        ]

    # grammar
    def replace_node(
    self,
    node_id: str,
    rule: GrammarRule):
        node = self.get_node(node_id)

        if node.type != rule.from_type:
            raise ValueError(
                f"Rule '{rule.id}' expects node type "
                f"'{rule.from_type}', got '{node.type}'"
            )
        
        incoming = self.incoming_edges(node_id)
        outgoing = self.outgoing_edges(node_id)
        
        if (
            rule.required_outputs is not None
            and len(outgoing) != rule.required_outputs
        ):
            raise ValueError(
                f"Rule '{rule.id}' requires "
                f"{rule.required_outputs} outputs, "
                f"but node '{node_id}' has {len(outgoing)}"
            )
        
        if (
            rule.required_inputs is not None
            and len(incoming) != rule.required_inputs
                ):
                    raise ValueError(
                        f"Rule '{rule.id}' requires "
                        f"{rule.required_inputs} inputs, "
                        f"but node '{node_id}' has {len(incoming)}"
                    )
        
        self.remove_node(node_id)
        
        # Так как в грамматике хранятся локальные адреса
        node_mapping = {}

        for replacement_node in rule.replacement.nodes:
            if replacement_node.allow_puzzle == "inherit":
                allow_puzzle = node.allow_puzzle
            else:
                allow_puzzle = replacement_node.allow_puzzle

            new_node = self.add_node(
                replacement_node.type,
                allow_puzzle
            )
            
            node_mapping[replacement_node.id] = new_node.id

        
        for replacement_edge in rule.replacement.edges:
            self.add_edge(
                Edge(
                    from_node=node_mapping[replacement_edge.from_node],
                    to_node=node_mapping[replacement_edge.to_node],
                    key_required=replacement_edge.key_required,
                )
            )

        
        # Входы  
        input_targets = [
            node_mapping[node_id]
            for interface_input in rule.interface.inputs
            for node_id in interface_input.connect_to
        ]

        for old_edge in incoming:
            for target_id in input_targets:
                self.add_edge(
                    Edge(
                        from_node=old_edge.from_node,
                        to_node=target_id,
                        key_required=old_edge.key_required,
                    )
                )
                
        # Выходы
        output_sources = [
        (node_mapping[node_id], interface_output.key_required)
        for interface_output in rule.interface.outputs
        for node_id in interface_output.connect_from
        ]

        for old_edge in outgoing:
            for source_id, key_required in output_sources:
                self.add_edge(
                    Edge(
                        from_node=source_id,
                        to_node=old_edge.to_node,
                        key_required=key_required or old_edge.key_required,
                    )
                )
    def get_nonterminals(self) -> list[Node]:
        nonterminal_types = {
            "level",
            "segment",
            "locked_quest",
            "key_segment",
            "finish",
            "room",
        }

        return [
            node
            for node in self.nodes.values()
            if node.type in nonterminal_types
        ]
        
    def is_complete(self) -> bool:
        return len(self.get_nonterminals()) == 0
    
    def degree(self, node_id: str) -> int:
        return sum(
            1
            for edge in self.edges
            if edge.from_node == node_id or edge.to_node == node_id
        )

# generation

class LevelGenerator:
    PUZZLE_NODE_TYPES = {
        "locked_quest"
    }

    
    def __init__(
        self,
        grammar: Grammar,
        budget_influence: float = 2.0,
        max_steps: int = 100,
    ):
        self.grammar = grammar
        self.budget_influence = budget_influence
        self.max_steps = max_steps

    def generate(
        self,
        size: tuple[int, int],
        rngen: Random,
    ) -> LevelGraph | None:
        rows, cols = size
        max_rooms = rows * cols

        # rng = Random(seed)
        rng = rngen

        graph = LevelGraph()
        graph.add_node("level")

        return self.search(
            graph=graph,
            remaining_budget=max_rooms,
            max_budget=max_rooms,
            rng=rng,
            steps=0,
        )

    def search(
        self,
        graph: LevelGraph,
        remaining_budget: int,
        max_budget: int,
        rng: Random,
        steps: int,
    ) -> LevelGraph | None:
        # Защита от бесконечного поиска
        if steps >= self.max_steps:
            return None

        # Успешное завершение
        if graph.is_complete():
            return graph

        # Собираем все допустимые действия:
        # (ID узла, правило, скорректированный вес)
        actions = []

        for node in graph.get_nonterminals():
            incoming_count = len(graph.incoming_edges(node.id))
            outgoing_count = len(graph.outgoing_edges(node.id))

            for rule in self.grammar.get_rules(node.type):
                # Проверка возможности размещения головоломки
                if not self.rule_respects_puzzle_policy(node, rule):
                    continue
                # Проверяем число входов
                if (
                    rule.required_inputs is not None
                    and incoming_count != rule.required_inputs
                ):
                    continue

                # Проверяем число выходов
                if (
                    rule.required_outputs is not None
                    and outgoing_count != rule.required_outputs
                ):
                    continue

                # Проверяем бюджет
                if rule.cost > remaining_budget:
                    continue

                # Рассчитываем скорректированный вес
                if rule.cost == 0:
                    adjusted_weight = rule.weight
                else:
                    budget_ratio = remaining_budget / max_budget

                    adjusted_weight = (
                        rule.weight
                        * budget_ratio
                        ** (self.budget_influence * rule.cost)
                    )

                if adjusted_weight > 0:
                    actions.append(
                        (node.id, rule, adjusted_weight)
                    )

        # Ни одного допустимого действия — тупик
        if not actions:
            return None

        # Пробуем варианты в случайном порядке
        ordered_actions = self.weighted_order(
            actions,
            rng,
        )

        for node_id, rule, _ in ordered_actions:
            # Каждая ветка поиска работает со своей копией
            next_graph = copy.deepcopy(graph)
            
            affected_nodes = {
                edge.from_node
                for edge in graph.edges
                if edge.to_node == node_id
            } | {
                edge.to_node
                for edge in graph.edges
                if edge.from_node == node_id
            }


            next_graph.replace_node(node_id, rule)
            
            if any(
                next_graph.degree(neighbor_id) > 4
                for neighbor_id in affected_nodes
                if next_graph.has_node(neighbor_id)
            ):
                continue

            result = self.search(
                graph=next_graph,
                remaining_budget=remaining_budget - rule.cost,
                max_budget=max_budget,
                rng=rng,
                steps=steps + 1,
            )

            if result is not None:
                return result

        # Все варианты привели в тупик
        return None
    
    def rule_respects_puzzle_policy(
        self,
        node: Node,
        rule: GrammarRule
    ) -> bool:
        for replacement_node in rule.replacement.nodes:
            if replacement_node.type not in self.PUZZLE_NODE_TYPES:
                continue

            if replacement_node.allow_puzzle == "inherit":
                effective_policy = node.allow_puzzle
            else:
                effective_policy = replacement_node.allow_puzzle

            if effective_policy == "forbid":
                return False

        return True


    @staticmethod
    def weighted_order(actions, rng):
        remaining = list(actions)
        result = []

        while remaining:
            weights = [
                action[2]
                for action in remaining
            ]

            selected = rng.choices(
                remaining,
                weights=weights,
                k=1,
            )[0]

            result.append(selected)
            remaining.remove(selected)

        return result

    @staticmethod
    def validate_graph(
    graph: LevelGraph,
    size: tuple[int, int],
    ) -> list[str]:
        errors = []
        max_rooms = size[0] * size[1]
        # 1. Проверяем, что все концы рёбер существуют,
        # и строим список смежности.
        adjacency = {node_id: set() for node_id in graph.nodes}

        for edge in graph.edges:
            if edge.from_node not in graph.nodes:
                errors.append(
                    f"Ребро ссылается на отсутствующий узел: "
                    f"{edge.from_node}"
                )
                continue

            if edge.to_node not in graph.nodes:
                errors.append(
                    f"Ребро ссылается на отсутствующий узел: "
                    f"{edge.to_node}"
                )
                continue

        # 2. Проверяем количество комнат.
        
        room_count = sum(
            1
            for _ in graph.nodes
        )

        if room_count > max_rooms:
            errors.append(
                f"Комнат больше, чем клеток сетки: "
                f"{room_count} > {max_rooms}"
            )

        return errors
    
def place_level(
    graph: LevelGraph,
    size: tuple[int, int],
    rngen: Random,
    max_search_steps: int = 10_000,
) -> Placement | None:
    rows, cols = size

    if rows <= 0 or cols <= 0:
        raise ValueError("Размер сетки должен быть положительным")

    if max_search_steps <= 0:
        raise ValueError("max_search_steps должен быть положительным")

    if not graph.nodes:
        raise ValueError("Нельзя разместить пустой граф")

    if len(graph.nodes) > rows * cols:
        return None

    starts = [
        node.id
        for node in graph.nodes.values()
        if node.type == "start_room"
    ]

    if len(starts) != 1:
        raise ValueError(
            f"Ожидалась одна стартовая комната, найдено: {len(starts)}"
        )

    # Строим неориентированный граф смежности.
    adjacency = {
        node_id: set()
        for node_id in graph.nodes
    }

    for edge in graph.edges:
        if (
            edge.from_node not in graph.nodes
            or edge.to_node not in graph.nodes
        ):
            raise ValueError(
                f"Ребро ссылается на отсутствующий узел: {edge}"
            )

        adjacency[edge.from_node].add(edge.to_node)
        adjacency[edge.to_node].add(edge.from_node)

    # rng = Random(seed)
    rng = rngen

    # node_id -> (row, col)
    positions: dict[str, tuple[int, int]] = {}

    # (row, col) -> node_id
    occupied: dict[tuple[int, int], str] = {}

    search_steps = 0

    def neighboring_cells(
        row: int,
        col: int,
    ) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r, c in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            )
            if 0 <= r < rows and 0 <= c < cols
        ]

    def get_candidates(node_id: str) -> list[tuple[int, int]]:
        # Все уже размещённые соседи этой комнаты по графу.
        placed_neighbors = [
            neighbor
            for neighbor in adjacency[node_id]
            if neighbor in positions
        ]

        if not placed_neighbors:
            return []

        # Клетки должны соседствовать со всеми уже размещёнными
        # соседями комнаты по графу.
        first = positions[placed_neighbors[0]]
        candidates = set(neighboring_cells(*first))

        for neighbor in placed_neighbors[1:]:
            cell = positions[neighbor]
            candidates &= set(neighboring_cells(*cell))

        # Убираем занятые клетки.
        candidates = [
            cell for cell in candidates
            if cell not in occupied
        ]

        rng.shuffle(candidates)
        return candidates

    def search() -> bool:
        nonlocal search_steps

        if len(positions) == len(graph.nodes):
            return True

        if search_steps >= max_search_steps:
            return False

        # Ищем комнаты, связанные с уже размещёнными.
        frontier = [
            node_id
            for node_id in graph.nodes
            if node_id not in positions
            and any(
                neighbor in positions
                for neighbor in adjacency[node_id]
            )
        ]

        if not frontier:
            # Например, граф оказался несвязным.
            return False

        # Сначала предпочитаем комнаты с большим количеством
        # уже размещённых соседей: для них меньше вариантов.
        max_placed_neighbors = max(
            sum(
                neighbor in positions
                for neighbor in adjacency[node_id]
            )
            for node_id in frontier
        )

        best_nodes = [
            node_id
            for node_id in frontier
            if sum(
                neighbor in positions
                for neighbor in adjacency[node_id]
            ) == max_placed_neighbors
        ]

        node_id = rng.choice(best_nodes)
        candidates = get_candidates(node_id)

        for cell in candidates:
            if search_steps >= max_search_steps:
                return False

            search_steps += 1

            # Пробуем разместить комнату.
            positions[node_id] = cell
            occupied[cell] = node_id

            if search():
                return True

            # Откат: освобождаем клетку.
            del positions[node_id]
            del occupied[cell]

        return False

    # Стартовую комнату тоже пробуем ставить в разные клетки.
    start_id = starts[0]
    start_cells = [
        (row, col)
        for row in range(rows)
        for col in range(cols)
    ]
    rng.shuffle(start_cells)

    for cell in start_cells:
        if search_steps >= max_search_steps:
            break

        search_steps += 1

        positions[start_id] = cell
        occupied[cell] = start_id

        if search():
            return Placement(
                rows=rows,
                cols=cols,
                positions=positions.copy(),
            )

        del positions[start_id]
        del occupied[cell]

    return None


def render_placement(
    graph: LevelGraph,
    placement: Placement,
) -> str:
    rows = placement.rows
    cols = placement.cols

    # Сопоставляем координаты и ID комнат.
    room_at = {
        position: node_id
        for node_id, position in placement.positions.items()
    }

    # Сопоставляем пары соседних комнат с типом связи.
    connections = {}

    for edge in graph.edges:
        if edge.from_node not in placement.positions:
            continue
        if edge.to_node not in placement.positions:
            continue

        a = placement.positions[edge.from_node]
        b = placement.positions[edge.to_node]

        # Упорядочиваем координаты, чтобы связь
        # находилась независимо от направления ребра.
        key = tuple(sorted((a, b)))

        # Если между комнатами несколько рёбер,
        # запертая связь имеет приоритет.
        locked = edge.key_required
        connections[key] = connections.get(key, False) or locked

    # Буква комнаты.
    def room_symbol(node_id):
        node_type = graph.nodes[node_id].type

        symbols = {
            "start_room": "S",
            "finish_room": "F",
            "generic_room": "G",
            "key_room": "K",
            "reward_room": "R",
        }

        return symbols.get(node_type, node_type[0].upper())

    # Связь между двумя клетками.
    def connection_symbol(a, b):
        key = tuple(sorted((a, b)))
        locked = connections.get(key, False)

        if a[0] == b[0]:
            return "=" if locked else "-"
        return "!" if locked else "|"

    # Каждая клетка отображается как символ комнаты
    # или пустое место. Связи выводятся между клетками.
    cell_width = 3
    output = []

    for row in range(rows):
        room_line = ""

        for col in range(cols):
            position = (row, col)
            node_id = room_at.get(position)

            symbol = room_symbol(node_id) if node_id else " "
            room_line += f" {symbol} "

            if col < cols - 1:
                next_position = (row, col + 1)

                if (
                    node_id is not None
                    and next_position in room_at
                    and tuple(sorted((position, next_position))) in connections
                ):
                    room_line += connection_symbol(
                        position,
                        next_position,
                    )
                else:
                    room_line += " "

        output.append(room_line.rstrip())

        if row < rows - 1:
            vertical_line = ""

            for col in range(cols):
                position = (row, col)
                next_position = (row + 1, col)

                if (
                    position in room_at
                    and next_position in room_at
                    and tuple(sorted((position, next_position))) in connections
                ):
                    symbol = connection_symbol(position, next_position)
                else:
                    symbol = " "

                vertical_line += f" {symbol} "

                if col < cols - 1:
                    vertical_line += " "

            if vertical_line.strip():
                output.append(vertical_line.rstrip())

    return "\n".join(output)


    
def main():

    # Найти где виснет + добавить функцию отсечения лишних маршрутов
    row = int(sys.argv[1])
    col = int(sys.argv[2])
    seed = int(sys.argv[3])
    # row = 8
    # col = 8
    # seed = 150
    rngen = Random(seed)
    
    grammar = Grammar.from_json("rules_upped.json")

    generator = LevelGenerator(
        grammar=grammar,
        budget_influence=2.0,
        max_steps=10000,
    )

    graph = generator.generate(
        size=(row, col),
        rngen=rngen,
    )

    if graph is None:
        print("Не удалось сгенерировать граф")
    else:
        errors = generator.validate_graph(graph, (row, col))

        if errors:
            for error in errors:
                print(f"Ошибка: {error}")
        else:
            placement = place_level(graph=graph,
                                    size=(row, col),
                                    rngen=rngen,
                                    max_search_steps=10_000,
                                    )
            if placement is None:
                print("Не удалось разместить уровень")
            else:
                print(render_placement(graph, placement))
                    
    #     print(render_placement(graph, placement))

    # print("Узлы:")
    # for node in graph.nodes.values():
    #     print(node)

    # print("\nРёбра:")
    # for edge in graph.edges:
    #     print(edge)
        
    # placement = place_level(
    # graph=graph,
    # size=(3, 4),
    # seed=42,
    # max_search_steps=10_000,
    # )

    # if placement is None:
    #     print("Не удалось найти размещение")
    # else:
    #     print(placement.positions)

    #     for row in placement.make_grid():
    #         print(row)
            
    #     print(render_placement(graph, placement))


main()
