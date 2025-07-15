# Smart Lock Control System (MQTT Demo)

This project simulates a secure MQTT-based smart lock network using containers, TLS, and authenticated communication. It is intended to be run on WSL for windows. However, would run on Ubuntu or other Linux distributions but would require a small change to the start up scripts - the core python functionality would not need to change.

It runs:
- 1x MQTT broker (Mosquitto) with TLS + password auth
- 4x simulated smart lock devices
- 1x command-line interface (CLI) for issuing lock/unlock/status commands

---

## Quickstart

### Prerequisites

- **WSL (Windows Subsystem for Linux)**
- [Docker installed and running](https://docs.docker.com/get-docker/)
- Make sure Docker works with:
```bash
  docker version
```

**On WSL**: ensure Docker Desktop is installed on Windows and the WSL integration is enabled.

---

### Running the Demo

The full system can be launched with:

```bash
make start
```

This will:

* Fix permissions on the broker password file (if needed)
* Generate self-signed TLS certificates
* Start all containers with Docker Compose
* Open a multi-terminal view (on Windows) for logs and CLI control

> On Linux/macOS, logs will be printed to your terminal instead.

---

### Interacting with the System

Once the CLI terminal appears, type:

```text
help        # See available commands
status      # View all device states
lock 1      # Lock device lock-01
unlock 2    # Unlock device lock-02
metrics     # MQTT connection stats
```

To exit the CLI cleanly:

```text
exit        # Stops the manager
quit        # Exits the CLI and stops containers
```

---

## Useful Commands

```bash
make stop         # Stop and clean up containers/networks
make logs_broker  # Show broker logs
make logs_lock_01 # Show device logs (also for lock_02..lock_04)
make rebuild      # Force full container rebuild
make test         # Run end-to-end integration test
```

---

## Authentication Setup

The system uses:

* **TLS (with self-signed CA)** — automatically generated on first run
* **Username/password auth** — credentials are stored in `broker/passwd`

This file is **committed to the repo** for ease of demo use.

To regenerate it manually:

```bash
docker run --rm -v "$PWD/broker:/mosquitto/config" eclipse-mosquitto \
  mosquitto_passwd -b -c /mosquitto/config/passwd <USERNAME> <PASSWORD>
```

---

## Developer Notes

You do **not** need Python or Poetry to run the demo, the docker files handle this for you.
But for development:

```bash
conda env create -f environment.yml
conda activate smartlock-sim
poetry install
```

Then run the CLI standalone via:

```bash
python src/application/main.py
```

Make sure your broker is already running via Docker.

---

## 🧼 Cleanup

To stop everything and remove containers, networks, and volumes:

```bash
make stop
```

---

## Logging

You can control verbosity by editing `LOG_LEVEL=INFO` in the `docker-compose.yml` per-service.

---

## Run Integration Tests

To verify end-to-end functionality:

```bash
make test
```

This will:

* Start all services in test mode
* Run the test suite from the CLI container
* Tear everything down automatically
