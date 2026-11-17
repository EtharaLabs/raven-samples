# syntax=docker/dockerfile:1.7.1@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
# Agent (inference) image. Built by Harbor from the environment/ build context because task.toml
# drops [environment].docker_image. The agent only reads the persona-rooted Mobile universe as
# JSON and writes actions.json, so it needs no dependencies and no network
# ([environment].network_mode = "no-network"). Built for linux/amd64 and linux/arm64 to match
# task.toml [metadata].platforms.
FROM python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

WORKDIR /app

# Bake the universe files (persona.json, contacts.json, chats/, emails/, calendar.json) into the
# agent workdir so they are readable offline at inference time.
COPY . /app

# Make the baked workdir writable by the non-root agent user so it can write actions.json.
RUN chown -R 1000:1000 /app

USER root
