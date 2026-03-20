import io
import json
import logging
import time
import sys
import networkx as nx
from networkx.readwrite import json_graph


def build_graph(event):
    size = event.get('size')
    if size is None:
        raise ValueError("Missing 'size' parameter")

    startVertex = event.get('startVertex', 0)
    graph_type = event.get("graph_type", "complete")

    if graph_type.lower() == "barabasi":
        edges = event.get('edges')
        if edges is None:
            raise ValueError("Missing 'edges' parameter for barabasi graph")
        graph = nx.barabasi_albert_graph(size, edges)

    elif graph_type.lower() == "binomial_tree":
        graph = nx.binomial_tree(size)

    elif graph_type.lower() == "power_law":
        edges = event.get('edges')
        if edges is None:
            raise ValueError("Missing 'edges' parameter for power_law graph")
        graph = nx.powerlaw_cluster_graph(size, edges, p=0.5)

    else:
        graph = nx.complete_graph(size)

    graph_dict = json_graph.adjacency_data(graph)
    return {
        "graph": graph_dict,
        "startVertex": startVertex
    }


def handler(data: io.BytesIO = None):
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        event = json.loads(data.getvalue())

        start_time = time.time()
        graph_result = build_graph(event)

        return json.dumps({
            "status": "success",
            "result": graph_result,
            "execution_time_sec": round(time.time() - start_time, 6)
        }, indent=2)

    except Exception as e:
        logging.error(str(e))
        return json.dumps({
            "status": "error",
            "error": "Processing error",
            "details": str(e)
        })


if __name__ == "__main__":
    data = io.BytesIO(sys.stdin.buffer.read())
    print(handler(data=data))