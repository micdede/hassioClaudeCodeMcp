#!/usr/bin/env python3
"""Node-RED MCP Server for Claude Code — lets Claude read, search, edit and deploy Node-RED flows."""

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

NODE_RED_URL = os.environ.get("NODE_RED_URL", "http://localhost:1880")

app = Server("nodered-mcp")


def nr_request(method: str, path: str, data: Any = None) -> Any:
    url = f"{NODE_RED_URL}{path}"
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json", "Node-RED-API-Version": "v2"}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Node-RED API Fehler {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Keine Verbindung zu Node-RED unter {NODE_RED_URL}: {e.reason}\n"
            "Ist das Node-RED Add-on gestartet?"
        )


def get_all_nodes() -> list:
    return nr_request("GET", "/flows") or []


def find_tab(all_nodes: list, flow_id: str) -> dict | None:
    return next((n for n in all_nodes if n["id"] == flow_id and n.get("type") == "tab"), None)


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_flows",
            description="Listet alle Node-RED Flows (Tabs) mit ID, Name, Status und Anzahl der Nodes auf.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_flow",
            description="Gibt alle Nodes eines bestimmten Flows/Tabs zurück (vollständige Konfiguration).",
            inputSchema={
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "Die ID des Flow-Tabs"}
                },
                "required": ["flow_id"],
            },
        ),
        types.Tool(
            name="get_all_flows",
            description="Gibt die gesamte Node-RED Konfiguration als JSON zurück (alle Flows und Nodes).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="search_flows",
            description=(
                "Sucht Text in allen Flows. Findet Nodes nach Name, Funktionscode, Topic, Payload "
                "oder beliebigem anderen Feld."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Suchbegriff"},
                    "search_in": {
                        "type": "string",
                        "enum": ["all", "name", "func", "topic", "payload"],
                        "description": "Wo suchen? Standard: all",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="update_flow",
            description=(
                "Ersetzt einen einzelnen Flow/Tab durch eine neue Konfiguration und deployed sie sofort. "
                "flow_json muss ein Array sein: [Tab-Node, ...alle Nodes des Flows]."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "Die ID des zu ändernden Flow-Tabs"},
                    "flow_json": {
                        "type": "string",
                        "description": "Neue Flow-Konfiguration als JSON-String (Array mit Tab-Node und allen zugehörigen Nodes)",
                    },
                },
                "required": ["flow_id", "flow_json"],
            },
        ),
        types.Tool(
            name="deploy_all_flows",
            description="Deployed die komplette Flow-Konfiguration (ersetzt alles in Node-RED).",
            inputSchema={
                "type": "object",
                "properties": {
                    "flows_json": {
                        "type": "string",
                        "description": "Vollständige Flows-Konfiguration als JSON-String",
                    }
                },
                "required": ["flows_json"],
            },
        ),
        types.Tool(
            name="export_flows",
            description="Exportiert alle aktuellen Node-RED Flows als JSON (für Backup oder Analyse).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="import_flows",
            description=(
                "Importiert neue Flows in Node-RED (fügt hinzu, ohne bestehende zu löschen). "
                "Nodes mit bereits existierender ID werden übersprungen."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "flows_json": {
                        "type": "string",
                        "description": "Zu importierende Flows als JSON-String",
                    }
                },
                "required": ["flows_json"],
            },
        ),
        types.Tool(
            name="get_node",
            description="Gibt die Konfiguration eines einzelnen Nodes anhand seiner ID zurück.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Die Node-ID"}
                },
                "required": ["node_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    def text(content: Any) -> list[types.TextContent]:
        if isinstance(content, str):
            return [types.TextContent(type="text", text=content)]
        return [types.TextContent(type="text", text=json.dumps(content, indent=2, ensure_ascii=False))]

    try:
        if name == "list_flows":
            all_nodes = get_all_nodes()
            tabs = [n for n in all_nodes if n.get("type") == "tab"]
            result = []
            for tab in tabs:
                node_count = sum(1 for n in all_nodes if n.get("z") == tab["id"])
                result.append({
                    "id": tab["id"],
                    "label": tab.get("label", "(kein Name)"),
                    "disabled": tab.get("disabled", False),
                    "info": tab.get("info", ""),
                    "node_count": node_count,
                })
            return text(result)

        elif name == "get_flow":
            flow_id = arguments["flow_id"]
            all_nodes = get_all_nodes()
            tab = find_tab(all_nodes, flow_id)
            if not tab:
                return text(f"Kein Flow mit ID '{flow_id}' gefunden.")
            nodes = [n for n in all_nodes if n.get("z") == flow_id]
            return text({"tab": tab, "nodes": nodes})

        elif name == "get_all_flows":
            return text(get_all_nodes())

        elif name == "search_flows":
            query = arguments["query"].lower()
            search_in = arguments.get("search_in", "all")
            all_nodes = get_all_nodes()

            matches = []
            for node in all_nodes:
                if node.get("type") == "tab":
                    continue

                if search_in == "all":
                    haystack = json.dumps(node, ensure_ascii=False).lower()
                else:
                    haystack = str(node.get(search_in, "")).lower()

                if query in haystack:
                    flow_id = node.get("z", "")
                    tab = find_tab(all_nodes, flow_id)
                    matches.append({
                        "node_id": node["id"],
                        "node_type": node.get("type", ""),
                        "node_name": node.get("name", ""),
                        "flow_id": flow_id,
                        "flow_name": tab.get("label", "(kein Name)") if tab else "(unbekannt)",
                        "node": node,
                    })

            summary = f"{len(matches)} Node(s) gefunden für '{arguments['query']}':"
            return text(summary + "\n" + json.dumps(matches, indent=2, ensure_ascii=False))

        elif name == "update_flow":
            flow_id = arguments["flow_id"]
            new_nodes = json.loads(arguments["flow_json"])
            if not isinstance(new_nodes, list):
                new_nodes = [new_nodes]

            all_nodes = get_all_nodes()
            # Entferne alle alten Nodes dieses Flows (Tab + seine Nodes)
            other_nodes = [n for n in all_nodes if n["id"] != flow_id and n.get("z") != flow_id]
            merged = other_nodes + new_nodes
            nr_request("POST", "/flows", merged)
            return text(f"Flow '{flow_id}' wurde aktualisiert und deployed.")

        elif name == "deploy_all_flows":
            flows_data = json.loads(arguments["flows_json"])
            nr_request("POST", "/flows", flows_data)
            return text("Alle Flows erfolgreich deployed.")

        elif name == "export_flows":
            all_nodes = get_all_nodes()
            return text(json.dumps(all_nodes, indent=2, ensure_ascii=False))

        elif name == "import_flows":
            new_flows = json.loads(arguments["flows_json"])
            if not isinstance(new_flows, list):
                new_flows = [new_flows]

            current = get_all_nodes()
            existing_ids = {n["id"] for n in current}
            to_add = [n for n in new_flows if n["id"] not in existing_ids]
            nr_request("POST", "/flows", current + to_add)
            skipped = len(new_flows) - len(to_add)
            return text(f"{len(to_add)} Node(s) importiert. {skipped} übersprungen (ID bereits vorhanden).")

        elif name == "get_node":
            node_id = arguments["node_id"]
            all_nodes = get_all_nodes()
            node = next((n for n in all_nodes if n["id"] == node_id), None)
            if not node:
                return text(f"Kein Node mit ID '{node_id}' gefunden.")
            return text(node)

        else:
            return text(f"Unbekanntes Tool: {name}")

    except Exception as e:
        return text(f"Fehler: {e}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
