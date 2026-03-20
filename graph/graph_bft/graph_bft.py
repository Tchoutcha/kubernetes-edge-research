import io
import json
import time
import logging
import sys
import networkx as nx


def bfs_handle(body):
    """Compute BFS traversal from adjacency_data graph."""
    if "graph" not in body:
        raise ValueError("Missing 'graph' field")

    graph = nx.adjacency_graph(body["graph"])
    start_vertex = body.get("startVertex", 0)

    bfs_list = nx.bfs_successors(graph, start_vertex)
    bfs_result = []
    first = True
    for node, successors in bfs_list:
        if first:
            bfs_result.append(node)
            first = False
        bfs_result.extend(successors)

    return bfs_result


def handler(data: io.BytesIO = None):
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        start_time = time.time()
        bfs_result = bfs_handle(body)
        end_time = time.time()

        return json.dumps({
            "status": "success",
            "result":{"function": "BFS", "result": bfs_result},
            "execution_time_sec": end_time - start_time
        }, indent=2)

    except Exception as e:
        logging.error(str(e))
        return json.dumps({
            "status": "error",
            "details": str(e)
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))