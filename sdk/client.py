"""Synchronous gRPC SDK. TLS is caller-selected; insecure mode is loopback demo only."""

from dataclasses import dataclass

import atlas_pb2
import atlas_pb2_grpc
import grpc


@dataclass(frozen=True)
class Neighbor:
    id: int
    squared_l2: float


class Client:
    def __init__(self, target: str, token: str, *, secure: bool = True) -> None:
        self.channel = (
            grpc.secure_channel(target, grpc.ssl_channel_credentials())
            if secure
            else grpc.insecure_channel(target)
        )
        self.stub = atlas_pb2_grpc.SearchStub(self.channel)
        self.token = token

    def query(
        self,
        vector: list[float],
        *,
        k: int = 10,
        effort: int = 64,
        algorithm: str = "hnsw",
        tag: int = -1,
        timeout: float = 5.0,
    ) -> list[Neighbor]:
        response = self.stub.Query(
            atlas_pb2.QueryRequest(vector=vector, k=k, effort=effort, algorithm=algorithm, tag=tag),
            metadata=(("authorization", f"Bearer {self.token}"),),
            timeout=timeout,
        )
        return [Neighbor(n.id, n.squared_l2) for n in response.neighbors]

    def close(self) -> None:
        self.channel.close()
