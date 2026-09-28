# Compatibility fixture only: archived MinIO source, never a production image.
FROM golang:1.26-alpine@sha256:8ac98ca534ac3f51e1f420a1dd2c15e74c75cfa0f23f3ad27eb5d7236c349a0c AS build
RUN apk add --no-cache git ca-certificates
WORKDIR /src
RUN git init . && git remote add origin https://github.com/minio/minio.git && \
    git fetch --depth 1 origin d10bb7e1b667c2df72c394ef1fa52ab4a6802d0f && \
    git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = d10bb7e1b667c2df72c394ef1fa52ab4a6802d0f
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
RUN go mod download && go mod verify
RUN go build -trimpath -ldflags="-s -w" -o /out/minio .

FROM alpine:3.23@sha256:85fe1e81d6758c208f3e1eed4338a1997e19d4be002d4dd32d3100c9a8c010a0
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="d10bb7e1b667c2df72c394ef1fa52ab4a6802d0f" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.description="ARGUS isolated recovery fixture; not approved for production"
RUN apk add --no-cache ca-certificates && \
    addgroup -S minio && adduser -S -G minio minio && \
    mkdir /data && chown minio:minio /data
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /usr/share/licenses/minio/LICENSE
USER minio
EXPOSE 9000
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data"]
