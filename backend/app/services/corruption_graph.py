from collections import deque
from dataclasses import dataclass
from random import randint
from uuid import uuid4

from app.config import settings
from app.schemas.prajatantra import (
    AuditPath,
    AuditRequest,
    AuditResponse,
    GraphEdge,
    GraphNode,
    ScamOperationRequest,
    ScamOperationResponse,
)


def _node(label: str, name: str, **properties: str | int | float | bool) -> GraphNode:
    node_id = f"{label.lower()}:{properties.get('id') or properties.get('name') or name}:{uuid4().hex[:6]}"
    return GraphNode(id=node_id, label=label, name=name, properties={"name": name, **properties})


@dataclass
class MemoryGraph:
    nodes: dict[str, GraphNode]
    edges: list[GraphEdge]
    project_index: dict[str, str]

    def add_scene(self, project_id: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self.nodes.update({node.id: node for node in nodes})
        self.edges.extend(edges)
        project = next(node for node in nodes if node.label == "Project")
        self.project_index[project_id] = project.id
        self.project_index[project.name.lower()] = project.id

    def outgoing(self, source: str) -> list[GraphEdge]:
        return [edge for edge in self.edges if edge.source == source]


class CorruptionGraphService:
    def __init__(self) -> None:
        self.memory = MemoryGraph(nodes={}, edges=[], project_index={})

    async def create_layered_scam(self, payload: ScamOperationRequest) -> ScamOperationResponse:
        project_id = f"PRJ-{uuid4().hex[:8].upper()}"
        nodes, edges = self._build_memory_scene(project_id, payload)
        cypher, parameters = self._build_cypher(project_id, payload)

        graph_backend = "memory"
        if settings.neo4j_enabled:
            try:
                await self._write_to_neo4j(cypher, parameters)
                graph_backend = "neo4j"
            except Exception:
                graph_backend = "memory"

        self.memory.add_scene(project_id, nodes, edges)
        return ScamOperationResponse(
            project_id=project_id,
            cypher=cypher,
            parameters=parameters,
            nodes=nodes,
            edges=edges,
            graph_backend=graph_backend,
        )

    async def audit_project(self, payload: AuditRequest) -> AuditResponse:
        start_id = self._find_project(payload)
        if not start_id:
            return AuditResponse(
                project_id=payload.project_id,
                project_name=payload.project_name,
                audit_level=payload.audit_level,
                corruption_detected=False,
                smoking_gun=None,
                paths=[],
                next_upgrade_hint="No matching project has been seeded yet. Create a budget operation first.",
            )

        paths = self._bounded_paths(start_id, payload.audit_level)
        detected = [path for path in paths if path.nodes[-1].label == "Player"]
        smoking_gun = None
        if detected:
            player = detected[0].nodes[-1]
            account = next((node for node in detected[0].nodes if node.label == "Account"), None)
            if account:
                smoking_gun = f"{account.name} is controlled by {player.name}"
            else:
                smoking_gun = f"Funds connect to {player.name}"

        return AuditResponse(
            project_id=payload.project_id,
            project_name=self.memory.nodes[start_id].name,
            audit_level=payload.audit_level,
            corruption_detected=bool(detected),
            smoking_gun=smoking_gun,
            paths=paths,
            next_upgrade_hint=self._upgrade_hint(payload.audit_level, bool(detected)),
        )

    def _build_memory_scene(
        self, project_id: str, payload: ScamOperationRequest
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        treasury = _node("Treasury", f"{payload.city_id} Treasury", city_id=payload.city_id, balance=0)
        department = _node(
            "Department",
            payload.department_name,
            portfolio_type=payload.portfolio_type,
        )
        project = _node(
            "Project",
            payload.project_name,
            id=project_id,
            public_budget=payload.public_budget,
            actual_value=payload.actual_value,
        )
        prime_vendor = _node("Vendor", payload.vendor_name, is_shell=False)
        player = _node("Player", payload.incumbent_username, incumbent=True)
        account_number = f"OFF_{randint(1000, 9999)}"
        account = _node("Account", account_number, acc_num=account_number, is_offshore=True)
        shells = [
            _node("Vendor", f"{name} Holdings {idx + 1}", is_shell=True)
            for idx, name in enumerate(["BlueSky", "Monsoon", "Saffron", "Harbor", "Lotus", "Meridian"][: payload.layer_depth])
        ]

        nodes = [treasury, department, project, prime_vendor, *shells, account, player]
        edges = [
            self._edge(treasury, department, "ALLOCATED", amount=payload.public_budget, fiscal_week=1),
            self._edge(
                department,
                project,
                "COMMISSIONED",
                declared_cost=payload.public_budget,
                actual_value=payload.actual_value,
            ),
            self._edge(project, prime_vendor, "AWARDED_TO", contract_value=payload.public_budget),
        ]

        previous = prime_vendor
        remaining_amount = payload.siphoned_amount
        for depth, shell in enumerate(shells, start=1):
            edge_amount = round(remaining_amount * (0.98 ** (depth - 1)))
            edges.append(
                self._edge(
                    previous,
                    shell,
                    "SUBCONTRACTED",
                    layer_depth=depth,
                    amount=edge_amount,
                    fake_service="Logistics Consultancy",
                )
            )
            previous = shell

        edges.append(self._edge(previous, account, "REMITTED_TO", amount=round(payload.siphoned_amount * 0.95), transfer_method="Wire"))
        edges.append(self._edge(account, player, "CONTROLLED_BY", anonymity_score=0.85))
        return nodes, edges

    def _build_cypher(self, project_id: str, payload: ScamOperationRequest) -> tuple[str, dict[str, str | int | float | bool]]:
        shell_create_lines: list[str] = []
        previous_variable = "v1"
        for depth in range(1, payload.layer_depth + 1):
            shell_variable = f"v{depth + 1}"
            shell_key = f"shell_name_{depth}"
            amount_key = f"shell_amount_{depth}"
            shell_create_lines.append(
                f'CREATE ({shell_variable}:Vendor {{name: ${shell_key}, is_shell: true}})'
            )
            shell_create_lines.append(
                f'CREATE ({previous_variable})-[:SUBCONTRACTED '
                f'{{layer_depth: {depth}, amount: ${amount_key}, fake_service: "Logistics Consultancy"}}]->({shell_variable})'
            )
            previous_variable = shell_variable

        cypher_lines = [
            "MERGE (t:Treasury {city_id: $city_id})",
            "CREATE (d:Department {name: $department_name, portfolio_type: $portfolio_type})",
            "CREATE (p:Project {id: $project_id, name: $project_name, public_budget: $public_budget, actual_value: $actual_value})",
            "CREATE (v1:Vendor {name: $vendor_name, is_shell: false})",
            "CREATE (t)-[:ALLOCATED {amount: $public_budget, fiscal_week: 1}]->(d)",
            "CREATE (d)-[:COMMISSIONED {declared_cost: $public_budget, actual_value: $actual_value}]->(p)",
            "CREATE (p)-[:AWARDED_TO {contract_value: $public_budget}]->(v1)",
            *shell_create_lines,
            "CREATE (a:Account {acc_num: $offshore_account, is_offshore: true})",
            "MERGE (pl:Player {username: $incumbent_username})",
            f'CREATE ({previous_variable})-[:REMITTED_TO {{amount: $remitted_amount, transfer_method: "Wire"}}]->(a)',
            "CREATE (a)-[:CONTROLLED_BY {anonymity_score: 0.85}]->(pl)",
            "RETURN p.id AS project_id",
        ]
        cypher = "\n".join(cypher_lines)
        offshore_account = f"OFF_{randint(1000, 9999)}"
        parameters: dict[str, str | int | float | bool] = {
            "city_id": payload.city_id,
            "department_name": payload.department_name,
            "portfolio_type": payload.portfolio_type,
            "project_id": project_id,
            "project_name": payload.project_name,
            "public_budget": payload.public_budget,
            "actual_value": payload.actual_value,
            "vendor_name": payload.vendor_name,
            "layer_depth": payload.layer_depth,
            "siphoned_amount": payload.siphoned_amount,
            "remitted_amount": round(payload.siphoned_amount * 0.95),
            "offshore_account": offshore_account,
            "incumbent_username": payload.incumbent_username,
        }
        for depth in range(1, payload.layer_depth + 1):
            parameters[f"shell_name_{depth}"] = f"Shell Layer {depth} for {project_id}"
            parameters[f"shell_amount_{depth}"] = round(payload.siphoned_amount * (0.98 ** (depth - 1)))
        return cypher, parameters

    async def _write_to_neo4j(self, cypher: str, parameters: dict[str, str | int | float | bool]) -> None:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        async with driver:
            async with driver.session(database=settings.neo4j_database) as session:
                await session.run(cypher, parameters)

    def _edge(self, source: GraphNode, target: GraphNode, rel_type: str, **properties: str | int | float | bool) -> GraphEdge:
        return GraphEdge(source=source.id, target=target.id, type=rel_type, properties=properties)

    def _find_project(self, payload: AuditRequest) -> str | None:
        if payload.project_id and payload.project_id in self.memory.project_index:
            return self.memory.project_index[payload.project_id]
        return self.memory.project_index.get(payload.project_name.lower())

    def _bounded_paths(self, start_id: str, max_depth: int) -> list[AuditPath]:
        queue = deque([(start_id, [start_id], [])])
        completed: list[AuditPath] = []

        while queue:
            current, node_ids, edges = queue.popleft()
            if edges:
                nodes = [self.memory.nodes[node_id] for node_id in node_ids]
                completed.append(
                    AuditPath(
                        hop_count=len(edges),
                        nodes=nodes,
                        edges=edges,
                        suspicion_score=self._suspicion_score(nodes, edges),
                    )
                )
            if len(edges) >= max_depth:
                continue
            for edge in self.memory.outgoing(current):
                if edge.target in node_ids:
                    continue
                queue.append((edge.target, [*node_ids, edge.target], [*edges, edge]))

        return sorted(completed, key=lambda path: (path.nodes[-1].label != "Player", -path.suspicion_score, path.hop_count))

    def _suspicion_score(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> int:
        score = 10
        score += 22 if any(node.label == "Vendor" and node.properties.get("is_shell") for node in nodes) else 0
        score += 28 if any(node.label == "Account" and node.properties.get("is_offshore") for node in nodes) else 0
        score += 35 if any(node.label == "Player" for node in nodes) else 0
        score += 5 if any(edge.type == "SUBCONTRACTED" for edge in edges) else 0
        return min(score, 100)

    def _upgrade_hint(self, audit_level: int, detected: bool) -> str:
        if detected:
            return "Smoking gun found. Package the path as a campaign leak before election day."
        return f"Level {audit_level} exposed suspicious layers but not ownership. Upgrade audit depth to {audit_level + 1}."


corruption_graph = CorruptionGraphService()
