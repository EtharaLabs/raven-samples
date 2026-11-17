# syntax=docker/dockerfile:1.10@sha256:865e5dd094beca432e8c0a1d5e1c465db5f998dca4e439981029b3b81fb39ed5
# Agent egress proxy. tinyproxy and its allowlist are installed at build time, so the
# container needs no network access to start.
FROM alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
RUN apk add --no-cache tinyproxy
COPY filter /etc/tinyproxy/filter
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
EXPOSE 3128
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
