## Artifact organization

The repository is organized into the following main components:

| Component | Description |
|---|---|
| [`adaptive-controller/`](adaptive-controller/) | **Implementation of the proposed Adaptive Control-Plane Configuration (ACP) controller.** This directory contains the standalone controller source code and its detailed usage and configuration instructions. |
| [`functions/`](functions/) | Knative function implementations used as workloads in the evaluation. |
| [`controller_adaptatif/`](controller_adaptatif/) | Experimental results produced using the adaptive controller, including results obtained while replaying the request workloads. |
| [`raspberry_local/`](raspberry_local/) | Results and experimental material for the local control-plane configuration. |
| [`raspberry_local_1core/`](raspberry_local_1core/) | Results and experimental material for the one-core-isolated control-plane configuration. |
| [`raspberry_local_apiserver_1core/`](raspberry_local_apiserver_1core/) | Results and experimental material for the API-server-isolated configuration. |
| [`Final_dataset/`](Final_dataset/) | Final experimental dataset used for the analysis reported in the paper. |

###

The artifact separates the **implementation of the proposed approach** from the **experimental results produced by that implementation**.

- **ACP implementation:** see [`adaptive-controller/`](adaptive-controller/).
- **Knative workloads:** see [`functions/`](functions/).
- **Results obtained with the adaptive controller:** see [`controller_adaptatif/`](controller_adaptatif/).
- **Results for the evaluated static configurations:** see the corresponding `raspberry_*` directories.
- **Final experimental dataset:** see [`Final_dataset/`](Final_dataset/).

For detailed instructions on building, configuring, and running the proposed controller, start with [`adaptive-controller/README.md`](adaptive-controller/README.md).
