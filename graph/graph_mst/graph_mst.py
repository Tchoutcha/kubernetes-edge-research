import io
import json
import logging
import time
import sys
import networkx as nx


def compute_mst(body):
    if "graph" not in body:
        raise ValueError("Missing 'graph' field")

    graph = nx.adjacency_graph(body.get("graph"))
    mst = nx.minimum_spanning_tree(graph)
    result = list(mst.edges)
    return result


def handler(data: io.BytesIO = None):
    try:
        if not data:
            return json.dumps({"status": "error", "error": "Empty request body"})

        body = json.loads(data.getvalue())

        start_time = time.time()
        mst_result = compute_mst(body)

        return json.dumps({
            "status": "success",
            "result": {"function": "MST", "result":mst_result},
            "execution_time_sec": round(time.time() - start_time, 6)
        })

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