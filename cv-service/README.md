# cv-service

OpenCV preprocessing + ONNX/YOLO defect detection microservice. Lands in **Phase 3**.

| | |
|---|---|
| **Port (host)** | `9102` |
| **Health** | `GET /health` (Phase 3) |
| **Contract** | Consumes `contracts/cv-finding-schema` |
| **Standalone** | TBD Phase 3 (containerized) |

Phase 0: directory + README only. CI must not run GPU inference (ADR-001).
