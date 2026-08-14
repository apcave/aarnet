#!/usr/bin/env python3
"""Stochastic load test for the network APIs.

This script creates a large but configurable multi-user load profile to
exercise all of the API endpoints in the project, including user auth,
network creation, site/device/interface management, and connection
creation using the nested connection endpoint.

Typical usage:
  python run_time_tests/stochastic_load_test.py \
      --base-url http://localhost:8000
  python run_time_tests/stochastic_load_test.py \
      --base-url http://localhost:8000 --users 20 --parallel 8

The default targets are sized roughly to the scale of Australia's
higher-education network footprint: about 43 universities and a similar
order of magnitude for campus/site objects, with proportional device,
interface and connection counts.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error, request
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "run_time_tests" / "test_data.json"
ENV_PATH = ROOT / ".env"

DEFAULT_TARGETS = {
    "users": 20,
    "networks": 43,
    "sites": 150,
    "devices": 450,
    "interfaces": 900,
    "connections": 600,
}

HALT_ON_STATUS = None


def load_seed_data() -> dict:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Seed data file not found: {DATA_PATH}")
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dotenv_values(path: Path = ENV_PATH) -> dict:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_admin_credentials() -> tuple[str | None, str | None]:
    env_values = load_dotenv_values()
    email = None
    for key in (
        "DJANGO_SUPERUSER_EMAIL",
        "ADMIN_EMAIL",
        "SUPERUSER_EMAIL",
        "EMAIL",
    ):
        value = env_values.get(key)
        if value:
            email = value
            break

    password = None
    for key in (
        "DJANGO_SUPERUSER_PASSWORD",
        "ADMIN_PASSWORD",
        "ADMIN_PASS",
        "DJANGO_ADMIN_PASSWORD",
        "DB_PASS",
        "PASSWORD",
    ):
        value = env_values.get(key)
        if value:
            password = value
            break

    return email, password


def resolve_admin_password() -> str | None:
    _, password = resolve_admin_credentials()
    return password


class ApiError(RuntimeError):
    """Raised when the HTTP API returns an error."""


class ApiClient:
    def __init__(
        self,
        base_url: str,
        debug_payloads: bool = False,
        halt_on_status: int | None = None,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.debug_payloads = debug_payloads
        self.halt_on_status = halt_on_status

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        token: str | None = None,
    ):
        url = urljoin(self.base_url, path)
        body = None
        headers = {"Accept": "application/json"}

        if self.debug_payloads:
            print(f"\n=== {method} {path} ===")
            if payload is not None:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                print("No payload")

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if token:
            headers["Authorization"] = f"Token {token}"
            if self.debug_payloads:
                print(f"Authorization: Token {token}...")

        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if self.debug_payloads:
                    print(f"Response status: {resp.status}")
                    if raw:
                        try:
                            print(
                                json.dumps(
                                    json.loads(raw.decode("utf-8")),
                                    indent=2,
                                    sort_keys=True,
                                )
                            )
                        except Exception:
                            print(raw.decode("utf-8", errors="replace"))
                    else:
                        print("Response body: <empty>")
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except error.HTTPError as exc:
            try:
                payload_text = exc.read().decode("utf-8")
                detail = payload_text[:1000]
            except Exception:
                detail = str(exc)
            message = f"HTTP {exc.code} for {method} {path}: {detail}"
            if self.debug_payloads:
                print(f"Response status: {exc.code}")
                print(detail)
            if (
                self.halt_on_status is not None
                and exc.code == self.halt_on_status
            ):
                print(
                    f"\nHALT requested on status {exc.code}: {method} {path}"
                )
                raise SystemExit(message)
            raise ApiError(message) from exc
        except (
            Exception
        ) as exc:  # pragma: no cover - proxy/connection failures
            raise ApiError(
                f"Request failed for {method} {path}: {exc}"
            ) from exc

    def health_check(self):
        return self._request("GET", "api/health-check/")

    def create_user(self, name: str, email: str, password: str):
        payload = {"name": name, "email": email, "password": password}
        return self._request("POST", "api/user/create/", payload)

    def create_user_as_admin(
        self, token: str, name: str, email: str, password: str
    ):
        payload = {"name": name, "email": email, "password": password}
        return self._request("POST", "api/user/create/", payload, token=token)

    def login(self, email: str, password: str):
        payload = {"email": email, "password": password}
        return self._request("POST", "api/user/token/", payload)

    def me(self, token: str):
        return self._request("GET", "api/user/me/", token=token)

    def list_networks(self, token: str):
        return self._request("GET", "api/network/networks/", token=token)

    def create_network(self, token: str, title: str, description: str = ""):
        return self._request(
            "POST",
            "api/network/networks/",
            {"title": title, "description": description},
            token=token,
        )

    def update_network(
        self, token: str, network_id: int, title: str, description: str = ""
    ):
        return self._request(
            "PATCH",
            f"api/network/networks/{network_id}/",
            {"title": title, "description": description},
            token=token,
        )

    def delete_network(self, token: str, network_id: int):
        return self._request(
            "DELETE", f"api/network/networks/{network_id}/", token=token
        )

    def list_sites(self, token: str):
        return self._request("GET", "api/network/sites/", token=token)

    def create_site(
        self, token: str, network_id: int, name: str, description: str = ""
    ):
        payload = {
            "network": network_id,
            "name": name,
            "description": description,
            "status": "active",
        }
        return self._request(
            "POST", "api/network/sites/", payload, token=token
        )

    def update_site(
        self,
        token: str,
        site_id: int,
        network_id: int,
        name: str,
        description: str = "",
    ):
        payload = {
            "network": network_id,
            "name": name,
            "description": description,
            "status": "active",
        }
        return self._request(
            "PATCH", f"api/network/sites/{site_id}/", payload, token=token
        )

    def delete_site(self, token: str, site_id: int):
        return self._request(
            "DELETE", f"api/network/sites/{site_id}/", token=token
        )

    def list_devices(self, token: str):
        return self._request("GET", "api/network/devices/", token=token)

    def create_device(
        self, token: str, site_id: int, name: str, serial_number: str
    ):
        payload = {
            "site": site_id,
            "name": name,
            "serial_number": serial_number,
        }
        return self._request(
            "POST", "api/network/devices/", payload, token=token
        )

    def update_device(
        self,
        token: str,
        device_id: int,
        site_id: int,
        name: str,
        serial_number: str,
    ):
        payload = {
            "site": site_id,
            "name": name,
            "serial_number": serial_number,
        }
        return self._request(
            "PATCH", f"api/network/devices/{device_id}/", payload, token=token
        )

    def delete_device(self, token: str, device_id: int):
        return self._request(
            "DELETE", f"api/network/devices/{device_id}/", token=token
        )

    def list_interfaces(self, token: str):
        return self._request("GET", "api/network/interfaces/", token=token)

    def create_interface(
        self, token: str, device_id: int, name: str, speed: int
    ):
        payload = {
            "device": device_id,
            "name": name,
            "speed": speed,
            "status": "up",
        }
        return self._request(
            "POST", "api/network/interfaces/", payload, token=token
        )

    def update_interface(
        self,
        token: str,
        interface_id: int,
        device_id: int,
        name: str,
        speed: int,
    ):
        payload = {
            "device": device_id,
            "name": name,
            "speed": speed,
            "status": "up",
        }
        return self._request(
            "PATCH",
            f"api/network/interfaces/{interface_id}/",
            payload,
            token=token,
        )

    def delete_interface(self, token: str, interface_id: int):
        return self._request(
            "DELETE", f"api/network/interfaces/{interface_id}/", token=token
        )

    def list_connections(self, token: str):
        return self._request("GET", "api/network/connections/", token=token)

    def create_connection(
        self,
        token: str,
        start_id: int,
        end_id: int,
        name: str,
        status: str = "connected",
    ):
        payload = {
            "name": name,
            "status": status,
            "start": start_id,
            "end": end_id,
        }
        return self._request(
            "POST", "api/network/connections/", payload, token=token
        )

    def create_connection_full(self, token: str, payload: dict):
        return self._request(
            "POST", "api/network/connections-full/", payload, token=token
        )

    def update_connection_full(
        self, token: str, connection_id: int, payload: dict
    ):
        return self._request(
            "PATCH",
            f"api/network/connections-full/{connection_id}/",
            payload,
            token=token,
        )

    def delete_connection(self, token: str, connection_id: int):
        return self._request(
            "DELETE", f"api/network/connections/{connection_id}/", token=token
        )


def split_total(total: int, parts: int):
    base, rem = divmod(total, parts)
    counts = [base + (1 if i < rem else 0) for i in range(parts)]
    return counts


def generate_username(seed_users: list[str], index: int) -> str:
    pool = seed_users or ["captain", "mate", "deckhand", "pilot"]
    return f"{pool[index % len(pool)]}{index + 1}"


def get_user_data_json(seed_users: dict, index: int):
    user_data = seed_users["users"][index % len(seed_users["users"])]
    first_name = user_data["first_name"]
    last_name = user_data["last_name"]
    username = user_data["username"]
    email = user_data["email"]
    return {
        "name": f"{first_name} {last_name}",
        "email": email,
        "username": username,
        "password": user_data["password"],
    }


def safe_call(name: str, operation, *args, **kwargs):
    halt_on_status = kwargs.pop("halt_on_status", None)
    if halt_on_status is None:
        halt_on_status = HALT_ON_STATUS

    try:
        value = operation(*args, **kwargs)
        return {"ok": True, "value": value, "name": name}
    except SystemExit:
        raise
    except Exception as exc:
        if isinstance(exc, ApiError):
            match = re.search(r"HTTP (\d{3})", str(exc))
            if (
                halt_on_status is not None
                and match
                and int(match.group(1)) == halt_on_status
            ):
                raise SystemExit(str(exc)) from exc
        return {"ok": False, "error": str(exc), "name": name}


def find_network_by_title(client: ApiClient, token: str, title: str):
    result = safe_call("list_networks", client.list_networks, token)
    if not result["ok"]:
        return None
    for network in result["value"] or []:
        if network.get("title") == title:
            return network
    return None


def find_site_by_name(
    client: ApiClient, token: str, network_id: int, name: str
):
    result = safe_call("list_sites", client.list_sites, token)
    if not result["ok"]:
        return None
    for site in result["value"] or []:
        if site.get("network") == network_id and site.get("name") == name:
            return site
    return None


def inject_invalid_payload(
    rng: random.Random, target: str, base_payload: dict | None = None
):
    if base_payload is None:
        base_payload = {}
    payload = dict(base_payload)

    if target == "network":
        if rng.random() < 0.5:
            payload["title"] = ""
        else:
            payload["description"] = None
    elif target == "site":
        payload["network"] = -999 if rng.random() < 0.5 else "bad-network"
        if rng.random() < 0.5:
            payload["name"] = ""
    elif target == "device":
        payload["site"] = -999 if rng.random() < 0.5 else None
        if rng.random() < 0.5:
            payload.pop("serial_number", None)
    elif target == "interface":
        payload["device"] = -999 if rng.random() < 0.5 else None
        payload["speed"] = -1 if rng.random() < 0.5 else "bad-speed"
    elif target == "connection":
        payload.pop("start", None)
        payload.pop("end", None)
        if rng.random() < 0.5:
            payload["status"] = "not-a-status"
    elif target == "nested-connection":
        payload.pop("start", None)
        if rng.random() < 0.5:
            payload["status"] = "not-a-status"
    return payload


def create_user_session(
    base_url: str,
    index: int,
    seed_users: dict,
    random_failures: float = 0.1,
    admin_password: str | None = None,
    debug_payloads: bool = False,
    halt_on_status: int | None = None,
    single_worker: bool = False,
):
    client = ApiClient(
        base_url, debug_payloads=debug_payloads, halt_on_status=halt_on_status
    )
    errors = []

    user = get_user_data_json(seed_users, index)

    login_result = safe_call(
        "login", client.login, user["email"], user["password"]
    )
    if login_result["ok"]:
        token = login_result["value"].get("token")
        if token is None:
            raise RuntimeError("login response missing token")

        me_result = safe_call("me", client.me, token)
        if me_result["ok"]:
            return {
                "index": index,
                "email": user["email"],
                "token": token,
                "password": user["password"],
                "name": user["name"],
                "created": False,
                "errors": [],
            }

    admin_email, env_admin_password = resolve_admin_credentials()
    admin_token = None
    if not admin_email or not env_admin_password:
        raise RuntimeError(
            "Admin credentials not found in environment variables or .env file"
        )

    admin_client = ApiClient(
        base_url, debug_payloads=debug_payloads, halt_on_status=halt_on_status
    )
    admin_login_result = safe_call(
        "login_admin", admin_client.login, admin_email, env_admin_password
    )
    if not admin_login_result["ok"]:
        raise RuntimeError(
            f"Admin login failed: {admin_login_result['error']}"
        )

    admin_token = admin_login_result["value"].get("token")
    if not admin_token:
        raise RuntimeError("admin login response missing token")

    create_result = safe_call(
        "create_user_as_admin",
        client.create_user_as_admin,
        admin_token,
        user["name"],
        user["email"],
        user["password"],
    )
    if not create_result["ok"]:
        raise RuntimeError(f"User creation failed: {create_result['error']}")

    login_result = safe_call(
        "login", client.login, user["email"], user["password"]
    )
    if not login_result["ok"]:
        return {
            "index": index,
            "email": user["email"],
            "token": None,
            "password": user["password"],
            "name": user["name"],
            "created": False,
            "errors": errors + [login_result["error"]],
        }

    token = login_result["value"].get("token")
    if token is None:
        return {
            "index": index,
            "email": user["email"],
            "token": None,
            "password": user["password"],
            "name": user["name"],
            "created": False,
            "errors": errors + ["login response missing token"],
        }

    me_result = safe_call("me", client.me, token)
    if not me_result["ok"]:
        return {
            "index": index,
            "email": user["email"],
            "token": token,
            "password": user["password"],
            "name": user["name"],
            "created": True,
            "errors": errors + [me_result["error"]],
        }

    return {
        "index": index,
        "email": user["email"],
        "token": token,
        "password": user["password"],
        "name": user["name"],
        "created": True,
        "errors": [],
    }


def exercise_user_workload(
    client: ApiClient,
    token: str,
    user_name: str,
    seed: dict,
    network_budget: int,
    site_budget: int,
    error_rate: float = 0.15,
):
    created_networks = []
    created_sites = []
    created_devices = []
    created_interfaces = []
    created_connections = []
    error_count = 0

    network_pool = seed["networks"]
    site_pool = seed["sites"]
    device_pool = seed["devices"]
    interface_pool = seed["interfaces"]
    rng = random.Random(
        sum(ord(ch) for ch in user_name) + network_budget + site_budget
    )

    for network_index in range(network_budget):
        title = f"{network_pool[network_index % len(network_pool)]}"
        payload = {
            "title": title,
            "description": f"Autogenerated network for {user_name}.",
        }
        if rng.random() < error_rate:
            payload = inject_invalid_payload(rng, "network", payload)
        network_result = safe_call(
            "create_network",
            client.create_network,
            token,
            payload["title"],
            payload.get("description", ""),
        )
        if not network_result["ok"]:
            existing = find_network_by_title(client, token, payload["title"])
            if existing is None:
                error_count += 1
                continue
            network = existing
        else:
            network = network_result["value"]
        created_networks.append(network)

        safe_call("list_networks", client.list_networks, token)

        if rng.random() < error_rate:
            update_payload = {"title": "", "description": "Updated network"}
        else:
            update_payload = {
                "title": f"{title}-patched",
                "description": "Maintained network",
            }
        safe_call(
            "update_network",
            client.update_network,
            token,
            network["id"],
            update_payload["title"],
            update_payload["description"],
        )

        site_iterations = max(1, site_budget // max(1, network_budget))
        for site_index in range(site_iterations):
            site_name = f"{site_pool[(network_index *
                                      3 +
                                      site_index) %
                                     len(site_pool)]}"
            site_payload = {
                "network": network["id"],
                "name": site_name,
                "description": f"Campus for {title}",
                "status": "active",
            }
            if rng.random() < error_rate:
                site_payload = inject_invalid_payload(
                    rng, "site", site_payload
                )
            site_result = safe_call(
                "create_site",
                client.create_site,
                token,
                site_payload.get("network", network["id"]),
                site_payload["name"],
                site_payload.get("description", ""),
            )
            if not site_result["ok"]:
                existing_site = find_site_by_name(
                    client, token, network["id"], site_payload["name"]
                )
                if existing_site is None:
                    error_count += 1
                    continue
                site = existing_site
            else:
                site = site_result["value"]
            created_sites.append(site)
            safe_call("list_sites", client.list_sites, token)

            safe_call(
                "update_site",
                client.update_site,
                token,
                site["id"],
                network["id"],
                f"{site_name}-updated",
                "Campus maintained",
            )

            for device_index in range(2):
                device_name = f"{device_pool[(network_index *
                                              5 +
                                              site_index *
                                              3 +
                                              device_index) %
                                             len(device_pool)]}"
                serial = f"SER-{uuid.uuid4().hex[:12]}"
                device_payload = {
                    "site": site["id"],
                    "name": device_name,
                    "serial_number": serial,
                }
                if rng.random() < error_rate:
                    device_payload = inject_invalid_payload(
                        rng, "device", device_payload
                    )
                device_result = safe_call(
                    "create_device",
                    client.create_device,
                    token,
                    device_payload.get("site", site["id"]),
                    device_payload["name"],
                    device_payload.get("serial_number", serial),
                )
                if not device_result["ok"]:
                    error_count += 1
                    continue
                device = device_result["value"]
                created_devices.append(device)
                safe_call("list_devices", client.list_devices, token)
                safe_call(
                    "update_device",
                    client.update_device,
                    token,
                    device["id"],
                    site["id"],
                    f"{device_name}-patched",
                    f"SER-{uuid.uuid4().hex[:12]}",
                )

                for iface_index in range(2):
                    iface_name = f"{interface_pool[(network_index *
                                                    4 +
                                                    site_index *
                                                    2 +
                                                    iface_index) %
                                                   len(interface_pool)]}"
                    iface_payload = {
                        "device": device["id"],
                        "name": iface_name,
                        "speed": 1000 + (iface_index * 250),
                        "status": "up",
                    }
                    if rng.random() < error_rate:
                        iface_payload = inject_invalid_payload(
                            rng, "interface", iface_payload
                        )
                    iface_result = safe_call(
                        "create_interface",
                        client.create_interface,
                        token,
                        iface_payload.get("device", device["id"]),
                        iface_payload["name"],
                        iface_payload.get("speed", 1000),
                    )
                    if not iface_result["ok"]:
                        error_count += 1
                        continue
                    iface = iface_result["value"]
                    created_interfaces.append(iface)
                    safe_call("list_interfaces", client.list_interfaces, token)
                    safe_call(
                        "update_interface",
                        client.update_interface,
                        token,
                        iface["id"],
                        device["id"],
                        f"{iface_name}-patched",
                        2000 + (iface_index * 250),
                    )

                    if len(created_interfaces) >= 2:
                        first_iface = created_interfaces[-2]
                        second_iface = created_interfaces[-1]
                        nested_payload = {
                            "name": (
                                f"{first_iface['name']}-"
                                f"{second_iface['name']}"
                            ),
                            "status": "connected",
                            "start": {
                                "network": {"title": title},
                                "site": {"name": site_name},
                                "device": {"name": device["name"]},
                                "interface": {"name": first_iface["name"]},
                            },
                            "end": {
                                "network": {"title": title},
                                "site": {"name": site_name},
                                "device": {"name": device["name"]},
                                "interface": {"name": second_iface["name"]},
                            },
                        }
                        if rng.random() < error_rate:
                            nested_payload = inject_invalid_payload(
                                rng, "nested-connection", nested_payload
                            )
                        conn_result = safe_call(
                            "create_connection_full",
                            client.create_connection_full,
                            token,
                            nested_payload,
                        )
                        if not conn_result["ok"]:
                            error_count += 1
                            continue
                        conn = conn_result["value"]
                        created_connections.append(conn)
                        safe_call(
                            "list_connections", client.list_connections, token
                        )

                        if len(created_connections) >= 2:
                            update_payload = {
                                "name": f"{conn['name']}-updated",
                                "status": "connected",
                                "start": nested_payload["start"],
                                "end": nested_payload["end"],
                            }
                            if rng.random() < error_rate:
                                update_payload["status"] = "not-a-status"
                            safe_call(
                                "update_connection_full",
                                client.update_connection_full,
                                token,
                                conn["id"],
                                update_payload,
                            )

    for conn in created_connections[
        : max(1, min(3, len(created_connections) // 5))
    ]:
        if rng.random() < error_rate:
            safe_call(
                "delete_connection",
                client.delete_connection,
                token,
                conn["id"] + 999999,
            )
        else:
            safe_call(
                "delete_connection",
                client.delete_connection,
                token,
                conn["id"],
            )

    safe_call("list_networks", client.list_networks, token)
    safe_call("list_sites", client.list_sites, token)
    safe_call("list_devices", client.list_devices, token)
    safe_call("list_interfaces", client.list_interfaces, token)
    safe_call("list_connections", client.list_connections, token)

    return {
        "networks": len(created_networks),
        "sites": len(created_sites),
        "devices": len(created_devices),
        "interfaces": len(created_interfaces),
        "connections": len(created_connections),
        "errors": error_count,
    }


def build_target_counts(user_count: int, targets: dict):
    net_counts = split_total(targets["networks"], user_count)
    site_counts = split_total(targets["sites"], user_count)
    device_counts = split_total(targets["devices"], user_count)
    interface_counts = split_total(targets["interfaces"], user_count)
    connection_counts = split_total(targets["connections"], user_count)
    return {
        "networks": net_counts,
        "sites": site_counts,
        "devices": device_counts,
        "interfaces": interface_counts,
        "connections": connection_counts,
    }


def run_load_test(
    base_url: str,
    user_count: int,
    parallel: int,
    dry_run: bool = False,
    error_rate: float = 0.15,
    debug_payloads: bool = False,
    halt_on_status: int | None = None,
    single_user: bool = False,
):
    global HALT_ON_STATUS
    seed = load_seed_data()
    if user_count < 1:
        raise ValueError("--users must be at least 1")

    if single_user:
        user_count = 1
        parallel = 1

    HALT_ON_STATUS = halt_on_status
    admin_password = resolve_admin_password()
    client = ApiClient(
        base_url, debug_payloads=debug_payloads, halt_on_status=halt_on_status
    )

    if dry_run:
        print(
            "Dry run: "
            f"{base_url} with {user_count} users and {parallel} "
            "workers"
        )
        print(
            json.dumps(
                {
                    "targets": DEFAULT_TARGETS,
                    "error_rate": error_rate,
                    "admin_password_loaded": bool(admin_password),
                    "single_worker": parallel == 1,
                    "halt_on_status": halt_on_status,
                    "debug_payloads": debug_payloads,
                },
                indent=2,
            )
        )
        return

    try:
        client.health_check()
    except Exception as exc:
        print(
            "Warning: API health check failed ("
            f"{exc}). Continuing with the load test anyway.",
            file=sys.stderr,
        )

    targets = build_target_counts(user_count, DEFAULT_TARGETS)
    print(
        "Creating "
        f"{user_count} users with {parallel} workers "
        f"(error rate: {error_rate})..."
    )
    users = []
    for idx in range(len(seed["users"])):
        result = create_user_session(
            base_url,
            idx,
            seed,
            error_rate,
            admin_password,
            debug_payloads,
            halt_on_status,
            single_user,
        )
        if result.get("token"):
            users.append(result)

    print(f"Created {len(users)} usable user sessions.")

    total_summary = {
        "networks": 0,
        "sites": 0,
        "devices": 0,
        "interfaces": 0,
        "connections": 0,
        "errors": 0,
    }

    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = []
        for index in range(parallel):
            api = ApiClient(
                base_url,
                debug_payloads=debug_payloads,
                halt_on_status=halt_on_status,
            )
            user_inx = index % len(users)
            user = users[user_inx]
            futures.append(
                executor.submit(
                    exercise_user_workload,
                    api,
                    user["token"],
                    user["name"],
                    seed,
                    targets["networks"][user_inx],
                    targets["sites"][user_inx],
                    error_rate,
                )
            )

        for future in as_completed(futures):
            result = future.result()
            for key in (
                "networks",
                "sites",
                "devices",
                "interfaces",
                "connections",
            ):
                total_summary[key] += result.get(key, 0)
            total_summary["errors"] += result.get("errors", 0)

    print(
        json.dumps(
            {"targets": DEFAULT_TARGETS, "actual": total_summary}, indent=2
        )
    )
    return total_summary


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stochastic API load test for the network app."
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE_URL", "http://localhost:8000"),
        help="Base API URL, e.g. http://localhost:8000",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=DEFAULT_TARGETS["users"],
        help="Number of users to create and drive in parallel.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=8,
        help=(
            "Maximum parallel worker count for user creation and "
            "workload execution."
        ),
    )
    parser.add_argument(
        "--single-user",
        "--single-worker",
        dest="single_user",
        action="store_true",
        help=(
            "Use the first seeded user, skip user creation, and run "
            "one worker for a single-user debug flow."
        ),
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.15,
        help=(
            "Probability of injecting invalid payloads or deliberately "
            "bad IDs into a request. Range 0.0 to 1.0."
        ),
    )
    parser.add_argument(
        "--debug-payloads",
        action="store_true",
        help="Print the JSON payload for each API request before it is sent.",
    )
    parser.add_argument(
        "--halt-on-status",
        type=int,
        default=None,
        help=(
            "Stop the script immediately when a request returns this "
            "HTTP status code (for example 400 or 500)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display the target sizes without creating data.",
    )
    args = parser.parse_args()
    if args.single_user:
        args.parallel = 1
        args.users = 1
    return args


if __name__ == "__main__":
    args = parse_args()
    if not 0.0 <= args.error_rate <= 1.0:
        raise SystemExit("--error-rate must be between 0.0 and 1.0")
    if (
        args.halt_on_status is not None
        and not 100 <= args.halt_on_status <= 599
    ):
        raise SystemExit(
            "--halt-on-status must be a valid HTTP status code "
            "between 100 and 599"
        )
    try:
        run_load_test(
            args.base_url,
            args.users,
            args.parallel,
            dry_run=args.dry_run,
            error_rate=args.error_rate,
            debug_payloads=args.debug_payloads,
            halt_on_status=args.halt_on_status,
            single_user=args.single_user,
        )
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
